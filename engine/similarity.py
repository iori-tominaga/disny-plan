"""
engine/similarity.py — 類似日抽出 & 待ち時間予測ロジック

アルゴリズム:
  1. 入力条件（未来の日付の属性）を特徴量ベクトルに変換
  2. daily_master 全行との重み付きユークリッド距離を計算
  3. 距離が小さい上位 N 日を「類似日」として抽出
  4. 類似日の同時間帯実績から IQR 外れ値を除外し、中央値を予測値とする
"""
from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np
import pandas as pd

# 特徴量の重み（CLAUDE.md の優先度: カレンダー > イベント > 気象）
WEIGHTS: dict[str, float] = {
    "month":       3.0,
    "day_of_week": 4.0,
    "week_num":    1.5,
    "is_holiday":  5.0,
    "same_event":  6.0,
    "rain":        2.0,
    "temp_diff":   1.0,
}

_RAINY = ("雨", "雪")


def build_target_features(
    target_date: str,
    is_holiday: int,
    event_name: str | None,
    weather: str,
    temp_max: float,
    temp_min: float,
) -> dict[str, Any]:
    """日付文字列(YYYY-MM-DD)からカレンダー属性を導出し target dict を組み立てる。"""
    d = pd.Timestamp(target_date)
    return {
        "month":       d.month,
        "day_of_week": d.dayofweek,          # 0=月〜6=日
        "week_num":    (d.day - 1) // 7 + 1,
        "is_holiday":  is_holiday,
        "event_name":  event_name,
        "weather":     weather,
        "temp_max":    temp_max,
        "temp_min":    temp_min,
    }


def extract_similar_days(
    conn: sqlite3.Connection,
    target: dict[str, Any],
    top_n: int = 10,
) -> pd.DataFrame:
    """
    過去データから target と類似する日を上位 top_n 件抽出する。

    Returns
    -------
    pd.DataFrame
        daily_master の行に distance / similarity_score を付加し、
        類似度の高い順にソートしたもの。
    """
    df = pd.read_sql_query("SELECT * FROM daily_master", conn)

    # ── 各特徴量の距離（すべて 0〜1 に正規化） ──────────────────────
    # 月: 12月と1月は隣同士なので循環距離を使う
    m = target["month"]
    d_month = df["month"].map(lambda x: min(abs(x - m), 12 - abs(x - m)) / 6.0)

    d_dow  = (df["day_of_week"] != target["day_of_week"]).astype(float)
    d_week = (df["week_num"] - target["week_num"]).abs() / 4.0
    d_hol  = (df["is_holiday"] - target["is_holiday"]).abs().astype(float)

    ev = target.get("event_name")
    d_event = df["event_name"].map(
        lambda x: 0.0 if (x == ev) or (pd.isna(x) and not ev) else 1.0
    )

    rain_t = 1.0 if target["weather"] in _RAINY else 0.0
    d_rain = df["weather"].map(lambda w: abs((1.0 if w in _RAINY else 0.0) - rain_t))

    d_temp = (
        ((df["temp_max"] - target["temp_max"]).abs()
         + (df["temp_min"] - target["temp_min"]).abs()) / 2 / 15.0
    ).clip(upper=1.0)

    # ── 重み付きユークリッド距離 ────────────────────────────────────
    dist_sq = (
        WEIGHTS["month"]       * d_month ** 2
        + WEIGHTS["day_of_week"] * d_dow ** 2
        + WEIGHTS["week_num"]    * d_week ** 2
        + WEIGHTS["is_holiday"]  * d_hol ** 2
        + WEIGHTS["same_event"]  * d_event ** 2
        + WEIGHTS["rain"]        * d_rain ** 2
        + WEIGHTS["temp_diff"]   * d_temp ** 2
    )
    df["distance"] = np.sqrt(dist_sq)
    df["similarity_score"] = 1.0 / (1.0 + df["distance"])

    return (
        df.sort_values("similarity_score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


def predict_wait_times(
    conn: sqlite3.Connection,
    similar_days: pd.DataFrame,
) -> pd.DataFrame:
    """
    類似日の実績から時間帯別予測待ち時間を算出する。

    is_valid=0（故障等）の行は除外済み。さらに 1.5×IQR ルールで
    外れ値を落としてから中央値を取る。

    Returns
    -------
    pd.DataFrame
        MultiIndex(attraction_id, hour)、
        カラム: wait_median, wait_p25, wait_p75, n_samples
    """
    dates = similar_days["date"].tolist()
    ph = ",".join("?" * len(dates))
    df = pd.read_sql_query(
        f"""
        SELECT attraction_id, hour, wait_minutes
        FROM hourly_wait_times
        WHERE is_valid = 1 AND date IN ({ph})
        """,
        conn,
        params=dates,
    )

    records: dict[tuple[str, int], dict[str, float]] = {}
    for (aid, hr), g in df.groupby(["attraction_id", "hour"]):
        v = g["wait_minutes"].to_numpy(dtype=float)
        q1, q3 = np.percentile(v, [25, 75])
        iqr = q3 - q1
        kept = v[(v >= q1 - 1.5 * iqr) & (v <= q3 + 1.5 * iqr)]
        if kept.size == 0:
            kept = v
        records[(aid, int(hr))] = {
            "wait_median": float(np.median(kept)),
            "wait_p25":    float(np.percentile(kept, 25)),
            "wait_p75":    float(np.percentile(kept, 75)),
            "n_samples":   int(kept.size),
        }

    out = pd.DataFrame.from_dict(records, orient="index")
    out.index = pd.MultiIndex.from_tuples(out.index, names=["attraction_id", "hour"])
    return out.sort_index()
