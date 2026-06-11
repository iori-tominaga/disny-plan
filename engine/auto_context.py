"""
engine/auto_context.py — ターゲット日の環境情報を外部から自動取得

ユーザー入力は「日付」だけでよい。以下を自動で導出する:
  - 天気・気温   : Open-Meteo API（無料・キー不要、舞浜の座標で16日先まで予報）
                   予報範囲外の日付は月別の平年値にフォールバック
  - 祝日・長期休み: jpholiday（国民の祝日）＋ 学校休暇期間ルール
  - イベント     : TDS の季節イベント開催パターン（DB のイベント名にマッピング）
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import requests

# 東京ディズニーシーの座標
_LAT, _LON = 35.6267, 139.8851
_FORECAST_DAYS = 16

# 月別平年値（最高気温, 最低気温）— 予報範囲外のフォールバック
_CLIMATE_NORMALS = {
    1: (9, 2), 2: (10, 3), 3: (14, 6), 4: (19, 11), 5: (24, 16), 6: (27, 20),
    7: (31, 25), 8: (33, 26), 9: (28, 21), 10: (22, 14), 11: (17, 9), 12: (12, 4),
}

# TDS 季節イベントの開催パターン（月日ベース）→ DB に存在するイベント名
_EVENT_SEASONS = [
    ((7, 1),  (8, 31),  "サマーフェスティバル2024"),
    ((9, 2),  (10, 31), "ディズニー・ハロウィーン2024"),
    ((11, 1), (12, 25), "ディズニー・クリスマス2024"),
    ((12, 26), (12, 31), "ディズニー・ニューイヤーズ・カウントダウン"),
    ((1, 1),  (1, 7),   "ディズニー・ニューイヤーズ・カウントダウン"),
    ((3, 20), (4, 20),  "ディズニー・イースター2025"),
]

# 学校の長期休暇（月日ベース）
_SCHOOL_VACATIONS = [
    ((7, 20), (8, 31)),   # 夏休み
    ((12, 23), (12, 31)), # 冬休み（年内）
    ((1, 1), (1, 7)),     # 冬休み（年明け）
    ((3, 21), (4, 7)),    # 春休み
]


def _in_md_range(d: date, start_md: tuple, end_md: tuple) -> bool:
    md = (d.month, d.day)
    return start_md <= md <= end_md


def _weathercode_to_label(code: int) -> str:
    if code in (0, 1):
        return "晴"
    if code in (2, 3, 45, 48):
        return "曇"
    if code in (71, 73, 75, 77, 85, 86):
        return "雪"
    return "雨"


def _fetch_forecast(target: date) -> dict | None:
    """Open-Meteo から予報を取得。範囲外・通信失敗なら None。"""
    if not (date.today() <= target <= date.today() + timedelta(days=_FORECAST_DAYS)):
        return None
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": _LAT,
                "longitude": _LON,
                "daily": "weathercode,temperature_2m_max,temperature_2m_min",
                "timezone": "Asia/Tokyo",
                "start_date": target.isoformat(),
                "end_date": target.isoformat(),
            },
            timeout=8,
        )
        r.raise_for_status()
        daily = r.json()["daily"]
        return {
            "weather":  _weathercode_to_label(int(daily["weathercode"][0])),
            "temp_max": float(daily["temperature_2m_max"][0]),
            "temp_min": float(daily["temperature_2m_min"][0]),
            "source":   "forecast",
        }
    except Exception:
        return None


def _is_holiday_or_vacation(target: date) -> bool:
    try:
        import jpholiday
        if jpholiday.is_holiday(target):
            return True
    except Exception:
        pass
    return any(_in_md_range(target, s, e) for s, e in _SCHOOL_VACATIONS)


def _event_for(target: date) -> str | None:
    for start_md, end_md, name in _EVENT_SEASONS:
        if _in_md_range(target, start_md, end_md):
            return name
    return None


def build_auto_context(target_date: str) -> dict[str, Any]:
    """
    日付文字列(YYYY-MM-DD)から環境情報をすべて自動導出する。

    Returns
    -------
    dict
        weather, temp_max, temp_min, is_holiday, event_name,
        weather_source ("forecast"=API予報 / "climate"=平年値)
    """
    target = date.fromisoformat(target_date)

    wx = _fetch_forecast(target)
    if wx is None:
        th, tl = _CLIMATE_NORMALS[target.month]
        wx = {"weather": "晴", "temp_max": float(th), "temp_min": float(tl),
              "source": "climate"}

    return {
        "weather":        wx["weather"],
        "temp_max":       wx["temp_max"],
        "temp_min":       wx["temp_min"],
        "weather_source": wx["source"],
        "is_holiday":     int(_is_holiday_or_vacation(target)),
        "event_name":     _event_for(target),
    }
