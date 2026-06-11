"""
app.py — マジカル・シー・プランナー（モバイルファースト）

入力は「日付」と「ぜったい乗りたい」だけ。
天気・祝日・イベントは自動取得し、必須アトラクションを
いちばん空いている時間に配置したフルデイプランを生成する。
"""
import os
import sqlite3

import streamlit as st

from engine.auto_context import build_auto_context
from engine.planner import build_full_plan
from engine.similarity import (
    build_target_features,
    extract_similar_days,
    predict_wait_times,
)
from ui.graphs import render_wait_graphs
from ui.input_panel import render_inputs
from ui.style import hero, inject_css
from ui.timeline import render_plan

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tds.db")

st.set_page_config(
    page_title="マジカル・シー・プランナー",
    page_icon="🏰",
    layout="centered",
    initial_sidebar_state="collapsed",
)

inject_css()
hero()

if not os.path.exists(DB_PATH):
    # クラウドデプロイ等の初回起動時は DB を自動生成する（冪等スクリプト）
    with st.spinner("はじめての起動… 魔法の本を準備しています 📖✨"):
        import sys
        sys.path.insert(
            0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
        )
        import generate_dummy_data
        generate_dummy_data.main()

_WEATHER_ICON = {"晴": "☀️", "曇": "☁️", "雨": "🌧️", "雪": "⛄"}


@st.cache_data(ttl=3600, show_spinner=False)
def _plan_pipeline(target_date: str, selected: tuple, start_hour: int, end_hour: int):
    ctx = build_auto_context(target_date)
    conn = sqlite3.connect(DB_PATH)
    target = build_target_features(
        target_date=target_date,
        is_holiday=ctx["is_holiday"],
        event_name=ctx["event_name"],
        weather=ctx["weather"],
        temp_max=ctx["temp_max"],
        temp_min=ctx["temp_min"],
    )
    similar = extract_similar_days(conn, target, top_n=10)
    waits = predict_wait_times(conn, similar)
    plan = build_full_plan(conn, list(selected), waits, start_hour, end_hour)
    conn.close()
    return ctx, similar, waits, plan


cond = render_inputs()
if cond:
    st.session_state["cond"] = cond

cond = st.session_state.get("cond")
if cond is None:
    st.markdown(
        '<p style="text-align:center; color:#cfc6ff;">'
        "🌟 日付とアトラクションをえらんだら、ボタンをタップ！</p>",
        unsafe_allow_html=True,
    )
    st.stop()

with st.spinner("🪄 魔法をかけています… 過去1年の記録から未来をよんでいます ✨"):
    try:
        ctx, similar, waits, plan = _plan_pipeline(
            cond["target_date"],
            tuple(cond["selected_attractions"]),
            cond["start_hour"],
            cond["end_hour"],
        )
    except Exception as e:
        st.error(f"プランが作れませんでした… 滞在時間をのばすか、アトラクションをへらしてみてね（{e}）")
        st.stop()

# ── 自動取得した当日情報 ──────────────────────────────────────────
wx_icon = _WEATHER_ICON.get(ctx["weather"], "🌤️")
wx_note = "予報" if ctx["weather_source"] == "forecast" else "平年なみ"
chips = [
    f"{wx_icon} {ctx['weather']}（{wx_note}）",
    f"🌡️ {ctx['temp_max']:.0f}℃ / {ctx['temp_min']:.0f}℃",
]
if ctx["is_holiday"]:
    chips.append("🎌 祝日・おやすみ期間")
if ctx["event_name"]:
    chips.append(f"🎉 {ctx['event_name'].replace('2024', '').replace('2025', '')}")
else:
    chips.append("🕊️ 通常期")

st.markdown(
    f'<h3 style="margin-bottom:.2rem;">🗓️ {cond["target_date"]} のプラン</h3>'
    '<div class="chip-row">'
    + "".join(f'<div class="chip">{c}</div>' for c in chips)
    + "</div>",
    unsafe_allow_html=True,
)
st.caption("☝️ 天気・イベント・祝日は自動でしらべました")

# ── プラン本体 ────────────────────────────────────────────────────
render_plan(plan)

# ── 詳しい人向けの根拠データ ──────────────────────────────────────
with st.expander("📈 待ち時間のうごきをみる"):
    render_wait_graphs(waits, cond["selected_attractions"])

with st.expander("🔍 予測のもとにした「にている日」"):
    st.dataframe(
        similar[["date", "is_holiday", "event_name", "weather", "similarity_score"]]
        .rename(columns={
            "date": "日付", "is_holiday": "祝日", "event_name": "イベント",
            "weather": "天気", "similarity_score": "にてる度",
        }),
        use_container_width=True,
        hide_index=True,
    )
