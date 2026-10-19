
import os
import hmac
import json
import sqlite3
import ipaddress
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
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

# ISP 조회 결과를 서버가 실행되는 동안 캐시
ISP_CACHE = {}


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
                visited_at TEXT NOT NULL,
                user_agent TEXT,
                browser TEXT,
                os TEXT,
                screen_width INTEGER,
                screen_height INTEGER
            )
        """)

        # 기존 데이터베이스에 새 열만 추가하고 기존 기록은 유지
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(visits)").fetchall()
        }

        additions = {
            "user_agent": "TEXT",
            "browser": "TEXT",
            "os": "TEXT",
            "screen_width": "INTEGER",
            "screen_height": "INTEGER",
        }

        for name, data_type in additions.items():
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE visits ADD COLUMN {name} {data_type}"
                )


def get_ip(request: Request) -> str:
    # 실제 접속 IP는 Render의 프록시 설정에 따라 달라질 수 있음.
    # 임의의 X-Forwarded-For 헤더를 직접 신뢰하지 않음.
    if request.client:
        return request.client.host
    return "unknown"


def parse_device(user_agent: str):
    ua = (user_agent or "").lower()

    if "edg/" in ua:
        browser = "Microsoft Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "firefox/" in ua:
        browser = "Firefox"
    elif "chrome/" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "safari/" in ua and "chrome/" not in ua:
        browser = "Safari"
    else:
        browser = "알 수 없음"

    if "windows" in ua:
        os_name = "Windows"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS/iPadOS"
    elif "android" in ua:
        os_name = "Android"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    else:
        os_name = "알 수 없음"

    return browser, os_name


init_db()


@app.get("/", response_class=HTMLResponse)
async def home():
    # 방문 기록은 아래 동의 화면에서 동의한 뒤 전송
    return """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>IP CONTROL</title>
<style>
body {
    background:#080b12;color:white;font-family:Arial,sans-serif;
    padding:40px;line-height:1.7
}
.panel {
    max-width:650px;margin:60px auto;background:#111827;
    border:1px solid #25334b;border-radius:16px;padding:28px
}
button,a {
    background:#3478f6;color:white;padding:12px 18px;
    border:0;border-radius:8px;cursor:pointer;text-decoration:none
}
.muted {color:#a9b6cc;font-size:14px}
</style>
</head>
<body>
<div class="panel">
    <h1>IP CONTROL</h1>
    <p>사이트가 정상적으로 실행 중입니다.</p>
    <p class="muted">
    보안 및 방문 통계를 위해 동의한 경우 IP 주소, 방문 시간,
    방문 페이지, 브라우저·운영체제 및 화면 크기 일부를 기록합니다.
    화면 크기는 브라우저에서 전달받습니다.
    </p>
    <button id="consent">동의하고 계속</button>
    <p id="status" class="muted"></p>
    <p><a href="/admin">관리자 페이지</a></p>
</div>
<script>
const button = document.getElementById("consent");
const statusText = document.getElementById("status");

async function recordVisit() {
    try {
        const response = await fetch("/track", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                consent: true,
                width: window.innerWidth,
                height: window.innerHeight
            })
        });
        if (!response.ok) throw new Error("기록 실패");
        statusText.textContent = "동의가 저장되었습니다.";
        button.disabled = true;
        button.textContent = "동의 완료";
    } catch (error) {
        statusText.textContent = "기록에 실패했습니다. 다시 시도해 주세요.";
        button.disabled = false;
    }
}

if (localStorage.getItem("ipcontrol_consent") === "yes") {
    button.textContent = "방문 기록 동의 완료";
    recordVisit();
}

button.addEventListener("click", () => {
    localStorage.setItem("ipcontrol_consent", "yes");
    recordVisit();
});
</script>
</body>
</html>
"""


@app.post("/track")
async def track(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "잘못된 요청"}, status_code=400)

    if data.get("consent") is not True:
        return JSONResponse({"error": "동의가 필요합니다."}, status_code=400)

    ip = get_ip(request)
    user_agent = request.headers.get("user-agent", "")[:1000]
    browser, os_name = parse_device(user_agent)

    # 브라우저에서 전달받은 크기는 범위 확인 후 저장
    try:
        width = int(data.get("width", 0))
        height = int(data.get("height", 0))
        if not (0 <= width <= 10000 and 0 <= height <= 10000):
            raise ValueError
    except (ValueError, TypeError):
        width, height = None, None

    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO visits
            (ip, path, visited_at, user_agent, browser, os,
             screen_width, screen_height)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ip,
                "/",
                datetime.now(timezone.utc).isoformat(),
                user_agent,
                browser,
                os_name,
                width,
                height,
            ),
        )

    return {"ok": True}


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
style="background:#111827;border:1px solid #25334b;padding:30px;
border-radius:15px;width:280px">
<h2 style="color:#6ca4ff">IP CONTROL</h2>
<p>관리자 비밀번호를 입력하세요.</p>
<input type="password" name="password" required
autocomplete="current-password" placeholder="비밀번호"
style="box-sizing:border-box;width:100%;padding:12px;
background:#080b12;color:white;border:1px solid #34435e;
border-radius:8px">
<button type="submit"
style="width:100%;margin-top:15px;padding:12px;
background:#3478f6;color:white;border:0;border-radius:8px">
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
            "비밀번호가 틀렸습니다. "
            "<a href='/admin/login'>다시 시도</a>",
            status_code=401,
        )

    request.session.clear()
    request.session["admin"] = True
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


@app.get("/admin/isp")
async def isp_lookup(request: Request, ip: str):
    if request.session.get("admin") is not True:
        return JSONResponse({"error": "로그인이 필요합니다."}, status_code=401)

    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return JSONResponse({"error": "IP 주소 형식이 잘못되었습니다."},
                            status_code=400)

    if not address.is_global:
        return JSONResponse({
            "error": "공인 IP 주소만 조회할 수 있습니다."
        }, status_code=400)

    if ip in ISP_CACHE:
        return ISP_CACHE[ip]

    # 버튼을 눌렀을 때만 외부 ISP 조회 서비스에 요청
    url = f"https://ipwho.is/{ip}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "IP-CONTROL/1.0"}
    )

    try:
        with urllib.request.urlopen(req, timeout=6) as response:
            result = json.loads(response.read().decode("utf-8"))

        if not result.get("success", False):
            return JSONResponse({
                "error": "ISP 정보를 조회하지 못했습니다."
            }, status_code=502)

        info = {
            "ip": ip,
            "country": result.get("country") or "알 수 없음",
            "region": result.get("region") or "알 수 없음",
            "city": result.get("city") or "알 수 없음",
            "isp": result.get("connection", {}).get("isp") or "알 수 없음",
            "org": result.get("connection", {}).get("org") or "알 수 없음",
            "asn": result.get("connection", {}).get("asn") or "알 수 없음",
        }

        ISP_CACHE[ip] = info
        return info

    except Exception:
        return JSONResponse({
            "error": "조회 서비스에 연결할 수 없습니다. 잠시 후 다시 시도하세요."
        }, status_code=502)


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    if request.session.get("admin") is not True:
        return RedirectResponse("/admin/login", status_code=303)

    with connect_db() as conn:
        records = conn.execute("""
            SELECT
                v.*,
                (SELECT COUNT(*) FROM visits AS x WHERE x.ip = v.ip)
                    AS ip_count
            FROM visits AS v
            ORDER BY v.id DESC
            LIMIT 500
        """).fetchall()

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
