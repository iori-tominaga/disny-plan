#!/usr/bin/env python3
"""
scripts/collect_live_waits.py — queue-times.com から実測待ち時間を収集

15分おき程度の定期実行を想定（Windows タスクスケジューラ / cron / GitHub Actions）。
1回の実行で:
  1. ライブ待ち時間を取得し wait_snapshots に生データを保存
  2. 当日・当該時間帯の hourly_wait_times をスナップショット平均で上書き
     （source='real'。ダミー行は実測が来た時点で置き換わる）
  3. 当日の daily_master 行を実況気象・祝日・イベントで upsert

定期実行の登録例（Windows・15分おき）:
  schtasks /create /tn "TDS_Collect" /sc minute /mo 15 ^
    /tr "C:\\...\\python.exe C:\\...\\scripts\\collect_live_waits.py"

データ提供: Powered by Queue-Times.com
"""
import os
import sys
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from engine.auto_context import build_auto_context

DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "tds.db")
)
API_URL = "https://queue-times.com/parks/275/queue_times.json"
JST = ZoneInfo("Asia/Tokyo")

# queue-times のライドID → 本プロジェクトの attraction_id
RIDE_MAP: dict[int, str] = {
    8029:  "leagues_20k",
    13559: "frozen",
    8038:  "aquatopia",
    8022:  "ariel_playground",
    8037:  "big_city",
    8044:  "blowfish_balloon",
    8036:  "electric_railway",   # American Waterfront 駅を代表値とする
    13562: "tinkerbell",
    8041:  "flounder_coaster",
    8048:  "fortress",
    8027:  "indiana_jones",
    8025:  "jasmine_carpet",
    8028:  "journey_center",
    8043:  "jumpin_jellyfish",
    8051:  "nemo_searider",
    13561: "peter_pan",
    8046:  "raging_spirits",
    13560: "rapunzel",
    8042:  "scuttle_scooters",
    8039:  "sindbad",
    8024:  "soaring",
    8030:  "magic_lamp",
    8047:  "tower_terror",
    8023:  "toy_story",
    8050:  "turtle_talk",
}


def _ensure_tables(c: sqlite3.Cursor) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS wait_snapshots (
            ts            TEXT,
            attraction_id TEXT,
            wait_minutes  INTEGER,
            is_open       INTEGER,
            PRIMARY KEY (ts, attraction_id)
        )
    """)
    cols = [r[1] for r in c.execute("PRAGMA table_info(hourly_wait_times)")]
    if "source" not in cols:
        c.execute("ALTER TABLE hourly_wait_times ADD COLUMN source TEXT DEFAULT 'dummy'")


def _upsert_daily_master(c: sqlite3.Cursor, ds: str) -> None:
    from datetime import date as _date
    d = _date.fromisoformat(ds)
    ctx = build_auto_context(ds)
    dow = d.weekday()
    pr = 5 if (ctx["is_holiday"] and dow >= 5) else (4 if (ctx["is_holiday"] or dow >= 5) else (2 if dow == 4 else 1))
    c.execute(
        """INSERT INTO daily_master
           (date, month, day_of_week, week_num, is_holiday, event_name,
            weather, temp_max, temp_min, wind_speed, price_rank)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(date) DO UPDATE SET
             is_holiday=excluded.is_holiday, event_name=excluded.event_name,
             weather=excluded.weather, temp_max=excluded.temp_max,
             temp_min=excluded.temp_min, price_rank=excluded.price_rank""",
        (ds, d.month, dow, (d.day - 1) // 7 + 1, ctx["is_holiday"],
         ctx["event_name"], ctx["weather"], ctx["temp_max"], ctx["temp_min"],
         3.5, pr),
    )


def main():
    now = datetime.now(JST)
    ds, hour = now.date().isoformat(), now.hour
    print(f"収集時刻: {now:%Y-%m-%d %H:%M} JST")

    r = requests.get(API_URL, timeout=20)
    r.raise_for_status()
    data = r.json()
    rides = []
    for land in data.get("lands", []):
        rides.extend(land.get("rides", []))
    rides.extend(data.get("rides", []))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    _ensure_tables(c)

    ts = now.strftime("%Y-%m-%d %H:%M")
    n_snap = 0
    for ride in rides:
        aid = RIDE_MAP.get(ride["id"])
        if aid is None:
            continue
        c.execute(
            "INSERT OR REPLACE INTO wait_snapshots VALUES (?,?,?,?)",
            (ts, aid, int(ride["wait_time"]), int(ride["is_open"])),
        )
        n_snap += 1
    print(f"スナップショット保存: {n_snap} 件")

    if not (8 <= hour <= 22):
        print("営業時間外のため hourly 集計はスキップ")
        conn.commit()
        conn.close()
        return

    # この1時間のスナップショット平均で hourly_wait_times を上書き
    n_hourly = 0
    for (aid,) in c.execute(
        "SELECT DISTINCT attraction_id FROM wait_snapshots WHERE ts LIKE ?",
        (f"{ds} {hour:02d}:%",),
    ).fetchall():
        row = c.execute(
            """SELECT AVG(wait_minutes), MAX(is_open)
               FROM wait_snapshots
               WHERE attraction_id=? AND ts LIKE ? AND is_open=1""",
            (aid, f"{ds} {hour:02d}:%"),
        ).fetchone()
        avg_wait, any_open = row
        is_valid = 1 if any_open else 0
        wait = int(round(avg_wait)) if avg_wait is not None else 0
        c.execute(
            "INSERT OR REPLACE INTO hourly_wait_times VALUES (?,?,?,?,?,?)",
            (ds, aid, hour, wait, is_valid, "real"),
        )
        n_hourly += 1
    print(f"hourly_wait_times 更新: {n_hourly} 件（{ds} {hour}時台, source='real'）")

    _upsert_daily_master(c, ds)
    print("daily_master 当日行を upsert")

    conn.commit()
    conn.close()
    print("✅ 収集完了")


if __name__ == "__main__":
    main()
