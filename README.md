# National Library Demo セットアップ手順

# 1. プロジェクトをクローンし、ディレクトリへ移動
`git clone <your-repo-url> national_library_demo`
`cd national_library_demo`

# 2. Python 仮想環境を作成・有効化
`python3 -m venv venv`
`source venv/bin/activate`

# 3. OpenAI API キーを含む .env ファイルを作成
`echo "OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" > .env`

# 4. 必要な依存パッケージをインストール
`pip install -r requirements.txt`

# ※ 開発中に依存を追加したら requirements.txt を更新
`# pip freeze > requirements.txt`

# 5. アプリケーションを開発モードで起動
`uvicorn app:app --reload`

# アプリにアクセス → http://localhost:8000/

# 6. （任意）Jupyter Lab を起動したい場合
`jupyter lab`
