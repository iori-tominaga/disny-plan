#!/usr/bin/env python3
"""
scripts/merge_real_data.py — 収集 CSV を DB へ取り込む

data/real_waits/*.csv（GitHub Actions ＋ ローカル収集の蓄積）を読み、
  - hourly_wait_times を時間平均で upsert（source='real'）
  - 該当日の daily_master を実測気象（Open-Meteo Archive）等で upsert
する。冪等：何度実行しても同じ結果になる。

app.py 起動時にも自動実行されるため、Streamlit Cloud などの
クラウドデプロイでも実測データが自動反映される。
"""
import glob
import os
import sys
import sqlite3
from datetime import date

import pandas as pd
import requests

if __name__ == "__main__" and sys.stdout.encoding \
        and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from engine.event_calendar import event_for_date  # noqa: E402

DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "tds.db")
)
CSV_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "real_waits")
)
_LAT, _LON = 35.6267, 139.8851
_SCHOOL_VACATIONS = [
    ((7, 20), (8, 31)), ((12, 23), (12, 31)), ((1, 1), (1, 7)), ((3, 21), (4, 7)),
]
_CLIMATE = {
    1: (9, 2), 2: (10, 3), 3: (14, 6), 4: (19, 11), 5: (24, 16), 6: (27, 20),
    7: (31, 25), 8: (33, 26), 9: (28, 21), 10: (22, 14), 11: (17, 9), 12: (12, 4),
}


def _wcode(code) -> str:
    code = int(code)
    if code in (0, 1):
        return "晴"
    if code in (2, 3, 45, 48):
        return "曇"
    if code in (71, 73, 75, 77, 85, 86):
        return "雪"
    return "雨"


def _is_holiday(d: date) -> int:
    try:
        import jpholiday
        if jpholiday.is_holiday(d):
            return 1
    except Exception:
        pass
    md = (d.month, d.day)
    return int(any(s <= md <= e for s, e in _SCHOOL_VACATIONS))


def _fetch_archive(d0: str, d1: str) -> dict:
    """期間の実測気象を取得。失敗・欠損は空 dict。"""
    try:
        r = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": _LAT, "longitude": _LON,
                "start_date": d0, "end_date": d1,
                "daily": "weathercode,temperature_2m_max,temperature_2m_min,wind_speed_10m_max",
                "timezone": "Asia/Tokyo",
            },
            timeout=30,
        )
        r.raise_for_status()
        dd = r.json()["daily"]
        return {
            t: (c, hi, lo, wd)
            for t, c, hi, lo, wd in zip(
                dd["time"], dd["weathercode"], dd["temperature_2m_max"],
                dd["temperature_2m_min"], dd["wind_speed_10m_max"],
            )
            if c is not None
        }
    except Exception:
        return {}


def main(verbose: bool = True) -> int:
    files = sorted(glob.glob(os.path.join(CSV_DIR, "*.csv")))
    if not files:
        if verbose:
            print("取り込む CSV がありません")
        return 0

    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df[df["is_open"] == 1].copy()
    if df.empty:
        if verbose:
            print("営業中スナップショットがありません")
        return 0

    ts = pd.to_datetime(df["ts"])
    df["date"] = ts.dt.strftime("%Y-%m-%d")
    df["hour"] = ts.dt.hour
    df = df[(df["hour"] >= 8) & (df["hour"] <= 22)]

    hourly = (
        df.groupby(["date", "attraction_id", "hour"])["wait_minutes"]
        .mean().round().astype(int).reset_index()
    )

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cols = [r[1] for r in c.execute("PRAGMA table_info(hourly_wait_times)")]
    if "source" not in cols:
        c.execute("ALTER TABLE hourly_wait_times ADD COLUMN source TEXT DEFAULT 'dummy'")

    for _, r in hourly.iterrows():
        c.execute(
            "INSERT OR REPLACE INTO hourly_wait_times VALUES (?,?,?,?,1,'real')",
            (r["date"], r["attraction_id"], int(r["hour"]), int(r["wait_minutes"])),
        )

    # ── 収集日の daily_master を実測値で upsert ───────────────────
    dates = sorted(hourly["date"].unique())
    wx = _fetch_archive(dates[0], dates[-1])
    for ds in dates:
        d = date.fromisoformat(ds)
        ih = _is_holiday(d)
        ev = event_for_date(d)
        dow = d.weekday()
        pr = 5 if (ih and dow >= 5) else (4 if (ih or dow >= 5) else (2 if dow == 4 else 1))
        if ds in wx:
            code, hi, lo, wd = wx[ds]
            weather, tmax, tmin, wind = _wcode(code), round(float(hi), 1), round(float(lo), 1), round(float(wd), 1)
        else:
            hi, lo = _CLIMATE[d.month]
            weather, tmax, tmin, wind = "晴", float(hi), float(lo), 3.5
        c.execute(
            """INSERT INTO daily_master VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(date) DO UPDATE SET
                 is_holiday=excluded.is_holiday, event_name=excluded.event_name,
                 weather=excluded.weather, temp_max=excluded.temp_max,
                 temp_min=excluded.temp_min, wind_speed=excluded.wind_speed,
                 price_rank=excluded.price_rank""",
            (ds, d.month, dow, (d.day - 1) // 7 + 1, ih, ev,
             weather, tmax, tmin, wind, pr),
        )

    conn.commit()
    conn.close()
    if verbose:
        print(f"✅ 取り込み完了: hourly {len(hourly)} 行 / daily {len(dates)} 日")
    return len(hourly)


if __name__ == "__main__":
    main()
