from SPARQLWrapper import SPARQLWrapper, JSON
from typing import List, Dict, Union
import html
import re

def sanitize_input(text: str) -> str:
    """
    SPARQLインジェクションを避けるために簡単なサニタイズを行う。
    - 危険な記号の除去
    - HTMLエンコード（念のため）
    """
    text = re.sub(r'["\'`]', '', text)
    return html.escape(text)

def search_japan_search_by_author(author: str, limit: int = 10) -> List[Dict[str, Union[str, None]]]:
    """
    国立国会図書館 JP Search から、著者名に基づいて作品を検索する。

    Parameters:
    - author: 著者名（検索ワード）
    - limit: 最大取得件数（デフォルト10）

    Returns:
    - 検索結果のリスト。該当なし・エラー時も一定の形式で返す。
    """
    sanitized_author = sanitize_input(author)
    sparql = SPARQLWrapper("https://jpsearch.go.jp/rdf/sparql")
    sparql.setTimeout(15)  # タイムアウトを5秒に設定

    query = f"""
        PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX schema:<http://schema.org/>
        SELECT ?item ?title ?creator ?date ?image WHERE {{
          ?item schema:name ?title ;
                schema:creator ?creatorURI .
          ?creatorURI rdfs:label ?creator .
          OPTIONAL {{ ?item schema:datePublished ?date }}
          OPTIONAL {{ ?item schema:image ?image }}
          FILTER(CONTAINS(STR(?creator), "{sanitized_author}"))
        }} LIMIT {limit}
    """

    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        response = sparql.query().convert()
        bindings = response.get("results", {}).get("bindings", [])

        # 該当なし処理
        if not bindings:
            return [{
                "title": "該当する資料が見つかりませんでした。",
                "creator": author,
                "date": "",
                "image": "",
                "link": ""
            }]

        # 結果変換
        return [{
            "title": r["title"]["value"],
            "creator": r["creator"]["value"],
            "date": r.get("date", {}).get("value", ""),
            "image": r.get("image", {}).get("value", ""),
            "link": r["item"]["value"]
        } for r in bindings]

    except Exception as e:
        # 通信・SPARQLエラー時
        print(f"[SPARQL ERROR] {e}")
        return [{
            "title": "該当する資料が見つかりませんでした。",
            "creator": author,
            "date": "",
            "image": "",
            "link": "",
            "error": str(e)
        }]
