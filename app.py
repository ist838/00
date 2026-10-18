import requests

import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

# Render의 Environment에 설정할 값
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")

if not ADMIN_PASSWORD or not SESSION_SECRET:
    print("경고: ADMIN_PASSWORD와 SESSION_SECRET을 설정해야 합니다.")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET or "temporary-secret-change-this",
    https_only=True,
    same_site="lax",
)

DB_FILE = "visitors.db"


def init_db():
    with sqlite3.connect(DB_FILE) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                visited_at TEXT NOT NULL,
                path TEXT NOT NULL
            )
        """)


init_db()


def get_ip(request: Request):
    # Render의 프록시를 통해 전달된 접속 IP
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def log_visits(request: Request, call_next):
    if request.url.path not in ("/admin", "/login", "/logout"):
        try:
            ip = get_ip(request)
            now = datetime.now(
                ZoneInfo("Asia/Seoul")
            ).strftime("%Y-%m-%d %H:%M:%S")

            with sqlite3.connect(DB_FILE) as db:
                db.execute(
                    "INSERT INTO visits (ip, visited_at, path) VALUES (?, ?, ?)",
                    (ip, now, request.url.path),
                )
        except Exception as e:
            print("방문 기록 오류:", e)

    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>내 웹사이트</title>
    </head>
    <body style="font-family:Arial;text-align:center;padding:60px 15px">
        <h1>내 웹사이트에 오신 것을 환영합니다!</h1>
        <p>웹사이트가 정상적으로 실행 중입니다.</p>
        <p>방문 기록은 운영 및 보안 목적으로 저장될 수 있습니다.</p>
    </body>
    </html>
    """


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head><meta charset="UTF-8"><title>관리자 로그인</title></head>
    <body style="font-family:Arial;text-align:center;padding:50px 15px">
        <h1>관리자 로그인</h1>
        <form method="post" action="/login">
            <input name="password" type="password"
                   placeholder="관리자 비밀번호" required>
            <button type="submit">로그인</button>
        </form>
    </body>
    </html>
    """


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if not ADMIN_PASSWORD:
        return HTMLResponse("관리자 비밀번호가 서버에 설정되지 않았습니다.", status_code=500)

    if password != ADMIN_PASSWORD:
        return HTMLResponse("비밀번호가 틀렸습니다.", status_code=401)

    request.session["is_admin"] = True
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    if not request.session.get("is_admin"):
        return RedirectResponse("/login", status_code=303)

    with sqlite3.connect(DB_FILE) as db:
        rows = db.execute(
            "SELECT id, ip, visited_at, path FROM visits ORDER BY id DESC LIMIT 500"
        ).fetchall()

    table_rows = ""
    for row in rows:
        visit_id, ip, visited_at, path = row
        table_rows += (
            "<tr>"
            f"<td>{visit_id}</td>"
            f"<td>{escape(ip)}</td>"
            f"<td>{escape(visited_at)}</td>"
            f"<td>{escape(path)}</td>"
            "</tr>"
        )

    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>관리자 페이지</title>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
            th {{ background: #eee; }}
            .wrap {{ overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>방문 기록</h1>
        <p>최근 방문 기록 최대 500개</p>
        <p><a href="/logout">로그아웃</a></p>
        <div class="wrap">
        <table>
            <tr><th>번호</th><th>IP 주소</th><th>접속 시간</th><th>경로</th></tr>
            {table_rows}
        </table>
        </div>
    </body>
    </html>
    """


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
