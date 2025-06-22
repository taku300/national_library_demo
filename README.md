# National Library Demo セットアップ手順

# 1. プロジェクトをクローン（またはフォルダを作成）
git clone <your-repo-url> national_library_demo
cd national_library_demo

# 2. Python 仮想環境を作成・有効化
python3 -m venv venv
source venv/bin/activate

# 3. .env ファイルを作成して OpenAI API キーを設定
echo "OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" > .env

# 4. 必要な依存ライブラリをインストール
pip install -r requirements.txt

# ※ 開発中に依存関係を追加したら以下で反映可能
# pip freeze > requirements.txt

# 5. アプリケーションを起動
uvicorn app:app --reload

# アクセス → http://localhost:8000/

# 6. （任意）Jupyter Lab を起動したい場合
jupyter lab
