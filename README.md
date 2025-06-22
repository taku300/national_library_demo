# 1. プロジェクトをクローンし、作業ディレクトリに移動
git clone <your-repo-url> national_library_demo
cd national_library_demo

# 2. Python 仮想環境を作成・有効化
python3 -m venv venv
source venv/bin/activate

# 3. OpenAI API キーを .env に設定（必要に応じてキーを差し替え）
echo "OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" > .env

# 4. パッケージをインストール
pip install -r requirements.txt

# 5. （任意）依存ライブラリを requirements.txt に書き出す
pip freeze > requirements.txt

# 6. アプリケーションを起動（開発モード）
uvicorn app:app --reload

# アクセス: http://localhost:8000/

# 7. （任意）Jupyter Lab を起動する（別ターミナルで実行してもOK）
# jupyter lab
