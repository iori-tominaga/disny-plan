"""
engine/event_calendar.py — TDS 実イベントカレンダー

実際の開催実績・恒例パターンに基づくイベント定義。
import_real_data.py（過去の daily_master 構築）と
auto_context.py（未来日のイベント推定）の両方から参照される。

新しいイベントが発表されたらここに追記するだけでよい。
"""
from __future__ import annotations

from datetime import date

# 確定日付のイベント（過去実績）: (開始, 終了, イベント名)
FIXED_EVENTS: list[tuple[str, str, str]] = [
    ("2024-06-06", "2024-09-01", "ファンタジースプリングス・グランドオープン"),
    ("2024-09-20", "2024-10-31", "ディズニー・ハロウィーン"),
    ("2024-11-15", "2024-12-25", "ディズニー・クリスマス"),
    ("2025-01-01", "2025-01-13", "お正月プログラム"),
    ("2025-01-15", "2025-03-16", "ダッフィー&フレンズのワンダフル・フレンドシップ"),
]

# 恒例イベント（月日ベース・毎年繰り返し）: 未来日の推定に使う
RECURRING_EVENTS: list[tuple[tuple[int, int], tuple[int, int], str]] = [
    ((7, 2),  (9, 1),   "ファンタジースプリングス・グランドオープン"),  # 夏イベント枠
    ((9, 20), (10, 31), "ディズニー・ハロウィーン"),
    ((11, 15), (12, 25), "ディズニー・クリスマス"),
    ((1, 1),  (1, 13),  "お正月プログラム"),
    ((1, 15), (3, 16),  "ダッフィー&フレンズのワンダフル・フレンドシップ"),
]


def event_for_date(d: date) -> str | None:
    """確定イベント表を優先し、なければ恒例パターンから推定する。"""
    ds = d.isoformat()
    for start, end, name in FIXED_EVENTS:
        if start <= ds <= end:
            return name
    md = (d.month, d.day)
    for start_md, end_md, name in RECURRING_EVENTS:
        if start_md <= md <= end_md:
            return name
    return None
