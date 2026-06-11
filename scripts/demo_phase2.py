#!/usr/bin/env python3
"""
scripts/demo_phase2.py — Phase 2 エンジンのエンドツーエンド動作確認

シナリオ:
  2026-07-23（木・夏休み・晴・サマーイベント期間相当）に
  人気アトラクション6件を 9:00〜21:00 で巡る。
"""
import os
import sys
import sqlite3

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from engine.similarity import build_target_features, extract_similar_days, predict_wait_times
from engine.optimizer import optimize_route, RouteInfeasibleError
from engine.park_data import display_name

DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "tds.db")
)


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def main():
    conn = sqlite3.connect(DB_PATH)

    # ── 1. 類似日抽出 ────────────────────────────────────────────
    target = build_target_features(
        target_date="2026-07-23",
        is_holiday=1,                          # 夏休み期間
        event_name="サマーフェスティバル2024",  # 同種イベント開催想定
        weather="晴",
        temp_max=32.0,
        temp_min=26.0,
    )
    print("=" * 60)
    print("【1】類似日抽出（ターゲット: 2026-07-23 木・晴・夏イベント）")
    print("=" * 60)
    similar = extract_similar_days(conn, target, top_n=10)
    for _, r in similar.iterrows():
        print(f"  {r['date']}  dow={r['day_of_week']} hol={r['is_holiday']} "
              f"event={r['event_name'] or '-'} {r['weather']} "
              f"score={r['similarity_score']:.3f}")

    # ── 2. 待ち時間予測 ──────────────────────────────────────────
    print()
    print("=" * 60)
    print("【2】待ち時間予測（類似日の中央値・外れ値除去済み）")
    print("=" * 60)
    waits = predict_wait_times(conn, similar)
    targets = ["soaring", "frozen", "tower_terror",
               "journey_center", "indiana_jones", "toy_story"]
    header = "  時刻 " + "".join(f"{aid[:8]:>10}" for aid in targets)
    print(header)
    for h in range(9, 22):
        row = f"  {h:02d}時 "
        for aid in targets:
            try:
                row += f"{int(waits.loc[(aid, h), 'wait_median']):>10}"
            except KeyError:
                row += f"{'-':>10}"
        print(row)

    # ── 3. ルート最適化 ──────────────────────────────────────────
    print()
    print("=" * 60)
    print("【3】最適巡回ルート（9:00 入園〜21:00 退園）")
    print("=" * 60)
    try:
        schedule = optimize_route(conn, targets, waits, start_hour=9, end_hour=21)
    except RouteInfeasibleError as e:
        print(f"  ルートなし: {e}")
        return

    total_wait = total_walk = 0
    for i, s in enumerate(schedule, 1):
        total_wait += s["wait_minutes"]
        total_walk += s["walk_from_prev"]
        print(f"  {i}. 徒歩{s['walk_from_prev']:>2}分 → "
              f"{hhmm(s['arrive_at'])} 着 | "
              f"待ち{s['wait_minutes']:>3}分 + 体験{s['ride_minutes']:>2}分 | "
              f"{hhmm(s['depart_at'])} 発  {display_name(s['attraction_id'])}")
    print()
    print(f"  合計: 待ち {total_wait} 分 / 歩き {total_walk} 分 / "
          f"終了 {hhmm(schedule[-1]['depart_at'])}")

    conn.close()


if __name__ == "__main__":
    main()
