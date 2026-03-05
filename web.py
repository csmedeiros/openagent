"""
OpenAgent Web — Flask server que serve o frontend (index.html).

Como rodar:
    python web.py

O frontend será acessível em http://localhost:3000
A API FastAPI deve estar rodando separadamente em http://localhost:8080
"""

import os
from flask import Flask, send_from_directory

# Diretório onde está o index.html (mesmo diretório deste arquivo)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename: str):
    """Serve qualquer arquivo estático (logo.png, etc.) a partir do diretório raiz."""
    return send_from_directory(BASE_DIR, filename)


if __name__ == "__main__":
    port = int(os.environ.get("WEB_PORT", 3000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    print(f"🌐  OpenAgent Web rodando em http://localhost:{port}")
    print(f"    Certifique-se de que a API está em http://localhost:8080")
    app.run(host="0.0.0.0", port=port, debug=debug)
