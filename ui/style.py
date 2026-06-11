"""
ui/style.py — 夢の国テーマ（モバイルファースト）

著作権フリー素材のみ使用:
  - Google Fonts「M PLUS Rounded 1c」（丸文字でパークらしい優しさ）
  - 絵文字・CSSグラデーション・きらめきアニメーション
"""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@500;700;800&display=swap');

html, body, .stApp, .stApp * {
    font-family: 'M PLUS Rounded 1c', 'Hiragino Maru Gothic ProN', sans-serif !important;
}

/* ── 夜空の背景 ─────────────────────────────────── */
.stApp {
    background:
        radial-gradient(1.4px 1.4px at 12% 18%, #fff 60%, transparent),
        radial-gradient(1.6px 1.6px at 78% 9%,  #ffe9a8 60%, transparent),
        radial-gradient(1.2px 1.2px at 33% 36%, #fff 60%, transparent),
        radial-gradient(1.8px 1.8px at 90% 42%, #cfe2ff 60%, transparent),
        radial-gradient(1.3px 1.3px at 55% 23%, #fff 60%, transparent),
        radial-gradient(1.5px 1.5px at 8% 60%,  #ffd9f2 60%, transparent),
        radial-gradient(1.2px 1.2px at 68% 70%, #fff 60%, transparent),
        radial-gradient(1.7px 1.7px at 42% 85%, #ffe9a8 60%, transparent),
        linear-gradient(180deg, #0c1445 0%, #20155e 35%, #3b1f7a 70%, #5a2a8f 100%);
    background-attachment: fixed;
}
header[data-testid="stHeader"] { background: transparent; }

h1, h2, h3, p, label, .stMarkdown, [data-testid="stWidgetLabel"] p {
    color: #fff7e6 !important;
}

/* ── ヒーロー ───────────────────────────────────── */
.hero { text-align: center; padding: 0.6rem 0 0.4rem; }
.hero .castle {
    font-size: 4.2rem; line-height: 1;
    filter: drop-shadow(0 0 18px rgba(255, 215, 130, .75));
    animation: floaty 4s ease-in-out infinite;
}
.hero h1 {
    font-size: 1.55rem; font-weight: 800; margin: .3rem 0 0;
    background: linear-gradient(90deg, #ffd86b, #ff9ecf, #9ecfff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero .sub { color: #cfc6ff !important; font-size: .85rem; margin-top: .15rem; }
@keyframes floaty { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-7px); } }

.sparkle { display: inline-block; animation: twinkle 1.8s ease-in-out infinite; }
.sparkle.s2 { animation-delay: .6s; }
.sparkle.s3 { animation-delay: 1.2s; }
@keyframes twinkle { 0%,100% { opacity: .35; transform: scale(.85);} 50% { opacity: 1; transform: scale(1.15);} }

/* ── 入力ウィジェット ────────────────────────────── */
div[data-baseweb="select"] > div, .stDateInput input, .stDateInput > div > div {
    background: rgba(255,255,255,.10) !important;
    border-color: rgba(255,216,107,.45) !important;
    color: #fff !important; border-radius: 14px !important;
}
span[data-baseweb="tag"] {
    background: linear-gradient(90deg, #7c5cff, #c08cff) !important;
    border-radius: 999px !important; color: #fff !important;
}

/* ── 魔法ボタン ─────────────────────────────────── */
.stButton > button {
    width: 100%;
    background: linear-gradient(90deg, #ffd86b 0%, #ffaad0 55%, #b08cff 100%);
    color: #2a1a05 !important; font-weight: 800 !important; font-size: 1.15rem !important;
    border: none; border-radius: 999px; padding: .85rem 1rem;
    box-shadow: 0 8px 26px rgba(255, 190, 120, .45);
    transition: transform .15s ease;
}
.stButton > button:hover { transform: scale(1.03); }

/* ── プランカード ───────────────────────────────── */
.walk-step {
    color: #bdb3e6; font-size: .8rem; text-align: center;
    padding: .15rem 0; letter-spacing: .05em;
}
.plan-card {
    display: flex; gap: .7rem; align-items: stretch;
    background: rgba(255,255,255,.10);
    border: 1px solid rgba(255,255,255,.16);
    border-radius: 18px; padding: .7rem .8rem; margin: .25rem 0;
    backdrop-filter: blur(6px);
}
.plan-card .clock {
    min-width: 3.2rem; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    font-weight: 800; font-size: 1.02rem; color: #ffe9a8;
}
.plan-card .clock small { font-weight: 500; font-size: .65rem; color: #cfc6ff; }
.plan-card .body { flex: 1; }
.plan-card .name { font-weight: 800; font-size: .98rem; color: #ffffff; }
.plan-card .meta { font-size: .78rem; color: #d9d2f5; margin-top: .15rem; }
.plan-card .badge {
    display: inline-block; font-size: .68rem; font-weight: 800;
    border-radius: 999px; padding: .1rem .6rem; margin-bottom: .2rem;
}
.plan-card.must  { border: 1.5px solid rgba(255,216,107,.85); box-shadow: 0 0 16px rgba(255,216,107,.25); }
.plan-card.must .badge { background: linear-gradient(90deg,#ffd86b,#ffb35c); color: #3a2500; }
.plan-card.recommend .badge { background: linear-gradient(90deg,#7be0d2,#8cb8ff); color: #00323a; }
.plan-card.recommend .reason { font-size: .76rem; color: #9fe8da; margin-top: .15rem; font-weight: 700; }
.plan-card.pause { background: rgba(255,255,255,.06); border-style: dashed; }
.plan-card.pause .name { color: #e8defc; font-weight: 700; }

/* ── 情報チップ ─────────────────────────────────── */
.chip-row { display: flex; flex-wrap: wrap; gap: .4rem; margin: .3rem 0 .5rem; }
.chip {
    background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.2);
    border-radius: 999px; padding: .25rem .75rem; font-size: .8rem; color: #fff;
}

/* ── メトリクス・エクスパンダー ───────────────────── */
[data-testid="stMetric"] {
    background: rgba(255,255,255,.08); border-radius: 16px; padding: .5rem .7rem;
}
[data-testid="stMetricValue"] { color: #ffe9a8 !important; }
[data-testid="stMetricLabel"] p { color: #cfc6ff !important; }
details, [data-testid="stExpander"] {
    background: rgba(255,255,255,.07); border-radius: 16px;
}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def hero() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="castle">🏰</div>
          <h1><span class="sparkle">✨</span> マジカル・シー・プランナー <span class="sparkle s2">✨</span></h1>
          <p class="sub">えらぶのは「いつ」と「なに」だけ。<span class="sparkle s3">🪄</span> あとは魔法におまかせ！</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
