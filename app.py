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

@app.post("/chat-stream")
async def chat_stream(request: Request):
    try:
        data = await request.json()
        history = data.get("history", [])

        print("\n📥 USER INPUT:")
        for h in history:
            print(f"{h['role']}: {h['content']}")

        # 🎯 会話生成のためのメッセージ（system含む）
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
            "content": """ユーザーの興味に基づいて、必ず具体的な著者名を1名以上提案してください。
著者名は検索可能な実在の日本の作家・文学者に限定し、その人の代表作も併せて紹介してください。
検索結果がまだない場合は、ユーザーの興味関心をふまえて検索につながる著者を提案してください。"""
        })

        # ストリーミング用の同期関数
        def run_sync():
            return openai_client.chat.completions.create(
                model="gpt-4o",
                stream=True,
                messages=messages,
                temperature=0.5,
            )

        # ストリーミングジェネレーター
        async def generator():
            collected_message = ""
            try:
                # ストリーミングレスポンス開始
                loop = asyncio.get_event_loop()
                stream = await loop.run_in_executor(None, run_sync)

                for chunk in stream:
                    text = getattr(chunk.choices[0].delta, "content", "")
                    if text:
                        collected_message += text
                        yield f"data: {json.dumps({'text': text})}\n\n"
                    await asyncio.sleep(0)

                # ストリーミング完了後に著者抽出と検索を実行
                print("\n💬 LLM応答完了。著者抽出を開始...")

                # ✅ 著者抽出対象：user/assistant のみ + 新しい応答
                updated_history = history + [{"role": "assistant", "content": collected_message}]
                plain_dialogue = [m for m in updated_history if m["role"] in ("user", "assistant")]

                # 📝 最新のユーザーメッセージを取得
                latest_user_message = ""
                user_messages = [m for m in plain_dialogue if m["role"] == "user"]
                if user_messages:
                    latest_user_message = user_messages[-1]["content"]

                total_user_turns = len(user_messages)

                # 📋 ターン番号付きの履歴を作成
                numbered_dialogue = []
                user_turn = 0
                for m in plain_dialogue:
                    if m["role"] == "user":
                        user_turn += 1
                        numbered_dialogue.append(f"[ターン{user_turn}] user: {m['content']}")
                    else:
                        numbered_dialogue.append(f"assistant: {m['content']}")

                formatted_history = "\n".join(numbered_dialogue)

                print(f"\n🔁 対話履歴（ターン番号付き）:")
                print(formatted_history)
                print(f"\n🎯 最新のユーザーメッセージ（ターン{total_user_turns}）: 「{latest_user_message}」")

                # 🎯 著者名抽出（非ストリーミング）
                def author_extraction_sync():
                    return openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": f"""
あなたは対話履歴から著者名を抽出する専門家です。

## 対話の構造について
- 対話は時系列順に並んでいます（[ターン1]が最初、[ターン{total_user_turns}]が最新）
- ターン番号が大きいほど新しい発言です
- **[ターン{total_user_turns}]が現在の最新のユーザー発言**です

## 抽出ルール（優先度順）
1. **最新ターン（[ターン{total_user_turns}]）のメッセージを最優先**で処理する
   - 最新ターンで著者名が明示されている場合は、過去の言及を無視してそれを採用
   - 「〜さん」「〜先生」などの敬語も著者名として認識
2. 最新ターンで著者が不明な場合のみ、過去のターンを参考にする
3. 複数の著者が異なるターンで言及された場合は、**より大きなターン番号**（より新しい）を選ぶ
4. 著者名のみを日本語で正確に返す（文章ではなく名前だけ）
5. どのターンでも明示されていなければ「不明」とだけ返す

## 抽出例
- [ターン3] user: 「有栖川有栖さん」→「有栖川有栖」
- [ターン2] user: 「夏目漱石について教えて」→「夏目漱石」
- [ターン1] user: 「東野圭吾」, [ターン2] user: 「有栖川有栖」→「有栖川有栖」（新しいターンを優先）

## 現在の状況
- 総ターン数: {total_user_turns}ターン
- 最新（最も重要）のユーザーメッセージ: 「{latest_user_message}」
- **この最新メッセージ（[ターン{total_user_turns}]）から著者名を最優先で抽出してください**

## 処理方針
1. まず[ターン{total_user_turns}]「{latest_user_message}」を詳しく分析
2. ここに著者名があれば即座に採用
3. なければターン番号の大きい順（新しい順）に確認
"""},
                            {"role": "user", "content": formatted_history}
                        ],
                        temperature=0.1,  # より一貫した結果のため低く設定
                    )

                author_response = await loop.run_in_executor(None, author_extraction_sync)
                author_name = author_response.choices[0].message.content.strip()

                # 敬語を除去する処理
                author_name = author_name.replace("さん", "").replace("先生", "").replace("氏", "")

                print(f"\n🔍 推定された著者名: [{author_name}]")

                # 🔎 ジャパンサーチAPIによる検索
                results = []
                if author_name.strip() != "不明":
                    def search_sync():
                        return search_japan_search_by_author(author_name)

                    results = await loop.run_in_executor(None, search_sync)
                    print(f"📚 検索結果数: {len(results)} 件")

                # 著者名と検索結果を送信
                yield f"data: {json.dumps({'author': author_name, 'results': results})}\n\n"

            except Exception as e:
                print(f"\n❗ ストリーミングエラー: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(generator(), media_type="text/event-stream")

    except Exception as e:
        print(f"\n❗ エラー: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
