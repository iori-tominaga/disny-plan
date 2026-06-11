#!/usr/bin/env python3
"""
scripts/generate_dummy_data.py

東京ディズニーシー 待ち時間予測アプリ — ダミーデータ生成スクリプト
冪等設計：何度実行しても同一の DB 状態を再現する（seed=42 固定）

生成データ:
  daily_master      : 365 行（2024-06-06 〜 2025-06-05）
  hourly_wait_times : 365 × 25 × 15 = 136,875 行
  movement_matrix   : 25 × 25 = 625 行
"""

import os
import sys
import sqlite3
import numpy as np

# Windows コンソール(cp932)でも絵文字・日本語を安全に出力する
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import date, timedelta

np.random.seed(42)

# ── パス設定 ──────────────────────────────────────────────────────────
_HERE   = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.normpath(os.path.join(_HERE, "..", "data", "tds.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ── データ期間 ────────────────────────────────────────────────────────
START_DATE = date(2024, 6, 6)   # ファンタジースプリングス開業日
END_DATE   = date(2025, 6, 5)

# ── アトラクション定義 ────────────────────────────────────────────────
# (id, 表示名, エリア, 体験時間[分], 人気度[0-1])
ATTRACTIONS = [
    # Mysterious Island
    ("journey_center",   "センター・オブ・ジ・アース",                 "MI",   3, 0.92),
    ("leagues_20k",      "海底2万マイル",                               "MI",   8, 0.65),
    # Lost River Delta
    ("indiana_jones",    "インディ・ジョーンズ・アドベンチャー",         "LRD",  3, 0.90),
    ("raging_spirits",   "レイジングスピリッツ",                        "LRD",  2, 0.75),
    # American Waterfront
    ("tower_terror",     "タワー・オブ・テラー",                        "AW",   2, 0.95),
    ("toy_story",        "トイ・ストーリー・マニア！",                   "AW",   7, 0.88),
    ("turtle_talk",      "タートル・トーク",                            "AW",  15, 0.50),
    # Port Discovery
    ("soaring",          "ソアリン：ファンタスティック・フライト",        "PD",   5, 0.98),
    ("nemo_searider",    "ニモ＆フレンズ・シーライダー",                 "PD",   5, 0.70),
    ("aquatopia",        "アクアトピア",                                "PD",   3, 0.55),
    # Arabian Coast
    ("sindbad",          "シンドバッド・ストーリーブック・ヴォヤッジ",   "AC",   8, 0.60),
    ("magic_lamp",       "マジックランプシアター",                      "AC",  15, 0.55),
    ("jasmine_carpet",   "ジャスミンのフライングカーペット",             "AC",   2, 0.45),
    # Mermaid Lagoon
    ("jumpin_jellyfish", "ジャンピン・ジェリーフィッシュ",               "ML",   2, 0.45),
    ("scuttle_scooters", "スカットルのスクーター",                      "ML",   2, 0.40),
    ("flounder_coaster", "フランダーのフライングフィッシュコースター",    "ML",   2, 0.48),
    ("blowfish_balloon", "ブローフィッシュ・バルーンレース",             "ML",   2, 0.42),
    ("ariel_playground", "アリエルのプレイグラウンド",                   "ML",  20, 0.25),
    # Mediterranean Harbor
    ("electric_railway", "ディズニーシー・エレクトリックレールウェイ",    "MH",  10, 0.35),
    ("fortress",         "フォートレス・エクスプロレーション",           "MH",  20, 0.10),
    # Fantasy Springs（開業直後の特需あり）
    ("peter_pan",        "ピーター・パンのネバーランドアドベンチャー",    "FS",   5, 0.99),
    ("tinkerbell",       "ティンカー・ベルのビジーバギー",               "FS",   3, 0.80),
    ("rapunzel",         "ラプンツェルのランタンフェスティバル",          "FS",   3, 0.97),
    ("frozen",           "アナとエルサのフローズンジャーニー",            "FS",   5, 0.99),
    # American Waterfront (その他)
    ("big_city",         "ビッグシティ・ヴィークル",                    "AW",   5, 0.15),
]

AREA_OF = {a[0]: a[2] for a in ATTRACTIONS}

# ── エリア間移動時間（分）—— メディテレーニアンハーバー迂回考慮済み ───
_AREA_WALK = {
    ("MH", "MH"):  3,  ("MH", "AC"):  6,  ("MH", "LRD"): 11, ("MH", "MI"):  8,
    ("MH", "PD"): 12,  ("MH", "AW"): 10,  ("MH", "ML"):  16, ("MH", "FS"): 20,
    ("AC", "AC"):  3,  ("AC", "LRD"):  5,  ("AC", "MI"):   9, ("AC", "PD"): 14,
    ("AC", "AW"): 14,  ("AC", "ML"):  14,  ("AC", "FS"):  18,
    ("LRD","LRD"): 3,  ("LRD","MI"):  11,  ("LRD","PD"):  13,
    ("LRD","AW"): 12,  ("LRD","ML"):  18,  ("LRD","FS"):  10,
    ("MI", "MI"):  3,  ("MI", "PD"):   8,  ("MI", "AW"):  13,
    ("MI", "ML"): 16,  ("MI", "FS"):  18,
    ("PD", "PD"):  3,  ("PD", "AW"):   8,  ("PD", "ML"):  12, ("PD", "FS"): 20,
    ("AW", "AW"):  3,  ("AW", "ML"):   5,  ("AW", "FS"):  12,
    ("ML", "ML"):  3,  ("ML", "FS"):  15,
    ("FS", "FS"):  4,
}

def _area_walk(a1: str, a2: str) -> int:
    return _AREA_WALK.get((a1, a2), _AREA_WALK.get((a2, a1), 15))


# ── イベントスケジュール ──────────────────────────────────────────────
_EVENTS = [
    ("2024-06-06", "2024-06-30", "グランドオープニング"),
    ("2024-07-01", "2024-08-31", "サマーフェスティバル2024"),
    ("2024-09-02", "2024-10-31", "ディズニー・ハロウィーン2024"),
    ("2024-11-01", "2024-12-25", "ディズニー・クリスマス2024"),
    ("2024-12-26", "2025-01-07", "ディズニー・ニューイヤーズ・カウントダウン"),
    ("2025-03-20", "2025-04-20", "ディズニー・イースター2025"),
]

def _get_event(ds: str):
    for s, e, n in _EVENTS:
        if s <= ds <= e:
            return n
    return None


# ── 祝日・長期休暇セット ──────────────────────────────────────────────
def _build_holidays() -> set:
    hols = {
        "2024-07-15", "2024-08-11",
        "2024-09-16", "2024-09-22", "2024-09-23",
        "2024-10-14", "2024-11-03", "2024-11-04", "2024-11-23",
        "2025-01-01", "2025-01-02", "2025-01-03", "2025-01-13",
        "2025-02-11", "2025-02-24", "2025-03-20",
        "2025-04-29",
        "2025-05-03", "2025-05-04", "2025-05-05", "2025-05-06",
    }
    # 夏休み 7/20〜8/31
    for m, days in [(7, range(20, 32)), (8, range(1, 32))]:
        for d in days:
            try:
                hols.add(date(2024, m, d).isoformat())
            except ValueError:
                pass
    # 年末年始 12/23〜1/7
    for d in range(23, 32):
        hols.add(f"2024-12-{d:02d}")
    for d in range(1, 8):
        hols.add(f"2025-01-{d:02d}")
    # 春休み 3/21〜4/7
    for d in range(21, 32):
        hols.add(f"2025-03-{d:02d}")
    for d in range(1, 8):
        hols.add(f"2025-04-{d:02d}")
    # GW 4/29〜5/6
    for d in range(29, 31):
        hols.add(f"2025-04-{d:02d}")
    for d in range(1, 7):
        hols.add(f"2025-05-{d:02d}")
    return hols

HOLIDAYS = _build_holidays()


# ── 価格ランク算出 ────────────────────────────────────────────────────
_PEAK_PERIODS = [
    ("2025-04-29", "2025-05-06"),    # GW
    ("2024-12-30", "2025-01-03"),    # 年末年始ピーク
]
_BUSY_PERIODS = [
    ("2024-07-20", "2024-08-31"),    # 夏休み
    ("2024-12-23", "2025-01-07"),    # 年末年始
    ("2025-03-21", "2025-04-07"),    # 春休み
]

def _price_rank(ds: str, dow: int, is_hol: int) -> int:
    for s, e in _PEAK_PERIODS:
        if s <= ds <= e:
            return 5
    for s, e in _BUSY_PERIODS:
        if s <= ds <= e:
            return 5 if (dow >= 5 or is_hol) else 4
    if dow >= 5 or is_hol:
        return 3
    if dow == 4:    # 金曜
        return 2
    return 1


# ── 待ち時間生成 ──────────────────────────────────────────────────────
_TIME_CURVE = {
    8: 0.35,  9: 0.65, 10: 1.05, 11: 1.30, 12: 1.25, 13: 1.10,
    14: 1.15, 15: 1.20, 16: 1.10, 17: 1.05,
    18: 0.80, 19: 0.60, 20: 0.55, 21: 0.45, 22: 0.30,
}
_FS_BONUS = {
    "peter_pan": 1.9, "rapunzel": 1.85, "frozen": 1.9, "tinkerbell": 1.3,
}

def _wait(hour: int, pop: float, price_rank: int, weather: str, att_id: str) -> int:
    base  = pop * 85 + 10
    crowd = 0.55 + (price_rank - 1) * 0.15
    tf    = _TIME_CURVE.get(hour, 0.5)
    wf    = {"晴": 1.10, "曇": 1.00, "雨": 0.65, "雪": 0.45}.get(weather, 1.0)
    fs    = _FS_BONUS.get(att_id, 1.0)
    noise = np.random.normal(1.0, 0.12)
    return max(0, min(150, int(base * crowd * tf * wf * fs * noise)))


# ── 月別気象データ ────────────────────────────────────────────────────
_TEMP = {
    1: (9, 2), 2: (10, 3),  3: (14, 6),  4: (19, 11), 5: (24, 16), 6: (27, 20),
    7: (31,25), 8: (33, 26), 9: (28, 21), 10: (22, 14), 11: (17, 9), 12: (12, 4),
}
# 月別天気確率 [晴, 曇, 雨, 雪]
_WP = {
    1:  [.55, .30, .13, .02],  2: [.50, .30, .15, .05],  3: [.45, .30, .25, .00],
    4:  [.45, .30, .25, .00],  5: [.45, .30, .25, .00],  6: [.30, .30, .40, .00],
    7:  [.40, .30, .30, .00],  8: [.50, .25, .25, .00],  9: [.35, .30, .35, .00],
    10: [.50, .30, .20, .00], 11: [.50, .30, .20, .00], 12: [.55, .30, .13, .02],
}
_WL = ["晴", "曇", "雨", "雪"]


# ════════════════════════════════════════════════════════════════════
def main():
    print(f"生成先: {DB_PATH}\n")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── テーブル再作成（冪等保証） ────────────────────────────────────
    c.executescript("""
        DROP TABLE IF EXISTS daily_master;
        DROP TABLE IF EXISTS hourly_wait_times;
        DROP TABLE IF EXISTS movement_matrix;

        CREATE TABLE daily_master (
            date        TEXT PRIMARY KEY,
            month       INTEGER,
            day_of_week INTEGER,
            week_num    INTEGER,
            is_holiday  INTEGER,
            event_name  TEXT,
            weather     TEXT,
            temp_max    REAL,
            temp_min    REAL,
            wind_speed  REAL,
            price_rank  INTEGER
        );

        CREATE TABLE hourly_wait_times (
            date          TEXT,
            attraction_id TEXT,
            hour          INTEGER,
            wait_minutes  INTEGER,
            is_valid      INTEGER,
            PRIMARY KEY (date, attraction_id, hour)
        );

        CREATE TABLE movement_matrix (
            from_attraction TEXT,
            to_attraction   TEXT,
            walk_minutes    INTEGER,
            PRIMARY KEY (from_attraction, to_attraction)
        );
    """)

    # ── 1. daily_master ──────────────────────────────────────────────
    print("[1/3] daily_master 生成中...")
    dm_rows = []
    cur = START_DATE
    while cur <= END_DATE:
        ds  = cur.isoformat()
        dow = cur.weekday()           # 0=月〜6=日
        wk  = (cur.day - 1) // 7 + 1 # 第何曜日か
        ih  = int(ds in HOLIDAYS)
        ev  = _get_event(ds)
        pr  = _price_rank(ds, dow, ih)

        m = cur.month
        th, tl = _TEMP[m]
        tmax = round(float(th + np.random.normal(0, 2.5)), 1)
        tmin = round(float(tl + np.random.normal(0, 2.0)), 1)
        wth  = _WL[int(np.random.choice(4, p=_WP[m]))]
        wnd  = round(max(0.0, float(np.random.normal(3.5, 1.5))), 1)

        dm_rows.append((ds, m, dow, wk, ih, ev, wth, tmax, tmin, wnd, pr))
        cur += timedelta(days=1)

    c.executemany("INSERT INTO daily_master VALUES (?,?,?,?,?,?,?,?,?,?,?)", dm_rows)
    print(f"       {len(dm_rows):,} 行を挿入")

    # ── 2. hourly_wait_times ─────────────────────────────────────────
    print("[2/3] hourly_wait_times 生成中...")
    hw_rows = []
    for ds, _m, _dow, _wk, _ih, _ev, wth, _tmax, _tmin, _wnd, pr in dm_rows:
        for att_id, _name, _area, _ride, pop in ATTRACTIONS:
            for hour in range(8, 23):
                valid = int(np.random.random() >= 0.025)  # 2.5%の確率で故障フラグ
                wait  = _wait(hour, pop, pr, wth, att_id) if valid else 0
                hw_rows.append((ds, att_id, hour, wait, valid))

    c.executemany("INSERT INTO hourly_wait_times VALUES (?,?,?,?,?)", hw_rows)
    print(f"       {len(hw_rows):,} 行を挿入")

    # ── 3. movement_matrix ───────────────────────────────────────────
    print("[3/3] movement_matrix 生成中...")
    att_ids = [a[0] for a in ATTRACTIONS]
    mm_rows = []
    for fid in att_ids:
        for tid in att_ids:
            if fid == tid:
                walk = 0
            else:
                base   = _area_walk(AREA_OF[fid], AREA_OF[tid])
                offset = int(np.random.randint(-2, 3))  # ±2分の個体差
                walk   = max(1, base + offset)
            mm_rows.append((fid, tid, walk))

    c.executemany("INSERT INTO movement_matrix VALUES (?,?,?)", mm_rows)
    print(f"       {len(mm_rows):,} 行を挿入")

    conn.commit()
    conn.close()

    print("\n" + "="*50)
    print("✅  DB 生成完了！")
    print(f"   パス: {DB_PATH}")
    print(f"   daily_master      : {len(dm_rows):,} 行")
    print(f"   hourly_wait_times : {len(hw_rows):,} 行")
    print(f"   movement_matrix   : {len(mm_rows):,} 行")
    print("="*50)


if __name__ == "__main__":
    main()
