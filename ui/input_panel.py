"""
ui/input_panel.py — ユーザー入力パネル（サイドバー）
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import streamlit as st

from engine.park_data import ATTRACTIONS, display_name

_WEATHER_OPTIONS = ["晴", "曇", "雨", "雪"]
_NORMAL_PERIOD = "（通常期）"


def render_input_panel(event_options: list[str]) -> dict[str, Any] | None:
    """
    サイドバーに入力 UI を描画し、「プラン作成」押下後に条件 dict を返す。
    未押下のときは None。
    """
    with st.sidebar:
        st.header("🎯 プラン条件")

        with st.form("plan_form"):
            target_date = st.date_input(
                "ターゲット日",
                value=date.today() + timedelta(days=30),
                min_value=date.today(),
            )

            st.subheader("当日の環境予測")
            weather = st.selectbox("天気", _WEATHER_OPTIONS)
            col1, col2 = st.columns(2)
            with col1:
                temp_max = st.number_input("最高気温(℃)", -5.0, 45.0, 25.0, 0.5)
            with col2:
                temp_min = st.number_input("最低気温(℃)", -10.0, 35.0, 18.0, 0.5)

            is_holiday = st.checkbox("祝日・長期休み期間", value=False)
            event_name = st.selectbox(
                "開催中イベント（類似イベントを選択）",
                [_NORMAL_PERIOD] + event_options,
            )

            st.subheader("希望アトラクション")
            selected = st.multiselect(
                "必ず体験したいもの（2件以上）",
                options=list(ATTRACTIONS.keys()),
                format_func=display_name,
                default=["soaring", "frozen", "tower_terror"],
            )

            st.subheader("滞在時間枠")
            start_hour, end_hour = st.select_slider(
                "入園 〜 退園",
                options=list(range(8, 23)),
                value=(9, 21),
                format_func=lambda h: f"{h}時",
            )

            submitted = st.form_submit_button("🚀 プラン作成", use_container_width=True)

    if not submitted:
        return None

    if len(selected) < 2:
        st.sidebar.error("アトラクションは2件以上選んでください")
        return None
    if temp_min > temp_max:
        st.sidebar.error("最低気温が最高気温を上回っています")
        return None

    return {
        "target_date": target_date.isoformat(),
        "weather": weather,
        "temp_max": float(temp_max),
        "temp_min": float(temp_min),
        "is_holiday": int(is_holiday),
        "event_name": None if event_name == _NORMAL_PERIOD else event_name,
        "selected_attractions": selected,
        "start_hour": int(start_hour),
        "end_hour": int(end_hour),
    }
