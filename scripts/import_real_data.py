#!/usr/bin/env python3
"""
scripts/import_real_data.py — daily_master を実データに置換する

置換対象（既存の日付レンジはそのまま）:
  - 天気・最高/最低気温・最大風速 : Open-Meteo Archive API（舞浜の実測値）
  - 祝日・長期休みフラグ          : jpholiday ＋ 学校休暇ルール
  - イベント名                    : engine/event_calendar.py（実開催実績）
  - price_rank                    : 過去の変動価格は公開アーカイブがないため
                                    曜日・祝日からのヒューリスティックを維持

また hourly_wait_times に source 列（'dummy' / 'real'）を追加し、
collect_live_waits.py が実測値で上書きできるようにする。
"""
import os
import sys
import sqlite3
from datetime import date

import requests

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from engine.event_calendar import event_for_date

DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "tds.db")
)
_LAT, _LON = 35.6267, 139.8851

_SCHOOL_VACATIONS = [
    ((7, 20), (8, 31)), ((12, 23), (12, 31)), ((1, 1), (1, 7)), ((3, 21), (4, 7)),
]


def _weathercode_to_label(code: int) -> str:
    if code in (0, 1):
        return "晴"
    if code in (2, 3, 45, 48):
        return "曇"
    if code in (71, 73, 75, 77, 85, 86):
        return "雪"
    return "雨"


def _is_holiday(d: date) -> int:
    import jpholiday
    if jpholiday.is_holiday(d):
        return 1
    md = (d.month, d.day)
    return int(any(s <= md <= e for s, e in _SCHOOL_VACATIONS))


def _price_rank(dow: int, is_hol: int, event: str | None) -> int:
    if is_hol and dow >= 5:
        return 5
    if is_hol or dow >= 5:
        return 4 if event else 3
    return 2 if dow == 4 else 1


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    dates = [r[0] for r in c.execute("SELECT date FROM daily_master ORDER BY date")]
    if not dates:
        raise SystemExit("daily_master が空です。先に generate_dummy_data.py を実行してください。")
    start, end = dates[0], dates[-1]
    print(f"対象期間: {start} 〜 {end}（{len(dates)}日）")

    # ── 1. 実測気象データ取得 ─────────────────────────────────────
    print("[1/3] Open-Meteo Archive から実測気象データを取得中...")
    r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": _LAT, "longitude": _LON,
            "start_date": start, "end_date": end,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,wind_speed_10m_max",
            "timezone": "Asia/Tokyo",
        },
        timeout=60,
    )
    r.raise_for_status()
    daily = r.json()["daily"]
    wx = {
        ds: (code, tmax, tmin, wind)
        for ds, code, tmax, tmin, wind in zip(
            daily["time"], daily["weathercode"],
            daily["temperature_2m_max"], daily["temperature_2m_min"],
            daily["wind_speed_10m_max"],
        )
    }
    print(f"       {len(wx)} 日分を取得")

    # ── 2. daily_master を実データで更新 ──────────────────────────
    print("[2/3] daily_master を実データに更新中...")
    updated = 0
    for ds in dates:
        d = date.fromisoformat(ds)
        ih = _is_holiday(d)
        ev = event_for_date(d)
        pr = _price_rank(d.weekday(), ih, ev)
        if ds in wx and wx[ds][0] is not None:
            code, tmax, tmin, wind = wx[ds]
            c.execute(
                """UPDATE daily_master
                   SET is_holiday=?, event_name=?, weather=?,
                       temp_max=?, temp_min=?, wind_speed=?, price_rank=?
                   WHERE date=?""",
                (ih, ev, _weathercode_to_label(int(code)),
                 round(float(tmax), 1), round(float(tmin), 1),
                 round(float(wind), 1), pr, ds),
            )
        else:
            c.execute(
                "UPDATE daily_master SET is_holiday=?, event_name=?, price_rank=? WHERE date=?",
                (ih, ev, pr, ds),
            )
        updated += 1
    print(f"       {updated} 日を更新")

    # ── 3. hourly_wait_times に source 列を追加 ───────────────────
    print("[3/3] hourly_wait_times に source 列を追加中...")
    cols = [r[1] for r in c.execute("PRAGMA table_info(hourly_wait_times)")]
    if "source" not in cols:
        c.execute(
            "ALTER TABLE hourly_wait_times ADD COLUMN source TEXT DEFAULT 'dummy'"
        )
        print("       source 列を追加（既存行は 'dummy'）")
    else:
        print("       source 列は追加済み")

    conn.commit()
    conn.close()
    print("\n✅ 実データへの置換が完了しました")
    print("   待ち時間の実測値は scripts/collect_live_waits.py で蓄積してください")


if __name__ == "__main__":
    main()
