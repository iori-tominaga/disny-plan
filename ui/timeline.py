"""
ui/timeline.py — 最適巡回タイムライン表示

optimize_route() の結果を「移動・待ち・体験」3色のガントチャートと
ステップ表で可視化する。
"""
from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st

from engine.park_data import display_name

_COLORS = {"移動": "#94a3b8", "待ち": "#f59e0b", "体験": "#10b981"}


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def render_timeline(schedule: list[dict[str, Any]], start_hour: int, end_hour: int) -> None:
    if not schedule:
        st.warning("スケジュールが空です")
        return

    total_wait = sum(s["wait_minutes"] for s in schedule)
    total_walk = sum(s["walk_from_prev"] for s in schedule)
    total_ride = sum(s["ride_minutes"] for s in schedule)
    finish = schedule[-1]["depart_at"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("総待ち時間", f"{total_wait} 分")
    c2.metric("総歩行時間", f"{total_walk} 分")
    c3.metric("総体験時間", f"{total_ride} 分")
    c4.metric("全行程終了", _hhmm(finish))

    # ── ガントチャート ────────────────────────────────────────────
    names = [display_name(s["attraction_id"]) for s in schedule]
    fig = go.Figure()
    seen_label: set[str] = set()
    for s, name in zip(schedule, names):
        walk_start = s["arrive_at"] - s["walk_from_prev"]
        segments = [
            ("移動", walk_start, s["walk_from_prev"]),
            ("待ち", s["arrive_at"], s["wait_minutes"]),
            ("体験", s["arrive_at"] + s["wait_minutes"], s["ride_minutes"]),
        ]
        for label, base, dur in segments:
            if dur <= 0:
                continue
            fig.add_trace(go.Bar(
                y=[name], x=[dur], base=[base],
                orientation="h",
                marker_color=_COLORS[label],
                name=label,
                showlegend=label not in seen_label,
                hovertemplate=(
                    f"{name}<br>{label}: %{{x}}分"
                    f"<br>{_hhmm(base)} 〜 {_hhmm(base + dur)}<extra></extra>"
                ),
            ))
            seen_label.add(label)

    tickvals = [h * 60 for h in range(start_hour, end_hour + 1)]
    fig.update_layout(
        barmode="stack",
        height=120 + 60 * len(schedule),
        xaxis=dict(
            tickvals=tickvals,
            ticktext=[f"{h}時" for h in range(start_hour, end_hour + 1)],
            range=[start_hour * 60 - 10, end_hour * 60 + 10],
            title="時刻",
        ),
        yaxis=dict(categoryorder="array", categoryarray=names[::-1]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── ステップ表 ────────────────────────────────────────────────
    rows = []
    for i, s in enumerate(schedule, 1):
        rows.append({
            "順": i,
            "アトラクション": display_name(s["attraction_id"]),
            "徒歩": f"{s['walk_from_prev']}分",
            "到着": _hhmm(s["arrive_at"]),
            "待ち": f"{s['wait_minutes']}分",
            "体験": f"{s['ride_minutes']}分",
            "出発": _hhmm(s["depart_at"]),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
