from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from dotenv import load_dotenv
from SPARQLWrapper import SPARQLWrapper, JSON
import os, asyncio, json

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()
templates = Jinja2Templates(directory="templates")

app.state.current_author = ""
app.state.ref_items = []

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request, "results": None, "author": None
    })

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, author: str = Form(...)):
    sparql = SPARQLWrapper("https://jpsearch.go.jp/rdf/sparql")
    sparql.setQuery(f"""
        PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX schema:<http://schema.org/>
        SELECT ?item ?title ?creator ?date ?image WHERE {{
          ?item schema:name     ?title ;
                schema:creator  ?creatorURI .
          ?creatorURI rdfs:label ?creator .
          OPTIONAL {{ ?item schema:datePublished ?date }}
          OPTIONAL {{ ?item schema:image ?image }}
          FILTER(CONTAINS(STR(?creator), "{author}"))
        }} LIMIT 10
    """)
    sparql.setReturnFormat(JSON)
    bindings = sparql.query().convert()["results"]["bindings"]

    results = [{
        "title": b["title"]["value"],
        "creator": b["creator"]["value"],
        "date": b.get("date", {}).get("value", ""),
        "image": b.get("image", {}).get("value", ""),
        "link": b["item"]["value"]
    } for b in bindings]

    app.state.current_author = author
    app.state.ref_items = [{"title": r["title"], "date": r["date"]} for r in results[:3]]

    return templates.TemplateResponse("index.html", {
        "request": request, "results": results, "author": author
    })

@app.get("/stream")
async def stream():
    author = app.state.current_author
    ref_items = app.state.ref_items

    refs_md = "\n".join([f"- {itm['title']}（{itm['date']}）" for itm in ref_items])

    prompt = f"""
# 指示
あなたは日本文化・芸術の専門家です。国立図書館の検索で上位3件の作品を参考に、検索ワードに基づいた簡潔な説明をして下さい。

# 制約条件
- 出力は300字以内
- 段落を明確に分けてください（空行を含めて）
- 完全なマークダウン形式で書いてください

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
                {"role": "system", "content": "あなたは浮世絵の専門家です。Markdown形式で答えてください。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
        )

    async def generator():
        loop = asyncio.get_event_loop()
        stream = await loop.run_in_executor(None, run_sync)
        for chunk in stream:
            text = getattr(chunk.choices[0].delta, "content", "")
            if text:
                yield f"data: {json.dumps({'text': text})}\n\n"
            await asyncio.sleep(0)
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")
