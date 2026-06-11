"""
app.py — Streamlit エントリーポイント

入力（サイドバー）→ 類似日抽出 → 待ち時間予測 → ルート最適化 → 可視化
"""
import os
import sqlite3

import streamlit as st

from engine.similarity import (
    build_target_features,
    extract_similar_days,
    predict_wait_times,
)
from engine.optimizer import optimize_route, RouteInfeasibleError
from ui.input_panel import render_input_panel
from ui.timeline import render_timeline
from ui.graphs import render_wait_graphs

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tds.db")

st.set_page_config(
    page_title="TDS 待ち時間予測 & ルート最適化",
    page_icon="🏰",
    layout="wide",
)

st.title("🏰 東京ディズニーシー 最適ルートプランナー")


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


@st.cache_data
def load_event_options() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT event_name FROM daily_master "
            "WHERE event_name IS NOT NULL ORDER BY event_name"
        ).fetchall()
    return [r[0] for r in rows]


if not os.path.exists(DB_PATH):
    # クラウドデプロイ等の初回起動時は DB を自動生成する（冪等スクリプト）
    with st.spinner("初回起動: ダミーデータベースを生成しています（数十秒）..."):
        import sys
        sys.path.insert(
            0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
        )
        import generate_dummy_data
        generate_dummy_data.main()

cond = render_input_panel(load_event_options())

if cond is None:
    st.info("⬅️ サイドバーで条件を指定して「プラン作成」を押してください")
    st.stop()

with st.spinner("類似日を抽出し、待ち時間を予測しています..."):
    conn = get_conn()
    target = build_target_features(
        target_date=cond["target_date"],
        is_holiday=cond["is_holiday"],
        event_name=cond["event_name"],
        weather=cond["weather"],
        temp_max=cond["temp_max"],
        temp_min=cond["temp_min"],
    )
    similar = extract_similar_days(conn, target, top_n=10)
    waits = predict_wait_times(conn, similar)

with st.spinner("最適ルートを計算しています（最大10秒）..."):
    try:
        schedule = optimize_route(
            conn,
            cond["selected_attractions"],
            waits,
            cond["start_hour"],
            cond["end_hour"],
        )
        infeasible_msg = None
    except RouteInfeasibleError as e:
        schedule = None
        infeasible_msg = str(e)

conn.close()

# ── 結果表示 ──────────────────────────────────────────────────────
st.subheader(f"📅 {cond['target_date']} のプラン")

if infeasible_msg:
    st.error(f"⚠️ {infeasible_msg}")
else:
    st.subheader("🗺️ 最適巡回タイムライン")
    render_timeline(schedule, cond["start_hour"], cond["end_hour"])

st.subheader("📈 待ち時間推移予測")
render_wait_graphs(waits, cond["selected_attractions"])

with st.expander("🔍 予測根拠：採用した類似日トップ10"):
    st.dataframe(
        similar[[
            "date", "day_of_week", "is_holiday", "event_name",
            "weather", "temp_max", "price_rank", "similarity_score",
        ]].rename(columns={
            "date": "日付", "day_of_week": "曜日(0=月)", "is_holiday": "祝日",
            "event_name": "イベント", "weather": "天気", "temp_max": "最高気温",
            "price_rank": "価格ランク", "similarity_score": "類似度",
        }),
        use_container_width=True,
        hide_index=True,
    )
