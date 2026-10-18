
import os
import hmac
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

app = FastAPI()
security = HTTPBasic()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "visits.db")))
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                path TEXT NOT NULL,
                visited_at TEXT NOT NULL
            )
        """)


init_db()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if not ADMIN_PASSWORD:
        raise HTTPException(
            status_code=503,
            detail="Render에서 ADMIN_PASSWORD 환경 변수를 설정하세요."
        )

    valid_user = hmac.compare_digest(
        credentials.username, ADMIN_USER
    )
    valid_password = hmac.compare_digest(
        credentials.password, ADMIN_PASSWORD
    )

    if not (valid_user and valid_password):
        raise HTTPException(
            status_code=401,
            detail="관리자 로그인 정보가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc).isoformat()

    with connect_db() as conn:
        conn.execute(
            "INSERT INTO visits (ip, path, visited_at) VALUES (?, ?, ?)",
            (client_ip, "/", now),
        )

    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head><meta charset="UTF-8"><title>IP CONTROL</title></head>
    <body style="background:#080a0f;color:white;font-family:Arial;padding:40px">
      <h1>IP CONTROL</h1>
      <p>사이트가 정상적으로 실행 중입니다.</p>
      <a style="color:#4388ff" href="/admin">관리자 페이지</a>
    </body>
    </html>
    """


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request, _: str = Depends(require_admin)):
    with connect_db() as conn:
        records = conn.execute(
            "SELECT ip, path, visited_at FROM visits ORDER BY id DESC LIMIT 500"
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM visits"
        ).fetchone()[0]
        unique = conn.execute(
            "SELECT COUNT(DISTINCT ip) FROM visits"
        ).fetchone()[0]
        latest_row = conn.execute(
            "SELECT visited_at FROM visits ORDER BY id DESC LIMIT 1"
        ).fetchone()

    latest = latest_row["visited_at"] if latest_row else "기록 없음"

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "total": total,
            "unique": unique,
            "latest": latest,
            "records": records,
        },
    )
