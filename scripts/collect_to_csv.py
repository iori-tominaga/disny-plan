#!/usr/bin/env python3
"""
scripts/collect_to_csv.py — GitHub Actions 用の軽量コレクター

queue-times.com のライブ待ち時間を取得し、月別 CSV
（data/real_waits/YYYY-MM.csv）に追記する。DB には触らない。
CSV は merge_real_data.py が DB へ取り込む。

実行環境が PC でもクラウドでも動くよう、依存は requests のみ。
"""
import csv
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.collect_live_waits import API_URL, RIDE_MAP  # noqa: E402

CSV_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "real_waits")
)
JST = ZoneInfo("Asia/Tokyo")


def main():
    now = datetime.now(JST)
    if not (8 <= now.hour <= 22):
        print(f"{now:%H:%M} JST は営業時間外のためスキップ")
        return

    r = requests.get(API_URL, timeout=20)
    r.raise_for_status()
    data = r.json()
    rides = []
    for land in data.get("lands", []):
        rides.extend(land.get("rides", []))
    rides.extend(data.get("rides", []))

    os.makedirs(CSV_DIR, exist_ok=True)
    path = os.path.join(CSV_DIR, f"{now:%Y-%m}.csv")
    is_new = not os.path.exists(path)

    n = 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["ts", "attraction_id", "wait_minutes", "is_open"])
        ts = now.strftime("%Y-%m-%d %H:%M")
        for ride in rides:
            aid = RIDE_MAP.get(ride["id"])
            if aid is None:
                continue
            w.writerow([ts, aid, int(ride["wait_time"]), int(ride["is_open"])])
            n += 1
    print(f"{path} に {n} 件追記")


if __name__ == "__main__":
    main()
