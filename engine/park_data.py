"""
engine/park_data.py — アトラクション静的マスタ

体験時間（ride_minutes）は固定値のため DB ではなくコードで保持する。
表示名は UI（Phase 3）でも使用する。
"""
from __future__ import annotations

# id -> {name, area, ride_minutes}
ATTRACTIONS: dict[str, dict] = {
    "journey_center":   {"name": "センター・オブ・ジ・アース",               "area": "MI",  "ride_minutes": 3},
    "leagues_20k":      {"name": "海底2万マイル",                             "area": "MI",  "ride_minutes": 8},
    "indiana_jones":    {"name": "インディ・ジョーンズ・アドベンチャー",       "area": "LRD", "ride_minutes": 3},
    "raging_spirits":   {"name": "レイジングスピリッツ",                      "area": "LRD", "ride_minutes": 2},
    "tower_terror":     {"name": "タワー・オブ・テラー",                      "area": "AW",  "ride_minutes": 2},
    "toy_story":        {"name": "トイ・ストーリー・マニア！",                 "area": "AW",  "ride_minutes": 7},
    "turtle_talk":      {"name": "タートル・トーク",                          "area": "AW",  "ride_minutes": 15},
    "soaring":          {"name": "ソアリン：ファンタスティック・フライト",      "area": "PD",  "ride_minutes": 5},
    "nemo_searider":    {"name": "ニモ＆フレンズ・シーライダー",               "area": "PD",  "ride_minutes": 5},
    "aquatopia":        {"name": "アクアトピア",                              "area": "PD",  "ride_minutes": 3},
    "sindbad":          {"name": "シンドバッド・ストーリーブック・ヴォヤッジ", "area": "AC",  "ride_minutes": 8},
    "magic_lamp":       {"name": "マジックランプシアター",                    "area": "AC",  "ride_minutes": 15},
    "jasmine_carpet":   {"name": "ジャスミンのフライングカーペット",           "area": "AC",  "ride_minutes": 2},
    "jumpin_jellyfish": {"name": "ジャンピン・ジェリーフィッシュ",             "area": "ML",  "ride_minutes": 2},
    "scuttle_scooters": {"name": "スカットルのスクーター",                    "area": "ML",  "ride_minutes": 2},
    "flounder_coaster": {"name": "フランダーのフライングフィッシュコースター",  "area": "ML",  "ride_minutes": 2},
    "blowfish_balloon": {"name": "ブローフィッシュ・バルーンレース",           "area": "ML",  "ride_minutes": 2},
    "ariel_playground": {"name": "アリエルのプレイグラウンド",                 "area": "ML",  "ride_minutes": 20},
    "electric_railway": {"name": "ディズニーシー・エレクトリックレールウェイ",  "area": "MH",  "ride_minutes": 10},
    "fortress":         {"name": "フォートレス・エクスプロレーション",         "area": "MH",  "ride_minutes": 20},
    "peter_pan":        {"name": "ピーター・パンのネバーランドアドベンチャー",  "area": "FS",  "ride_minutes": 5},
    "tinkerbell":       {"name": "ティンカー・ベルのビジーバギー",             "area": "FS",  "ride_minutes": 3},
    "rapunzel":         {"name": "ラプンツェルのランタンフェスティバル",        "area": "FS",  "ride_minutes": 3},
    "frozen":           {"name": "アナとエルサのフローズンジャーニー",          "area": "FS",  "ride_minutes": 5},
    "big_city":         {"name": "ビッグシティ・ヴィークル",                  "area": "AW",  "ride_minutes": 5},
}

DEFAULT_RIDE_MINUTES = 5


def ride_minutes(attraction_id: str) -> int:
    return ATTRACTIONS.get(attraction_id, {}).get("ride_minutes", DEFAULT_RIDE_MINUTES)


def display_name(attraction_id: str) -> str:
    return ATTRACTIONS.get(attraction_id, {}).get("name", attraction_id)
