## 🛠 National Library Demo セットアップ手順

1. **プロジェクトをクローンし、作業ディレクトリに移動する**
   - `git clone <your-repo-url> national_library_demo`
   - `cd national_library_demo`

2. **Python 仮想環境を作成・有効化する**
   - `python3 -m venv venv`
   - `source venv/bin/activate`

3. **OpenAI API キーを .env ファイルに設定する**
   - `echo "OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" > .env`

4. **必要な Python パッケージをインストールする**
   - `pip install -r requirements.txt`

5. **（任意）依存ライブラリを requirements.txt に書き出す**
   - `pip freeze > requirements.txt`

6. **アプリケーションを起動する（開発モード）**
   - `uvicorn app:app --reload`
   - アクセス: [http://localhost:8000/](http://localhost:8000/)

7. **（任意）Jupyter Lab を起動する**
   - `jupyter lab`
