from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from dotenv import load_dotenv
import os, asyncio, json

from jpsearch_client import search_japan_search_by_author

# 環境変数読み込み
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY が設定されていません")

openai_client = OpenAI(api_key=api_key)

# FastAPIアプリケーションとテンプレート
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# グローバル状態（簡易）
app.state.current_author = ""
app.state.ref_items = []

# -------------------------------
# トップページ（モード選択）
# -------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# -------------------------------
# 検索モード
# -------------------------------
@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    return templates.TemplateResponse("search.html", {
        "request": request,
        "results": None,
        "author": None,
        "error": None
    })

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, author: str = Form(...)):
    author = author.strip()
    if not author:
        return templates.TemplateResponse("search.html", {
            "request": request,
            "results": [],
            "author": "",
            "error": "著者名を入力してください。"
        })

    try:
        results = search_japan_search_by_author(author)
        if results:
            app.state.current_author = author
            app.state.ref_items = [{"title": r["title"], "date": r["date"]} for r in results[:3]]
        else:
            app.state.current_author = ""
            app.state.ref_items = []
            return templates.TemplateResponse("search.html", {
                "request": request,
                "results": [],
                "author": author,
                "error": "該当する資料が見つかりませんでした。"
            })

        return templates.TemplateResponse("search.html", {
            "request": request,
            "results": results,
            "author": author,
            "error": None
        })

    except Exception as e:
        print(f"[検索エラー] {e}")
        return templates.TemplateResponse("search.html", {
            "request": request,
            "results": [],
            "author": author,
            "error": "検索中にエラーが発生しました。"
        })

# -------------------------------
# 解説ストリーム（OpenAI + 検索結果）
# -------------------------------
@app.get("/stream")
async def stream():
    author = app.state.current_author
    ref_items = app.state.ref_items

    if not author or not ref_items:
        return JSONResponse({"error": "検索結果がありません。再度検索してください。"}, status_code=400)

    refs_md = "\n".join([f"- {itm['title']}（{itm['date']}）" for itm in ref_items])

    prompt = f"""
# 指示
文学作品や著書に関するユーザーに役に立つ情報を伝えるアドバイザーです。
ジャパンサーチで著者で検索したときの結果上位3件の参考作品を参照して、検索ワードに基づいた簡潔な説明をして下さい。

# 制約条件
- 出力は300字以内
- 親しみやすい口調でユーザー接してください。
- 必ず最後に次の著者の検索の提案を行ってください。
- 段落を明確に分けてください（空行を含めて）
- 段落が変わった場合は必ず見出しをつけてください。
- 完全なマークダウン形式で書いてください
- 参考作品がないときはその旨を伝えた上で役に立つ回答をしてください。

# 検索ワード
{author}

# 参考作品
{refs_md}
"""

    def run_sync():
        return openai_client.chat.completions.create(
            model="gpt-4o",
            stream=True,
            messages=[
                {"role": "system", "content": "あなたは文化解説者です。Markdown形式でわかりやすく出力してください。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
        )

    async def generator():
        try:
            loop = asyncio.get_event_loop()
            stream = await loop.run_in_executor(None, run_sync)
            for chunk in stream:
                text = getattr(chunk.choices[0].delta, "content", "")
                if text:
                    yield f"data: {json.dumps({'text': text})}\n\n"
                await asyncio.sleep(0)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")

# -------------------------------
# チャットモード（対話ベース検索）
# -------------------------------
@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/guess-author", response_class=JSONResponse)
async def guess_author_and_search_chain(request: Request):
    data = await request.json()
    history = data.get("history", [])

    print("\n📥 USER INPUT:")
    for h in history:
        print(f"{h['role']}: {h['content']}")

    messages = [
        {"role": "system", "content": """# 指示
あなたは文学作品や著書に関するユーザーに役に立つ情報を伝えるアシスタントです。
ジャパンサーチで検索ワードをお客さんのニーズから提案してください。

# 制約条件
- 出力は100字以内
- 親しみやすい口調でユーザーに接してください
- 相手のニーズが分からない場合はジャンル等をこちらから提案してください。
- 但し、無理に著者を提案するのは不自然なので、イメージできない場合は深掘りを行ってください。
- 段落を明確に分けてください（空行を含めて）
- 段落が変わった場合は必ず見出しをつけてください
- 完全なマークダウン形式で書いてください
"""}
    ]

    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({
        "role": "user",
        "content": "検索結果がまだない場合は、ユーザーの興味関心をふまえて、検索につながるような提案をしてください。"
    })

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.5,
        )
        message = response.choices[0].message.content.strip()

        plain_dialogue = [m for m in history if m["role"] in ("user", "assistant")]
        reversed_dialogue = "\n".join([f"{m['role']}: {m['content']}" for m in reversed(plain_dialogue)])
        print("\n🔁 抽出対象の本編対話履歴（逆順）:")
        print(reversed_dialogue)

        author_extraction = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": """
以下の会話履歴を新しい順に見て、ユーザーが関心を示している著者名を一人だけ日本語で正確に抽出してください。
文章ではなく、名前だけを返してください。もし明示されていなければ「不明」とだけ返してください。
"""},
                {"role": "user", "content": reversed_dialogue}
            ],
            temperature=0.2,
        )
        author_name = author_extraction.choices[0].message.content.strip()
        print(f"\n🔍 推定された著者名: [{author_name}]")

        if author_name.strip() == "不明":
            print("🚫 著者名が不明のため検索をスキップします。")
            return JSONResponse({
                "author": author_name,
                "message": message,
                "results": []
            })

        results = search_japan_search_by_author(author_name)
        print(f"📚 検索結果数: {len(results)} 件")

        return JSONResponse({
            "author": author_name,
            "message": message,
            "results": results
        })

    except Exception as e:
        print(f"\n❗ エラー: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
