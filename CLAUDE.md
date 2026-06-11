# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

東京ディズニーシー（TDS）の過去データを活用し、未来の特定日における各アトラクションの待ち時間を予測、ユーザー指定条件に基づき最適な巡回ルートを動的生成する Web アプリケーション。対象データは**ファンタジースプリングス開業後の直近1年間**に限定する。

---

## 技術スタック

| 項目 | 採用技術 |
|---|---|
| UI ＋ サーバー | Python + Streamlit |
| データ処理・類似日計算 | pandas + scipy |
| ルート最適化 | Google OR-Tools |
| 可視化 | Plotly（Streamlit 統合） |
| データ永続化 | SQLite（標準ライブラリ sqlite3） |

### 主要コマンド

```bash
# 依存インストール
pip install -r requirements.txt

# アプリ起動
streamlit run app.py

# DB 初期化・ダミーデータ生成
python scripts/generate_dummy_data.py
```

---

## ディレクトリ構成

```
disny-plan/
├── app.py                        # Streamlit エントリーポイント
├── requirements.txt
├── data/
│   └── tds.db                    # SQLite DB（generate_dummy_data.py で生成）
├── scripts/
│   └── generate_dummy_data.py    # Phase 1: ダミーデータ生成
├── engine/
│   ├── similarity.py              # Phase 2: 類似日抽出ロジック
│   └── optimizer.py               # Phase 2: ルート最適化ロジック
└── ui/
    ├── input_panel.py             # Phase 3: 入力UI
    ├── timeline.py                # Phase 3: 最適巡回タイムライン
    └── graphs.py                  # Phase 3: 待ち時間推移グラフ
```

---

## データモデル（3テーブル）

### daily_master（日別環境データ）

```sql
CREATE TABLE daily_master (
    date         TEXT PRIMARY KEY,  -- YYYY-MM-DD
    month        INTEGER,
    day_of_week  INTEGER,           -- 0=月〜6=日
    week_num     INTEGER,           -- 第何曜日か（1〜5）
    is_holiday   INTEGER,           -- 0 or 1
    event_name   TEXT,              -- NULL=通常期、文字列=イベント名
    weather      TEXT,              -- 晴/曇/雨/雪
    temp_max     REAL,
    temp_min     REAL,
    wind_speed   REAL,              -- ハーバーショー中止判定に使用
    price_rank   INTEGER            -- チケット価格ランク 1〜5（混雑指標）
);
```

### hourly_wait_times（時間別待ち時間）

```sql
CREATE TABLE hourly_wait_times (
    date           TEXT,
    attraction_id  TEXT,
    hour           INTEGER,   -- 8〜22（24h表記）
    wait_minutes   INTEGER,
    is_valid       INTEGER,   -- 0=故障等ノイズ除外フラグ
    PRIMARY KEY (date, attraction_id, hour)
);
```

### movement_matrix（アトラクション間移動時間）

```sql
CREATE TABLE movement_matrix (
    from_attraction  TEXT,
    to_attraction    TEXT,
    walk_minutes     INTEGER,  -- メディテレーニアンハーバー迂回を考慮した実歩行時間
    PRIMARY KEY (from_attraction, to_attraction)
);
```

---

## コアアルゴリズム

### 類似日抽出（engine/similarity.py）

入力条件を特徴量ベクトルに変換し、過去データとの**重み付きユークリッド距離**で上位 N 日を抽出する。
予測待ち時間 = 抽出された類似日の同時間帯待ち時間の中央値（外れ値除外後）。

**特徴量の重み優先度:**
1. カレンダー属性（月・曜日・第何週・祝日フラグ）← 最重要
2. イベント属性（同一イベント開催中か）
3. 気象属性（雨有無・気温差）

### ルート最適化（engine/optimizer.py）

希望アトラクションを頂点とする**時間枠付き巡回問題（TSPTW）**として定式化し OR-Tools で解く。

- コスト = `walk_minutes` + 時間帯別予測待ち時間 + 体験時間（固定値）
- **夜間ハーバーショー補正**: 19〜21 時は全体待ち時間が緩和する傾向のため、該当時間帯の予測値にバイアス係数（< 1.0）を乗算する

---

## 開発フェーズ

| Phase | 内容 | 主要成果物 |
|---|---|---|
| **Phase 1** | アーキテクチャ確定 ＋ ダミーデータ生成 | `scripts/generate_dummy_data.py`, `data/tds.db` |
| **Phase 2** | 予測・最適化エンジン構築 | `engine/similarity.py`, `engine/optimizer.py` |
| **Phase 3** | UI 構築・システム統合 | `app.py`, `ui/` 配下全ファイル |

---

## 実装上の注意点

- `movement_matrix` はパーク内の**実際の歩行動線**を反映すること。エリアをまたぐ場合はメディテレーニアンハーバーを迂回するルートで計算する。
- 故障・臨時休止時のデータは `is_valid=0` フラグで除外し、類似日スコア計算・予測値算出の両方から除く。
- `generate_dummy_data.py` は冪等に設計する（何度実行しても同じ DB 状態になること）。
