"""
ui/timeline.py — フルデイプランの縦型カードタイムライン（モバイルファースト）

planner.build_full_plan() の結果を、スマホで読みやすい
縦スクロールのカード列として描画する。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from engine.park_data import attraction_emoji, display_name


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _ride_card(p: dict[str, Any]) -> str:
    aid = p["attraction_id"]
    name = f"{attraction_emoji(aid)} {display_name(aid)}"
    if p["type"] == "must":
        badge = '<span class="badge">★ ぜったい乗る！</span>'
        reason = ""
        cls = "must"
    else:
        badge = '<span class="badge">🎁 おすすめ</span>'
        reason = f'<div class="reason">💡 {p.get("reason", "")}</div>'
        cls = "recommend"
    # Markdown が4スペースインデントをコードブロック扱いするため1行で組む
    return (
        f'<div class="plan-card {cls}">'
        f'<div class="clock">{_hhmm(p["arrive_at"])}<small>とうちゃく</small></div>'
        f'<div class="body">{badge}<div class="name">{name}</div>'
        f'<div class="meta">⏳ 待ち {p["wait_minutes"]}分 ｜ 🎬 体験 {p["ride_minutes"]}分 ｜ '
        f'🏁 {_hhmm(p["depart_at"])} しゅっぱつ</div>{reason}</div></div>'
    )


def _pause_card(p: dict[str, Any]) -> str:
    return (
        f'<div class="plan-card pause">'
        f'<div class="clock">{_hhmm(p["arrive_at"])}<small>〜{_hhmm(p["depart_at"])}</small></div>'
        f'<div class="body"><div class="name">{p["label"]}</div>'
        f'<div class="meta">じゆうじかん {p["depart_at"] - p["arrive_at"]}分</div></div></div>'
    )


def render_plan(plan: list[dict[str, Any]]) -> None:
    if not plan:
        st.warning("プランが空です")
        return

    rides = [p for p in plan if p["type"] in ("must", "recommend")]
    total_wait = sum(p["wait_minutes"] for p in rides)
    n_must = sum(1 for p in rides if p["type"] == "must")
    n_rec  = len(rides) - n_must

    c1, c2, c3 = st.columns(3)
    c1.metric("のれる数", f"{len(rides)}コ")
    c2.metric("うち おすすめ", f"+{n_rec}コ")
    c3.metric("総待ち時間", f"{total_wait}分")

    html_parts: list[str] = []
    for p in plan:
        if p["type"] in ("must", "recommend"):
            if p.get("walk_from_prev"):
                html_parts.append(
                    f'<div class="walk-step">🚶 あるいて {p["walk_from_prev"]}分 ↓</div>'
                )
            html_parts.append(_ride_card(p))
        else:
            html_parts.append(_pause_card(p))

    st.markdown("".join(html_parts), unsafe_allow_html=True)
