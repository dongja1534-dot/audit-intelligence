from flask import Flask, request
import sqlite3
import csv
import math

app = Flask(__name__)

DB_FILE = "audit.db"
REPORT_FILE = "fy2025_report_companies.csv"

PER_PAGE = 50


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# DART 사업보고서 접수정보 찾기
def get_report_info(corp_code):

    try:
        with open(
            REPORT_FILE,
            "r",
            encoding="utf-8-sig"
        ) as f:

            reader = csv.DictReader(f)

            for row in reader:

                if row["corp_code"] == corp_code:

                    return {
                        "report_nm": row["report_nm"],
                        "rcept_no": row["rcept_no"],
                        "rcept_dt": row["rcept_dt"]
                    }

    except:
        pass

    return None


@app.route("/")
def home():

    search = request.args.get("search", "").strip()
    year = request.args.get("year", "2025")
    auditor_filter = request.args.get("auditor", "")
    opinion_filter = request.args.get("opinion", "")
    emphasis_filter = request.args.get("emphasis", "")
    kam_filter = request.args.get("kam", "")
    kam_keyword = request.args.get("kam_keyword", "").strip()

    # 현재 페이지
    try:
        page = int(request.args.get("page", "1"))
    except:
        page = 1

    if page < 1:
        page = 1

    conn = get_db()
    cur = conn.cursor()

    # -------------------------
    # 검색 조건 만들기
    # -------------------------

    where_sql = """
        FROM audit_data
        WHERE bsns_year = ?
    """

    params = [year]

    if auditor_filter:
        where_sql += " AND auditor = ?"
        params.append(auditor_filter)

    if opinion_filter:
        where_sql += " AND opinion = ?"
        params.append(opinion_filter)

    if emphasis_filter == "yes":

        where_sql += """
            AND emphasis IS NOT NULL
            AND emphasis != ''
            AND emphasis != '해당사항 없음'
        """

    elif emphasis_filter == "no":

        where_sql += """
            AND (
                emphasis IS NULL
                OR emphasis = ''
                OR emphasis = '해당사항 없음'
            )
        """

    if kam_filter == "yes":
        where_sql += " AND kam_count > 0"

    elif kam_filter == "no":
        where_sql += """
            AND (
                kam_count IS NULL
                OR kam_count = 0
            )
        """

    if kam_keyword:
        where_sql += " AND kam LIKE ?"
        params.append(f"%{kam_keyword}%")

    if search:

        where_sql += """
            AND (
                corp_name LIKE ?
                OR stock_code LIKE ?
            )
        """

        params.append(f"%{search}%")
        params.append(f"%{search}%")

    # -------------------------
    # 검색 결과 전체 개수
    # -------------------------

    count_query = "SELECT COUNT(*) " + where_sql

    cur.execute(count_query, params)

    total_results = cur.fetchone()[0]

    total_pages = max(
        1,
        math.ceil(total_results / PER_PAGE)
    )

    if page > total_pages:
        page = total_pages

    offset = (page - 1) * PER_PAGE

    # -------------------------
    # 현재 페이지 50개만 가져오기
    # -------------------------

    query = """
        SELECT
            corp_code,
            corp_name,
            stock_code,
            bsns_year,
            auditor,
            opinion,
            emphasis,
            kam_count
    """

    query += where_sql

    query += """
        ORDER BY corp_name
        LIMIT ?
        OFFSET ?
    """

    page_params = params.copy()
    page_params.append(PER_PAGE)
    page_params.append(offset)

    cur.execute(query, page_params)

    results = cur.fetchall()

    # -------------------------
    # 감사인 목록
    # -------------------------

    cur.execute("""
        SELECT DISTINCT auditor
        FROM audit_data
        WHERE bsns_year = ?
          AND auditor IS NOT NULL
          AND auditor != ''
          AND auditor != '-'
        ORDER BY auditor
    """, (year,))

    auditors = cur.fetchall()

    # -------------------------
    # 감사의견 목록
    # -------------------------

    cur.execute("""
        SELECT DISTINCT opinion
        FROM audit_data
        WHERE bsns_year = ?
          AND opinion IS NOT NULL
          AND opinion != ''
        ORDER BY opinion
    """, (year,))

    opinions = cur.fetchall()

    conn.close()

    # -------------------------
    # 감사인 선택창
    # -------------------------

    auditor_options = '<option value="">감사인 전체</option>'

    for row in auditors:

        auditor_name = row["auditor"]

        selected = (
            "selected"
            if auditor_filter == auditor_name
            else ""
        )

        auditor_options += f"""
        <option value="{auditor_name}" {selected}>
            {auditor_name}
        </option>
        """

    # -------------------------
    # 감사의견 선택창
    # -------------------------

    opinion_options = '<option value="">감사의견 전체</option>'

    for row in opinions:

        opinion_name = row["opinion"]

        selected = (
            "selected"
            if opinion_filter == opinion_name
            else ""
        )

        opinion_options += f"""
        <option value="{opinion_name}" {selected}>
            {opinion_name}
        </option>
        """

    # -------------------------
    # 회사 목록
    # -------------------------

    rows_html = ""

    for item in results:

        auditor = item["auditor"] or "자료 없음"
        opinion = item["opinion"] or "자료 없음"

        emphasis = item["emphasis"] or ""

        if (
            emphasis == ""
            or emphasis == "해당사항 없음"
        ):
            emphasis_display = "없음"
        else:
            emphasis_display = "있음"

        kam_count = item["kam_count"] or 0

        kam_display = (
            kam_count
            if kam_count > 0
            else "-"
        )

        rows_html += f"""
        <tr>

            <td>
                <a href="/company/{item["corp_code"]}?year={item["bsns_year"]}">
                    {item["corp_name"]}
                </a>
            </td>

            <td>{item["stock_code"]}</td>
            <td>{item["bsns_year"]}</td>
            <td>{auditor}</td>
            <td>{opinion}</td>
            <td>{emphasis_display}</td>
            <td>{kam_display}</td>

        </tr>
        """

    # -------------------------
    # 페이지 버튼
    # -------------------------

    def make_page_url(target_page):

        return (
            "/?"
            + "year=" + year
            + "&auditor=" + auditor_filter
            + "&opinion=" + opinion_filter
            + "&emphasis=" + emphasis_filter
            + "&kam=" + kam_filter
            + "&kam_keyword=" + kam_keyword
            + "&search=" + search
            + "&page=" + str(target_page)
)
    pagination_html = ""

    if total_pages > 1:

        # 이전 버튼
        if page > 1:

            pagination_html += f"""
            <a class="page-button"
               href="{make_page_url(page - 1)}">
               ← 이전
            </a>
            """

        # 현재 페이지 주변 번호만 표시
        start_page = max(1, page - 3)
        end_page = min(total_pages, page + 3)

        if start_page > 1:

            pagination_html += f"""
            <a class="page-button"
               href="{make_page_url(1)}">
               1
            </a>
            """

            if start_page > 2:
                pagination_html += """
                <span class="dots">...</span>
                """

        for p in range(
            start_page,
            end_page + 1
        ):

            if p == page:

                pagination_html += f"""
                <span class="page-button active">
                    {p}
                </span>
                """

            else:

                pagination_html += f"""
                <a class="page-button"
                   href="{make_page_url(p)}">
                   {p}
                </a>
                """

        if end_page < total_pages:

            if end_page < total_pages - 1:
                pagination_html += """
                <span class="dots">...</span>
                """

            pagination_html += f"""
            <a class="page-button"
               href="{make_page_url(total_pages)}">
               {total_pages}
            </a>
            """

        # 다음 버튼
        if page < total_pages:

            pagination_html += f"""
            <a class="page-button"
               href="{make_page_url(page + 1)}">
               다음 →
            </a>
            """

    # -------------------------
    # 메인 화면
    # -------------------------

    return f"""
<!DOCTYPE html>

<html lang="ko">

<head>

<meta charset="UTF-8">

<title>Audit Viewer</title>

<style>

body {{
    font-family: Arial, sans-serif;
    margin: 0;
    background: white;
    color: #222;
}}

.container {{
    width: 1250px;
    margin: 50px auto;
}}

h1 {{
    color: #1837d1;
    margin-bottom: 5px;
}}

.subtitle {{
    color: #666;
    margin-bottom: 30px;
}}

.filters {{
    background: #f8f9fb;
    border: 1px solid #ddd;
    padding: 20px;
    margin-bottom: 25px;
}}

.filter-row {{
    margin-bottom: 10px;
}}

select,
input {{
    padding: 11px;
    border: 1px solid #ccc;
    border-radius: 5px;
    margin-right: 8px;
}}

select {{
    width: 180px;
}}

input {{
    width: 350px;
}}

button {{
    padding: 11px 25px;
    background: #1837d1;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
}}

table {{
    width: 100%;
    border-collapse: collapse;
}}

th {{
    text-align: left;
    background: #f7f7f7;
    padding: 14px;
}}

td {{
    padding: 14px;
    border-bottom: 1px solid #eee;
}}

a {{
    color: #1837d1;
    text-decoration: none;
    font-weight: bold;
}}

.pagination {{
    text-align: center;
    margin-top: 30px;
    margin-bottom: 50px;
}}

.page-button {{
    display: inline-block;
    padding: 9px 13px;
    margin: 3px;
    border: 1px solid #ddd;
    border-radius: 5px;
    color: #333;
    background: white;
    text-decoration: none;
}}

.page-button:hover {{
    background: #f2f4ff;
}}

.page-button.active {{
    background: #1837d1;
    color: white;
    border-color: #1837d1;
}}

.dots {{
    margin: 0 5px;
    color: #888;
}}

.result-info {{
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

.page-info {{
    color: #777;
    font-size: 14px;
}}

</style>

</head>

<body>

<div class="container">

<h1>Audit Intelligence</h1>

<div class="subtitle">
OpenDART 기반 상장사 감사정보 검색·분석 도구
<br>
감사인 · 감사의견 · 강조사항 · 핵심감사사항(KAM)을 조건별로 조회할 수 있습니다.
</div>


<div class="filters">

<form method="GET">

<div class="filter-row">

<select name="year">

<option value="2025"
{"selected" if year == "2025" else ""}>
FY2025
</option>

<option value="2024"
{"selected" if year == "2024" else ""}>
FY2024
</option>

</select>


<select name="auditor">
{auditor_options}
</select>


<select name="opinion">
{opinion_options}
</select>

</div>


<div class="filter-row">

<select name="emphasis">

<option value="">
강조사항 전체
</option>

<option value="yes"
{"selected" if emphasis_filter == "yes" else ""}>
강조사항 있음
</option>

<option value="no"
{"selected" if emphasis_filter == "no" else ""}>
강조사항 없음
</option>

</select>


<select name="kam">

<option value="">
KAM 전체
</option>

<option value="yes"
{"selected" if kam_filter == "yes" else ""}>
KAM 있음
</option>

<option value="no"
{"selected" if kam_filter == "no" else ""}>
KAM 없음
</option>

</select>

<input
type="text"
name="kam_keyword"
placeholder="KAM 키워드 검색"
value="{kam_keyword}"
>

<input
type="text"
name="search"
placeholder="회사명 또는 종목코드 검색"
value="{search}"
>


<button type="submit">
검색
</button>

</div>

</form>

</div>


<div class="result-info">

<h3>
FY{year} 검색 결과: {total_results:,}건
</h3>

<div class="page-info">
{page} / {total_pages} 페이지
</div>

</div>


<table>

<tr>
<th>회사명</th>
<th>종목코드</th>
<th>사업연도</th>
<th>감사인</th>
<th>감사의견</th>
<th>강조사항</th>
<th>KAM</th>
</tr>

{rows_html}

</table>


<div class="pagination">
{pagination_html}
</div>


</div>

</body>

</html>
"""


