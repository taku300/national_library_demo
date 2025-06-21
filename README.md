# 1. プロジェクトをクローン（または任意のフォルダを作成）
git clone <your-repo-url> national_library_demo
cd national_library_demo

# 2. Python仮想環境を作成
python -m venv venv

# 3. 仮想環境を有効化
source venv/bin/activate

# 4. .env ファイルを作成して OpenAI APIキーを登録
touch .env
以下を保存する
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 5. 依存ライブラリをインストール
# pip freeze > requirements.txt で定期的に更新可能
pip install -r requirements.txt

# 6. アプリを起動
uvicorn app:app --reload

# 7. ブラウザでアクセス
# http://localhost:8000/
