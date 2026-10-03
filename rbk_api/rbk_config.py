import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# --- База данных ---
RBK_DB_URL = os.getenv("RBK_DB_URL", f"sqlite:///{BASE_DIR}/rbk_db/rbk_dev.sqlite3")

# --- Сервер ---
RBK_API_HOST = os.getenv("RBK_API_HOST", "127.0.0.1")
RBK_API_PORT = int(os.getenv("RBK_API_PORT", "8101"))

RBK_WEB_DIR = BASE_DIR / "rbk_web"