@app.route("/company/<corp_code>")
def company_detail(corp_code):

    year = request.args.get("year", "2025")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM audit_data
        WHERE corp_code = ?
          AND bsns_year = ?
        LIMIT 1
    """, (
        corp_code,
        year
    ))

    item = cur.fetchone()

    conn.close()

    if not item:
        return "자료를 찾을 수 없습니다."

    auditor = item["auditor"] or "자료 없음"
    opinion = item["opinion"] or "자료 없음"
    emphasis = item["emphasis"] or "해당사항 없음"
    kam = item["kam"] or "핵심감사사항 없음"

    kam_html = kam.replace("\n", "<br>")

    # DART 공시정보 찾기
    report = get_report_info(corp_code)

    report_html = ""

    if report:

        rcept_no = report["rcept_no"]

        dart_url = (
            "https://dart.fss.or.kr/"
            "dsaf001/main.do?rcpNo="
            + rcept_no
        )

        report_html = f"""
        <tr>
            <th>보고서명</th>
            <td>{report["report_nm"]}</td>
        </tr>

        <tr>
            <th>DART 접수일</th>
            <td>{report["rcept_dt"]}</td>
        </tr>

        <tr>
            <th>DART 접수번호</th>
            <td>{rcept_no}</td>
        </tr>

        <tr>
            <th>DART 원문</th>

            <td>
                <a
                    class="dart-button"
                    href="{dart_url}"
                    target="_blank"
                >
                    DART 원문 보기
                </a>
            </td>
        </tr>
        """

    return f"""
