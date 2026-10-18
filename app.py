
import os
import sqlite3
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape
from ipaddress import ip_address

import requests
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware


# =========================
# 기본 설정
# =========================

app = FastAPI()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
HIDDEN_IP = os.getenv("HIDDEN_IP", "").strip()

DB_FILE = "visitors.db"

if not ADMIN_PASSWORD:
    raise RuntimeError("Render Environment에 ADMIN_PASSWORD를 설정하세요.")

if not SESSION_SECRET:
    raise RuntimeError("Render Environment에 SESSION_SECRET을 설정하세요.")


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    https_only=True,
    same_site="lax",
)


# =========================
# 데이터베이스
# =========================

def init_db():
    with sqlite3.connect(DB_FILE) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                visited_at TEXT NOT NULL,
                path TEXT NOT NULL,
                vpn_status TEXT DEFAULT '확인 불가'
            )
        """)

        # 이전 버전 데이터베이스와 호환
        columns = {
            row[1]
            for row in db.execute("PRAGMA table_info(visits)").fetchall()
        }

        if "vpn_status" not in columns:
            db.execute(
                "ALTER TABLE visits ADD COLUMN vpn_status TEXT DEFAULT '확인 불가'"
            )


init_db()


# =========================
# 방문자 IP 확인
# =========================

def get_ip(request: Request) -> str:
    # Render의 프록시를 신뢰하도록 Start Command를 설정해야 함
    if request.client:
        return request.client.host
    return "unknown"


# =========================
# VPN / 프록시 확인
# =========================

def check_vpn(ip: str) -> str:
    try:
        parsed_ip = ip_address(ip)

        if not parsed_ip.is_global:
            return "확인 불가"

        response = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,message,proxy,hosting"},
            timeout=4,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            return "확인 불가"

        if data.get("proxy") or data.get("hosting"):
            return "VPN/프록시 의심"

        return "일반 IP 추정"

    except Exception:
        return "확인 불가"


async def check_vpn_async(ip: str) -> str:
    # 외부 조회 때문에 웹사이트가 오래 멈추지 않도록 별도 스레드 사용
    return await asyncio.to_thread(check_vpn, ip)


# =========================
# 방문 기록
# =========================

@app.middleware("http")
async def log_visits(request: Request, call_next):
    path = request.url.path

    # 관리자 페이지와 로그인/로그아웃은 기록하지 않음
    ignored_paths = {"/admin", "/login", "/logout"}

    if path not in ignored_paths:
        try:
            ip = get_ip(request)

            # 숨길 IP는 기록 자체를 저장하지 않음
            if ip != HIDDEN_IP and ip != "unknown":
                now = datetime.now(
                    ZoneInfo("Asia/Seoul")
                ).strftime("%Y-%m-%d %H:%M:%S")

                vpn_status = await check_vpn_async(ip)

                with sqlite3.connect(DB_FILE) as db:
                    db.execute(
                        """
                        INSERT INTO visits
                        (ip, visited_at, path, vpn_status)
                        VALUES (?, ?, ?, ?)
                        """,
                        (ip, now, path, vpn_status),
                    )

        except Exception as error:
            print("방문 기록 오류:", error)

    return await call_next(request)


# =========================
# 메인 페이지
# =========================

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>내 웹사이트</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 70px 20px;
                background: #f5f7fb;
                color: #202536;
            }
            main {
                max-width: 650px;
                margin: auto;
                padding: 35px 20px;
                background: white;
                border-radius: 18px;
                box-shadow: 0 5px 25px #0000000d;
            }
            h1 { color: #3458db; }
        </style>
    </head>
    <body>
        <main>
            <h1>내 웹사이트에 오신 것을 환영합니다!</h1>
            <p>웹사이트가 정상적으로 실행 중입니다.</p>
            <p>방문 기록은 운영 및 보안 목적으로 저장될 수 있습니다.</p>
        </main>
    </body>
    </html>
    """


# =========================
# 관리자 로그인 페이지
# =========================

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>관리자 로그인</title>
    </head>
    <body style="font-family:Arial;text-align:center;padding:60px 15px">
        <h1>관리자 로그인</h1>
        <form method="post" action="/login">
            <input
                name="password"
                type="password"
                placeholder="관리자 비밀번호"
                required
                autocomplete="current-password"
            >
            <button type="submit">로그인</button>
        </form>
    </body>
    </html>
    """


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if password != ADMIN_PASSWORD:
        return HTMLResponse(
            "비밀번호가 틀렸습니다. <a href='/login'>다시 시도</a>",
            status_code=401,
        )

    request.session["is_admin"] = True
    return RedirectResponse("/admin", status_code=303)


# =========================
# 관리자 방문 기록 페이지
# =========================

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    if not request.session.get("is_admin"):
        return RedirectResponse("/login", status_code=303)

    with sqlite3.connect(DB_FILE) as db:
        rows = db.execute(
            """
            SELECT id, ip, visited_at, path, vpn_status
            FROM visits
            ORDER BY id DESC
            LIMIT 500
            """
        ).fetchall()

    table_rows = ""

    for visit_id, ip, visited_at, path, vpn_status in rows:
        table_rows += f"""
        <tr>
            <td>{visit_id}</td>
            <td>{escape(ip)}</td>
            <td>{escape(visited_at)}</td>
            <td>{escape(path)}</td>
            <td>{escape(vpn_status or '확인 불가')}</td>
        </tr>
        """

    if not table_rows:
        table_rows = """
        <tr>
            <td colspan="5">아직 저장된 방문 기록이 없습니다.</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>관리자 페이지</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                padding: 20px;
                color: #222;
            }}
            .table-wrap {{ overflow-x: auto; }}
            table {{
                border-collapse: collapse;
                width: 100%;
                min-width: 650px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
            }}
            th {{ background: #edf1f8; }}
            a {{ margin-right: 12px; }}
        </style>
    </head>
    <body>
        <h1>방문 기록 관리</h1>
        <p>최근 방문 기록 최대 500개</p>
        <p>
            <a href="/">메인 페이지</a>
            <a href="/logout">로그아웃</a>
        </p>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>번호</th>
                        <th>IP 주소</th>
                        <th>접속 시간</th>
                        <th>경로</th>
                        <th>VPN 상태</th>
                    </tr>
                </thead>
                <tbody>{table_rows}</tbody>
            </table>
        </div>
        <p>VPN 상태는 추정 결과이며 정확하지 않을 수 있습니다.</p>
    </body>
    </html>
    """


# =========================
# 로그아웃
# =========================

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
