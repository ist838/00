import os
import sqlite3
import hmac
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "visits.db")))
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")

if not SESSION_SECRET:
    raise RuntimeError("Render 환경 변수에 SESSION_SECRET을 설정하세요.")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    https_only=True,
    same_site="lax",
)


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


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    client_ip = request.client.host if request.client else "unknown"

    with connect_db() as conn:
        conn.execute(
            "INSERT INTO visits (ip, path, visited_at) VALUES (?, ?, ?)",
            (
                client_ip,
                "/",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head><meta charset="UTF-8"><title>IP CONTROL</title></head>
    <body style="background:#080b12;color:white;font-family:Arial;padding:40px">
        <h1>IP CONTROL</h1>
        <p>사이트가 정상적으로 실행 중입니다.</p>
        <a style="color:#4388ff" href="/admin">관리자 페이지</a>
    </body>
    </html>
    """


@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("admin") is True:
        return RedirectResponse("/admin", status_code=303)

    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>IP CONTROL 로그인</title>
    </head>
    <body style="background:#080b12;color:white;font-family:Arial;
                 display:grid;place-items:center;min-height:90vh">
        <form method="post" action="/admin/login"
              style="background:#111827;border:1px solid #25334b;
                     padding:30px;border-radius:15px;width:280px">
            <h2 style="color:#6ca4ff">IP CONTROL</h2>
            <p>관리자 비밀번호를 입력하세요.</p>
            <input type="password" name="password" required
                   autocomplete="current-password"
                   placeholder="비밀번호"
                   style="box-sizing:border-box;width:100%;padding:12px;
                          background:#080b12;color:white;
                          border:1px solid #34435e;border-radius:8px">
            <button type="submit"
                    style="width:100%;margin-top:15px;padding:12px;
                           background:#3478f6;color:white;border:0;
                           border-radius:8px;cursor:pointer">
                로그인
            </button>
        </form>
    </body>
    </html>
    """


@app.post("/admin/login")
async def login(request: Request):
    if not ADMIN_PASSWORD:
        return HTMLResponse(
            "Render 환경 변수 ADMIN_PASSWORD를 설정하세요.",
            status_code=503,
        )

    body = (await request.body()).decode("utf-8")
    values = parse_qs(body)
    password = values.get("password", [""])[0]

    if not hmac.compare_digest(password, ADMIN_PASSWORD):
        return HTMLResponse(
            "비밀번호가 틀렸습니다. <a href='/admin/login'>다시 시도</a>",
            status_code=401,
        )

    request.session.clear()
    request.session["admin"] = True
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    if request.session.get("admin") is not True:
        return RedirectResponse("/admin/login", status_code=303)

    with connect_db() as conn:
        records = conn.execute(
            "SELECT ip, path, visited_at FROM visits "
            "ORDER BY id DESC LIMIT 500"
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