<!DOCTYPE html>

<html lang="ko">

<head>

<meta charset="UTF-8">

<title>{item["corp_name"]}</title>

<style>

body {{
    font-family: Arial, sans-serif;
    margin: 0;
    background: #f7f8fa;
    color: #222;
}}

.container {{
    width: 1000px;
    margin: 50px auto;
}}

.back {{
    color: #1837d1;
    text-decoration: none;
    display: inline-block;
    margin-bottom: 20px;
}}

.card {{
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 30px;
    margin-bottom: 20px;
}}

h1 {{
    margin-top: 0;
    color: #1837d1;
}}

table {{
    width: 100%;
    border-collapse: collapse;
}}

th {{
    width: 190px;
    text-align: left;
    background: #f7f7f7;
    padding: 13px;
    border-bottom: 1px solid #ddd;
}}

td {{
    padding: 13px;
    border-bottom: 1px solid #eee;
}}

.kam {{
    line-height: 1.8;
}}

.dart-button {{
    display: inline-block;
    padding: 9px 16px;
    background: #1837d1;
    color: white;
    text-decoration: none;
    border-radius: 5px;
    font-weight: bold;
}}

</style>

</head>

<body>

<div class="container">

<a href="/" class="back">
← 목록으로 돌아가기
</a>


<div class="card">

<h1>{item["corp_name"]}</h1>

<table>

<tr>
<th>종목코드</th>
<td>{item["stock_code"]}</td>
</tr>

<tr>
<th>사업연도</th>
<td>{item["bsns_year"]}</td>
</tr>

<tr>
<th>감사인</th>
<td>{auditor}</td>
</tr>

<tr>
<th>감사의견</th>
<td>{opinion}</td>
</tr>

<tr>
<th>강조사항</th>
<td>{emphasis}</td>
</tr>

<tr>
<th>KAM 개수</th>
<td>{item["kam_count"]}</td>
</tr>

<tr>
<th>DB 업데이트</th>
<td>{item["updated_at"]}</td>
</tr>

{report_html}

</table>

</div>


<div class="card">

<h2>핵심감사사항 KAM</h2>

<div class="kam">
{kam_html}
</div>

</div>

</div>

</body>

</html>
"""


if __name__ == "__main__":
    app.run(debug=True)