"""
ui/input_panel.py — モバイルファースト入力 UI

ユーザーが入力するのは「日付」と「ぜったい乗りたいアトラクション」の2つだけ。
天気・気温・祝日・イベントは engine/auto_context.py が自動取得する。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import streamlit as st

from engine.park_data import ATTRACTIONS, attraction_emoji, display_name


def _label(aid: str) -> str:
    return f"{attraction_emoji(aid)} {display_name(aid)}"


def render_inputs() -> dict[str, Any] | None:
    """入力 UI を描画し、「魔法のプランをつくる」押下時に条件を返す。"""
    target_date = st.date_input(
        "🗓️ いつ あそびにいく？",
        value=date.today() + timedelta(days=14),
        min_value=date.today(),
        format="YYYY/MM/DD",
    )

    selected = st.multiselect(
        "🎢 ぜったい乗りたいアトラクションは？",
        options=list(ATTRACTIONS.keys()),
        format_func=_label,
        default=["frozen", "soaring"],
        placeholder="タップしてえらんでね",
    )

    with st.expander("🕐 入園・退園時間をかえる（ふつうは9時〜21時）"):
        start_hour, end_hour = st.select_slider(
            "あそぶ時間",
            options=list(range(8, 23)),
            value=(9, 21),
            format_func=lambda h: f"{h}時",
            label_visibility="collapsed",
        )

    pressed = st.button("🪄 魔法のプランをつくる ✨")

    if not pressed:
        return None
    if not selected:
        st.error("アトラクションを1つ以上えらんでね！")
        return None

    return {
        "target_date": target_date.isoformat(),
        "selected_attractions": selected,
        "start_hour": int(start_hour),
        "end_hour": int(end_hour),
    }
