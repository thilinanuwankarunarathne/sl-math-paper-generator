# -*- coding: utf-8 -*-
"""
app.py  -  ගණිත ප්‍රශ්න පත්‍ර උත්පාදක පද්ධතිය (Math Exam Paper Generator)
Run:  streamlit run app.py
"""
import base64
import html
import json
import random
import sqlite3
import threading

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from database_setup import DB_PATH, DIFF_SI, DIFFS, SYLLABUS, init_db
from media import render

st.set_page_config(page_title="ගණිත ප්‍රශ්න පත්‍ර උත්පාදකය", page_icon="📐", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Sinhala:wght@400;600;700&display=swap');
html, body, [class*="css"], .stMarkdown { font-family: 'Noto Sans Sinhala', sans-serif; }
.paper-head { text-align:center; border-bottom:2px solid #222; padding-bottom:10px; margin-bottom:18px; }
.marks-badge { text-align:right; font-weight:700; white-space:nowrap; }
@page { size: A4; margin: 15mm; }
@media print {
  [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"],
  [data-baseweb="tab-list"], .stButton, iframe, .no-print, footer { display:none !important; }
  .block-container { padding:0 !important; max-width:100% !important; }
}
</style>
""", unsafe_allow_html=True)

if not DB_PATH.exists():
    init_db(force=False, per_lesson=100, append=True)


# ---------------------------------------------------------------------------
# Fast 1M-Row Ready Data Access
# ---------------------------------------------------------------------------
def get_db_count():
    with sqlite3.connect(DB_PATH) as con:
        return con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]


def load_questions_sampled(grade, lessons, diffs, per_lesson_limit=120):
    """Samples directly in SQLite per lesson so 1,000,000+ row DBs stay instant."""
    if not lessons or not diffs:
        return pd.DataFrame()
    frames = []
    d_placeholders = ",".join("?" * len(diffs))
    sql = (f"SELECT * FROM questions WHERE grade=? AND lesson=? "
           f"AND difficulty IN ({d_placeholders}) ORDER BY RANDOM() LIMIT ?")
    with sqlite3.connect(DB_PATH) as con:
        for les in lessons:
            df_les = pd.read_sql_query(sql, con, params=[grade, les, *diffs, per_lesson_limit])
            if not df_les.empty:
                frames.append(df_les)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def pick_questions(df, target, seed):
    rng = random.Random(seed)
    pools = [g.sample(frac=1, random_state=rng.randint(0, 10**6)).to_dict("records")
             for _, g in df.groupby("lesson")]
    rng.shuffle(pools)
    chosen, left, total = [], [], 0
    while any(pools) and total < target:
        for p in pools:
            if p:
                item = p.pop()
                if total + item["marks"] <= target:
                    chosen.append(item)
                    total += item["marks"]
                else:
                    left.append(item)
            if total >= target:
                break
    for item in sorted(left, key=lambda i: -i["marks"]):
        if total + item["marks"] <= target:
            chosen.append(item)
            total += item["marks"]
    return chosen, total


def pick_long(df, n, seed):
    rng = random.Random(seed)
    if df.empty:
        return []
    pools = [g.sample(frac=1, random_state=rng.randint(0, 10**6)).to_dict("records")
             for _, g in df.groupby("lesson")]
    rng.shuffle(pools)
    chosen = []
    while len(chosen) < n and any(pools):
        for p in pools:
            if p and len(chosen) < n:
                chosen.append(p.pop())
    return chosen


# ---------------------------------------------------------------------------
# Figures & Isolated A4 Print HTML Builder
# ---------------------------------------------------------------------------
_FIG_LOCK = threading.Lock()


@st.cache_data(show_spinner=False, max_entries=1500)
def figure_bytes(spec_json):
    spec = json.loads(spec_json)
    with _FIG_LOCK:
        return render(spec["kind"], spec["p"])


def render_question(no, q, with_marks=True):
    c1, c2 = st.columns([11, 1])
    c1.markdown(f"**{no}.** {q['content']}")
    spec = q.get("image_spec")
    if isinstance(spec, str) and spec:
        try:
            c1.image(figure_bytes(spec), width=360)
        except Exception as e:
            c1.warning(f"⚠️ රූපය ඇඳීමට නොහැකි විය: {e}")
    if with_marks:
        c2.markdown(f"<div class='marks-badge'>({q['marks']})</div>", unsafe_allow_html=True)


def build_printable_html(paper, include_answers=False, answer_lines=True):
    """Builds a standalone A4 HTML document with KaTeX so ONLY the paper prints."""
    school_n, exam_n, dur = paper["head"]
    total = paper["total"]
    grade = paper["grade"]
    title_prefix = "පිළිතුරු පත්‍රය (Marking Scheme) - " if include_answers else ""

    body_parts = []
    no = 0
    for sec_title, qs, sec_total in paper["sections"]:
        if sec_title and qs:
            sec_lbl = f"{html.escape(sec_title)} (ලකුණු {sec_total})" if not include_answers else html.escape(sec_title)
            body_parts.append(f"<h3 class='sec-title'>{sec_lbl}</h3>")
        for q in qs:
            no += 1
            img_html = ""
            spec = q.get("image_spec")
            if isinstance(spec, str) and spec:
                try:
                    b64 = base64.b64encode(figure_bytes(spec)).decode("ascii")
                    img_html = f"<div class='q-fig'><img src='data:image/png;base64,{b64}'/></div>"
                except Exception:
                    pass

            ans_html = ""
            if include_answers:
                try:
                    scheme = json.loads(q["marking_scheme"])
                    steps_li = "".join(
                        f"<li>{s['step']} <span class='step-m'>[{s['marks']} ලකුණු]</span></li>"
                        for s in scheme.get("steps", [])
                    )
                    ans_html = f"<div class='ans-box'><b>පිළිතුර / ලකුණු දීමේ පියවර:</b><ol>{steps_li}</ol></div>"
                except Exception:
                    pass
            elif answer_lines:
                lines_cnt = 3 if q["marks"] <= 4 else 6
                dots = "".join("<div class='dot-line'></div>" for _ in range(lines_cnt))
                ans_html = f"<div class='work-space'>{dots}</div>"

            body_parts.append(f"""
            <div class='q-block'>
              <div class='q-row'>
                <div class='q-text'><b>{no}.</b> {q['content']}</div>
                <div class='q-marks'>({q['marks']})</div>
              </div>
              {img_html}
              {ans_html}
            </div>
            """)

    return f"""<!DOCTYPE html>
<html lang="si">
<head>
<meta charset="utf-8"/>
<title>{html.escape(exam_n)} - {grade} ශ්‍රේණිය</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body, {{delimiters: [{{left: '$$', right: '$$', display: true}}, {{left: '$', right: '$', display: false}}]}});"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Sinhala:wght@400;600;700&display=swap');
  @page {{ size: A4 portrait; margin: 15mm; }}
  body {{ font-family: 'Noto Sans Sinhala', sans-serif; color: #000; margin: 0; padding: 0; font-size: 11pt; line-height: 1.5; }}
  .paper-header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 8px; margin-bottom: 14px; }}
  .paper-header h2 {{ margin: 0; font-size: 15pt; }}
  .paper-header h3 {{ margin: 4px 0; font-size: 13pt; }}
  .meta-bar {{ display: flex; justify-content: space-between; font-weight: 700; margin-top: 6px; font-size: 10.5pt; }}
  .sec-title {{ background: #f2f2f2; padding: 5px 10px; border-left: 4px solid #000; margin: 16px 0 10px 0; font-size: 11.5pt; }}
  .q-block {{ page-break-inside: avoid; border-bottom: 1px solid #ddd; padding: 10px 0; }}
  .q-row {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }}
  .q-text {{ flex: 1; }}
  .q-marks {{ font-weight: 700; white-space: nowrap; }}
  .q-fig img {{ max-width: 260px; max-height: 190px; margin-top: 6px; }}
  .dot-line {{ border-bottom: 1px dotted #888; height: 22px; width: 100%; }}
  .ans-box {{ background: #f9f9f9; border-left: 3px solid #2b6cb0; padding: 6px 12px; margin-top: 8px; font-size: 10pt; }}
  .step-m {{ font-weight: 700; color: #1a365d; }}
</style>
</head>
<body>
  <div class="paper-header">
    {f"<h2>{html.escape(school_n)}</h2>" if school_n else ""}
    <h3>{title_prefix}{html.escape(exam_n)} - {grade} ශ්‍රේණිය</h3>
    <div class="meta-bar">
      <span>කාලය: {html.escape(dur)}</span>
      <span>මුළු ලකුණු: {total}</span>
    </div>
  </div>
  {''.join(body_parts)}
</body>
</html>"""


def render_print_toolbar(paper, include_answers=False, show_lines=True, key_suffix="q"):
    html_doc = build_printable_html(paper, include_answers=include_answers, answer_lines=show_lines)
    b64_doc = base64.b64encode(html_doc.encode("utf-8")).decode("ascii")
    btn_label = "🖨️ පිළිතුරු පත්‍රය පමණක් මුද්‍රණය කරන්න (Print Marking Scheme)" if include_answers else "🖨️ ප්‍රශ්න පත්‍රය පමණක් මුද්‍රණය කරන්න (Print Paper Only)"
    components.html(f"""
    <div style="display:flex; gap:10px; align-items:center;">
      <button onclick="printIsolated()" style="background:#1a56db;color:white;border:none;padding:9px 18px;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer;">
        {btn_label}
      </button>
    </div>
    <script>
    function printIsolated() {{
      const htmlBytes = Uint8Array.from(atob("{b64_doc}"), c => c.charCodeAt(0));
      const htmlStr = new TextDecoder("utf-8").decode(htmlBytes);
      const win = window.open("", "_blank", "width=900,height=800");
      win.document.open();
      win.document.write(htmlStr);
      win.document.close();
      win.onload = function() {{
        setTimeout(function() {{ win.focus(); win.print(); }}, 600);
      }};
    }}
    </script>
    """, height=52)


# ---------------------------------------------------------------------------
# Sidebar - Configuration
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ සැකසුම්")
    st.caption(f"📊 දත්ත සමුදායේ මුළු ප්‍රශ්න: **{get_db_count():,}**")
    if st.button("➕ අලුත් ප්‍රශ්න 8,000+ එක් කරන්න", use_container_width=True):
        with st.spinner("නව තාර්කික ප්‍රශ්න ජනනය කරමින්..."):
            b, a = init_db(force=False, per_lesson=150, append=True)
            st.cache_data.clear()
        st.success(f"අලුත් ප්‍රශ්න {a - b:,} ක් එක් කරන ලදී! (මුළු: {a:,})")
        st.rerun()

    st.divider()
    grade = st.selectbox("ශ්‍රේණිය", [10, 11], format_func=lambda g: f"{g} ශ්‍රේණිය")
    all_lessons = SYLLABUS[grade]
    pick_all = st.checkbox("සියලු පාඩම් තෝරන්න", value=True, key=f"all_{grade}")
    lessons = st.multiselect("පාඩම් (බහුවිධ තේරීම)", all_lessons,
                             default=all_lessons if pick_all else [], key=f"les_{grade}_{pick_all}")
    diffs = st.multiselect("දුෂ්කරතා මට්ටම", DIFFS, default=DIFFS, format_func=lambda d: DIFF_SI[d])
    mode = st.radio("ප්‍රශ්න පත්‍ර ආකෘතිය", ["ව්‍යුහගත (A + B කොටස්)", "සරල (ලකුණු අනුව)"])
    if mode.startswith("ව්‍යුහගත"):
        targetA = st.number_input("A කොටස - කෙටි ප්‍රශ්න ලකුණු", min_value=10, max_value=100, value=40, step=5)
        nB = st.number_input("B කොටස - දිගු ප්‍රශ්න ගණන (ලකුණු 10 බැගින්)", min_value=1, max_value=10, value=4)
    else:
        target = st.number_input("ඉලක්කගත මුළු ලකුණු", min_value=5, max_value=200, value=50, step=5)
    show_lines = st.checkbox("පිළිතුරු ලිවීමට තිත් ඉරි (Dotted Lines) එක් කරන්න", value=True)
    st.divider()
    school = st.text_input("පාසල / පන්තිය", "උසස් ගණිත අධ්‍යාපන ආයතනය")
    exam_name = st.text_input("විභාග නාමය", "ගණිතය - පෙරහුරු පරීක්ෂණය")
    duration = st.text_input("කාලය", "පැය 2")
    go = st.button("📄 ප්‍රශ්න පත්‍රය සාදන්න", type="primary", use_container_width=True)

if go:
    pool = load_questions_sampled(grade, tuple(lessons), tuple(diffs))
    order = {l: i for i, l in enumerate(all_lessons)}
    sortkey = lambda q: (DIFFS.index(q["difficulty"]), order.get(q["lesson"], 99))
    seed = random.randint(0, 10**6)
    if pool.empty:
        st.session_state["paper"] = {"empty": True}
    elif mode.startswith("ව්‍යුහගත"):
        is_long = pool["question_type"] == "දිගු ප්‍රශ්නය"
        a_qs, a_tot = pick_questions(pool[~is_long], targetA, seed)
        a_qs.sort(key=sortkey)
        b_qs = pick_long(pool[is_long], nB, seed)
        b_qs.sort(key=sortkey)
        b_tot = sum(q["marks"] for q in b_qs)
        warn = []
        if a_tot < targetA:
            warn.append(f"A කොටසට ඉලක්කගත ලකුණු {targetA} සඳහා ප්‍රමාණවත් ප්‍රශ්න නොමැත (ලැබුණු: {a_tot}).")
        if len(b_qs) < nB:
            warn.append(f"B කොටසට දිගු ප්‍රශ්න {nB} ක් සඳහා ප්‍රමාණවත් නොමැත (ලැබුණු: {len(b_qs)}).")
        st.session_state["paper"] = dict(
            sections=[("A කොටස - කෙටි ප්‍රශ්න (සියල්ලටම පිළිතුරු සපයන්න)", a_qs, a_tot),
                      ("B කොටස - ව්‍යුහගත රචනා ප්‍රශ්න", b_qs, b_tot)],
            total=a_tot + b_tot, grade=grade, warn=warn, head=(school, exam_name, duration))
    else:
        chosen, total = pick_questions(pool, target, seed)
        chosen.sort(key=sortkey)
        warn = ([f"ඉලක්කගත ලකුණු {target} සඳහා ප්‍රමාණවත් ප්‍රශ්න නොමැත (ලැබුණු: {total})."]
                if total < target else [])
        st.session_state["paper"] = dict(sections=[("", chosen, total)], total=total, grade=grade,
                                         warn=warn, head=(school, exam_name, duration))

# ---------------------------------------------------------------------------
# Main Area
# ---------------------------------------------------------------------------
st.title("📐 ගණිත ප්‍රශ්න පත්‍ර උත්පාදක පද්ධතිය")
paper = st.session_state.get("paper")

if not paper:
    st.info("වම් පස සැකසුම් තෝරා **ප්‍රශ්න පත්‍රය සාදන්න** බොත්තම ඔබන්න.")
elif paper.get("empty") or not any(s[1] for s in paper["sections"]):
    st.warning("තෝරාගත් පාඩම් / දුෂ්කරතා මට්ටම් සඳහා ප්‍රශ්න හමු නොවීය.")
else:
    for w in paper["warn"]:
        st.warning(w)
    total = paper["total"]
    school_n, exam_n, dur = paper["head"]
    tab_q, tab_a = st.tabs(["📝 ප්‍රශ්න පත්‍රය", "✅ පිළිතුරු පත්‍රය (Marking Scheme)"])

    with tab_q:
        render_print_toolbar(paper, include_answers=False, show_lines=show_lines, key_suffix="q")
        st.markdown(f"<div class='paper-head'><h2>{school_n}</h2><h3>{exam_n} - {paper['grade']} ශ්‍රේණිය</h3>"
                    f"<b>කාලය: {dur} &nbsp;|&nbsp; මුළු ලකුණු: {total}</b></div>", unsafe_allow_html=True)
        no = 0
        for title, qs, sec_total in paper["sections"]:
            if title and qs:
                st.markdown(f"### {title} &nbsp; <small>(ලකුණු {sec_total})</small>", unsafe_allow_html=True)
            for q in qs:
                no += 1
                render_question(no, q)
                st.markdown("---")

    with tab_a:
        render_print_toolbar(paper, include_answers=True, show_lines=False, key_suffix="a")
        st.markdown(f"<div class='paper-head'><h3>පිළිතුරු පත්‍රය - {exam_n}</h3>"
                    f"<b>මුළු ලකුණු: {total}</b></div>", unsafe_allow_html=True)
        no = 0
        for title, qs, sec_total in paper["sections"]:
            if title and qs:
                st.markdown(f"### {title}")
            for q in qs:
                no += 1
                render_question(no, q)
                try:
                    scheme = json.loads(q["marking_scheme"])
                    st.markdown("**පිළිතුර / ලකුණු දීමේ පියවර:**")
                    for n, s in enumerate(scheme["steps"], 1):
                        st.markdown(f"{n}. {s['step']} &nbsp; **[{s['marks']} ලකුණු]**")
                    st.markdown(f"**මුළු ලකුණු: {scheme.get('total', q['marks'])}**")
                except (json.JSONDecodeError, KeyError, TypeError):
                    st.error("මෙම ප්‍රශ්නයේ ලකුණු දීමේ පටිපාටිය කියවිය නොහැක.")
                st.markdown("---")