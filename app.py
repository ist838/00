<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IP CONTROL | 관리자</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #080a0f;
      --panel: #11151e;
      --border: #252c3a;
      --blue: #4388ff;
      --text: #f2f5fc;
      --muted: #8993a7;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, "Malgun Gothic", sans-serif;
    }

    .sidebar {
      position: fixed;
      inset: 0 auto 0 0;
      width: 230px;
      padding: 28px 18px;
      background: #0c0f16;
      border-right: 1px solid var(--border);
    }

    .logo {
      font-size: 22px;
      font-weight: 800;
      letter-spacing: 1px;
      margin: 5px 8px 40px;
    }

    .logo span {
      color: var(--blue);
    }

    .section-label {
      color: #667187;
      font-size: 11px;
      font-weight: bold;
      margin: 24px 10px 10px;
      letter-spacing: 1.5px;
    }

    .nav-item {
      display: block;
      padding: 13px 14px;
      margin: 5px 0;
      border-radius: 9px;
      color: #aeb8ca;
      text-decoration: none;
      font-size: 14px;
    }

    .nav-item.active {
      color: white;
      background: #192a49;
      border: 1px solid #254779;
    }

    main {
      margin-left: 230px;
      padding: 32px;
      max-width: 1600px;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 32px;
    }

    h1 {
      font-size: 27px;
      margin: 0 0 9px;
    }

    .muted {
      color: var(--muted);
      font-size: 13px;
    }

    .admin-badge {
      padding: 9px 13px;
      border: 1px solid #284a7d;
      border-radius: 9px;
      color: #80b5ff;
      background: #101d32;
      font-size: 12px;
      font-weight: bold;
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }

    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 21px;
      min-width: 0;
    }

    .stat-title {
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 18px;
    }

    .stat-value {
      font-size: 28px;
      font-weight: 800;
      overflow-wrap: anywhere;
    }

    .stat-note {
      color: #6d9eff;
      font-size: 12px;
      margin-top: 12px;
    }

    .table-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 14px;
      margin-bottom: 20px;
    }

    h2 {
      font-size: 18px;
      margin: 0 0 7px;
    }

    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 9px;
    }

    input, select, button {
      color: var(--text);
      background: #0b0e15;
      border: 1px solid #30394a;
      border-radius: 8px;
      padding: 11px 12px;
      font: inherit;
      font-size: 13px;
    }

    input {
      width: 230px;
      max-width: 100%;
    }

    button {
      background: var(--blue);
      border-color: var(--blue);
      cursor: pointer;
      font-weight: bold;
    }

    button:hover {
      filter: brightness(1.15);
    }

    .table-wrap {
      overflow-x: auto;
      margin: 0 -4px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      white-space: nowrap;
      font-size: 13px;
    }

    th, td {
      text-align: left;
      padding: 16px 14px;
      border-bottom: 1px solid #222937;
    }

    th {
      color: #8f9ab0;
      font-weight: 600;
      background: #0d1119;
    }

    td {
      color: #d8deea;
    }

    .ip {
      color: #83b5ff;
      font-family: Consolas, monospace;
    }

    .status {
      display: inline-block;
      padding: 5px 9px;
      border-radius: 6px;
      font-size: 11px;
      background: #132b20;
      color: #6de0a0;
    }

    .status.unknown {
      background: #302817;
      color: #f4c86a;
    }

    .empty {
      padding: 35px;
      color: var(--muted);
      text-align: center;
    }

    footer {
      color: #596477;
      text-align: center;
      font-size: 12px;
      margin-top: 25px;
    }

    @media (max-width: 1100px) {
      .stats {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      main {
        padding: 22px;
      }
    }

    @media (max-width: 650px) {
      .sidebar {
        position: static;
        width: 100%;
        padding: 17px;
        border-right: 0;
        border-bottom: 1px solid var(--border);
      }

      .logo {
        margin: 4px 5px 15px;
      }

      .section-label {
        display: none;
      }

      .nav-list {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
      }

      .nav-item {
        margin: 0;
        padding: 10px;
      }

      main {
        margin-left: 0;
        padding: 20px 14px;
      }

      h1 {
        font-size: 22px;
      }

      .stats {
        gap: 10px;
      }

      .card {
        padding: 15px;
      }

      .stat-value {
        font-size: 23px;
      }

      .topbar {
        align-items: flex-start;
      }

      input {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <aside class="sidebar">
    <div class="logo">IP <span>CONTROL</span></div>
    <div class="section-label">MANAGEMENT</div>
    <nav class="nav-list">
      <a class="nav-item active" href="/admin">▦ &nbsp; 대시보드</a>
      <a class="nav-item" href="#records">⌕ &nbsp; 접속 기록</a>
    </nav>
    <div class="section-label">SYSTEM</div>
    <nav class="nav-list">
      <a class="nav-item" href="/">↗ &nbsp; 사이트로 이동</a>
    </nav>
  </aside>

  <main>
    <header class="topbar">
      <div>
        <h1>관리자 대시보드</h1>
        <div class="muted">방문 기록과 접속 현황을 확인하세요.</div>
      </div>
      <div class="admin-badge">● ADMIN PANEL</div>
    </header>

    <section class="stats">
      <div class="card">
        <div class="stat-title">전체 접속 기록</div>
        <div class="stat-value" id="total">—</div>
        <div class="stat-note">누적 기록</div>
      </div>
      <div class="card">
        <div class="stat-title">고유 IP 수</div>
        <div class="stat-value" id="unique">—</div>
        <div class="stat-note">중복 제외</div>
      </div>
      <div class="card">
        <div class="stat-title">VPN · 프록시</div>
        <div class="stat-value" id="vpn">—</div>
        <div class="stat-note">확인 가능한 기록</div>
      </div>
      <div class="card">
        <div class="stat-title">최근 접속</div>
        <div class="stat-value" id="latest" style="font-size:18px">—</div>
        <div class="stat-note">마지막 기록 시간</div>
      </div>
    </section>

    <section class="card" id="records">
      <div class="table-header">
        <div>
          <h2>접속 기록</h2>
          <div class="muted">기록을 검색하고 필터링하세요.</div>
        </div>
        <div class="filters">
          <input id="search" placeholder="IP 또는 경로 검색">
          <input id="date" type="date" aria-label="날짜 필터">
          <button id="reset" type="button">초기화</button>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>IP 주소</th>
              <th>접속 시간</th>
              <th>경로</th>
              <th>VPN 상태</th>
            </tr>
          </thead>
          <tbody id="rows">
            <tr>
              <td colspan="4" class="empty">
                기존 서버의 기록 데이터 연결이 필요합니다.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <footer>IP CONTROL · PRIVATE ADMINISTRATION</footer>
  </main>

  <script>
    // 실제 데이터는 기존 Flask 서버에서 안전하게 전달해야 합니다.
    // 현재는 디자인 확인용이며, 임의의 IP 기록을 만들지 않습니다.

    const search = document.getElementById("search");
    const date = document.getElementById("date");

    function filterNotice() {
      document.getElementById("rows").innerHTML =
        '<tr><td colspan="4" class="empty">' +
        '실제 검색을 사용하려면 기존 IP 기록 데이터와 연결해야 합니다.' +
        '</td></tr>';
    }

    search.addEventListener("input", filterNotice);
    date.addEventListener("change", filterNotice);

    document.getElementById("reset").addEventListener("click", () => {
      search.value = "";
      date.value = "";
      filterNotice();
    });
  </script>
</body>
</html>
