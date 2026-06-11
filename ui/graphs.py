"""
ui/graphs.py — 待ち時間推移グラフ

選択アトラクションの1日の予測待ち時間（中央値）を折れ線で描画する。
1件のみ選択時は 25〜75 パーセンタイルの予測幅バンドも表示する。
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.park_data import display_name


def render_wait_graphs(
    predicted_waits: pd.DataFrame,
    selected_attractions: list[str],
) -> None:
    fig = go.Figure()

    show_band = len(selected_attractions) == 1

    for aid in selected_attractions:
        try:
            sub = predicted_waits.loc[aid].sort_index()
        except KeyError:
            continue
        hours = sub.index.tolist()
        name = display_name(aid)

        if show_band:
            fig.add_trace(go.Scatter(
                x=hours + hours[::-1],
                y=sub["wait_p75"].tolist() + sub["wait_p25"].tolist()[::-1],
                fill="toself",
                fillcolor="rgba(99, 110, 250, 0.15)",
                line=dict(width=0),
                hoverinfo="skip",
                showlegend=True,
                name="予測幅 (25〜75%)",
            ))

        fig.add_trace(go.Scatter(
            x=hours,
            y=sub["wait_median"],
            mode="lines+markers",
            name=name,
            hovertemplate=f"{name}<br>%{{x}}時: %{{y:.0f}}分<extra></extra>",
        ))

    fig.update_layout(
        height=420,
        xaxis=dict(title="時刻", dtick=1, ticksuffix="時"),
        yaxis=dict(title="予測待ち時間（分）", rangemode="tozero"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)
