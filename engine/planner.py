"""
engine/planner.py — フルデイプラン生成

1. 必須アトラクションを「1日でいちばん空いているタイミング」に配置
   （optimizer の min_wait 目的関数を使用）
2. 空いた時間に「いま行くとお得・近くて効率的」なアトラクションを自動挿入
3. 食事どきの空き時間にはランチ・ディナー休憩を自動で組み込む
4. それでも残る空き時間はショー鑑賞・ショッピング提案カードにする

プラン要素の type:
  "must"      — ユーザーが選んだ必須アトラクション
  "recommend" — 自動挿入されたおすすめアトラクション（reason 付き）
  "meal"      — 食事休憩
  "free"      — ショー鑑賞・ショッピングなどの自由時間提案
"""
from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from engine.optimizer import (
    HARBOR_SHOW_BIAS,
    HARBOR_SHOW_HOURS,
    PARK_CLOSE_HOUR,
    PARK_OPEN_HOUR,
    _ENTRANCE_PROXY,
    _GATE_MINUTES,
    _load_walk_matrix,
    optimize_route,
)
from engine.park_data import ride_minutes

_DEFAULT_WALK   = 15
_MIN_FREE_BLOCK = 25   # これ以上の残り空き時間は「自由時間」カードにする
_MEAL_MINUTES   = 45

# (開始可能, 終了期限, 種別) — この窓に空きがあれば食事を入れる
_MEAL_WINDOWS = [
    (11 * 60 + 30, 14 * 60, "lunch"),
    (17 * 60 + 30, 20 * 60, "dinner"),
]
_MEAL_LABELS = {"lunch": "🍽️ ランチ休憩", "dinner": "🍽️ ディナー休憩"}


def _wait_at(waits: pd.DataFrame, aid: str, minute: int) -> int | None:
    """その時刻の予測待ち時間（ハーバーショー補正込み）。データなしは None。"""
    hour = min(max(minute // 60, PARK_OPEN_HOUR), PARK_CLOSE_HOUR)
    try:
        w = float(waits.loc[(aid, hour), "wait_median"])
    except KeyError:
        return None
    if hour in HARBOR_SHOW_HOURS:
        w *= HARBOR_SHOW_BIAS
    return int(round(w))


def _daily_median(waits: pd.DataFrame, aid: str) -> float:
    try:
        return float(waits.loc[aid]["wait_median"].median())
    except KeyError:
        return 0.0


def _reason(saving: int, wait: int) -> str:
    if saving >= 15:
        return f"いつもより約{saving}分も空いてる狙い目！"
    if wait <= 20:
        return f"待ち{wait}分でサクッと体験！"
    return "ルートの途中で効率よく回れる！"


class _GapFiller:
    """1日のすき間時間におすすめ・食事・自由時間を詰めるヘルパー。"""

    def __init__(
        self,
        candidates: list[str],
        waits: pd.DataFrame,
        walk: dict[tuple[str, str], int],
        used: set[str],
    ):
        self.candidates = candidates
        self.waits = waits
        self.walk = walk
        self.used = used
        self.meals_taken: set[str] = set()

    def wk(self, a: str, b: str) -> int:
        if a == "ENTRANCE":
            return self.walk.get((_ENTRANCE_PROXY, b), _DEFAULT_WALK) + _GATE_MINUTES
        return self.walk.get((a, b), _DEFAULT_WALK)

    def _try_meal(self, t: int, limit: int) -> dict[str, Any] | None:
        for win_start, win_end, kind in _MEAL_WINDOWS:
            if kind in self.meals_taken:
                continue
            begin = max(t, win_start)
            # 現在時刻が食事時間帯に達しているときだけ挿入する（時間の飛び越え防止）
            if begin - t > 15:
                continue
            if begin + _MEAL_MINUTES <= min(limit, win_end):
                self.meals_taken.add(kind)
                return {
                    "type":      "meal",
                    "label":     _MEAL_LABELS[kind],
                    "arrive_at": begin,
                    "depart_at": begin + _MEAL_MINUTES,
                }
        return None

    def _best_ride(
        self, t: int, loc: str, limit: int, next_loc: str | None
    ) -> dict[str, Any] | None:
        best, best_key = None, None
        for aid in self.candidates:
            if aid in self.used:
                continue
            wm = self.wk(loc, aid)
            arrive = t + wm
            w = _wait_at(self.waits, aid, arrive)
            if w is None:
                continue
            depart = arrive + w + ride_minutes(aid)
            back = self.wk(aid, next_loc) if next_loc else 0
            if depart + back > limit:
                continue
            saving = int(round(_daily_median(self.waits, aid) - w))
            # お得さを重視しつつ、遠回り・長時間待ちにはペナルティ
            key = saving - 1.5 * wm - 0.5 * w
            if best_key is None or key > best_key:
                best_key = key
                best = {
                    "type":           "recommend",
                    "attraction_id":  aid,
                    "walk_from_prev": wm,
                    "arrive_at":      arrive,
                    "wait_minutes":   w,
                    "ride_minutes":   ride_minutes(aid),
                    "depart_at":      depart,
                    "reason":         _reason(saving, w),
                }
        return best

    def fill(
        self, t: int, loc: str, limit: int, next_loc: str | None
    ) -> tuple[list[dict[str, Any]], int, str]:
        """t〜limit を埋める。(挿入カード列, 更新時刻, 更新現在地) を返す。"""
        out: list[dict[str, Any]] = []
        while True:
            meal = self._try_meal(t, limit)
            if meal:
                out.append(meal)
                t = meal["depart_at"]
                continue
            ride = self._best_ride(t, loc, limit, next_loc)
            if ride is None:
                break
            out.append(ride)
            self.used.add(ride["attraction_id"])
            t, loc = ride["depart_at"], ride["attraction_id"]
        return out, t, loc


def _free_block(start: int, end: int) -> dict[str, Any] | None:
    if end - start < _MIN_FREE_BLOCK:
        return None
    h = start // 60
    if h >= 19:
        label = "🎆 ハーバーの夜ショーを鑑賞✨"
    else:
        label = "🛍️ おみやげ＆グリーティングタイム"
    return {"type": "free", "label": label, "arrive_at": start, "depart_at": end}


def build_full_plan(
    conn: sqlite3.Connection,
    must_attractions: list[str],
    predicted_waits: pd.DataFrame,
    start_hour: int = 9,
    end_hour: int = 21,
) -> list[dict[str, Any]]:
    """
    必須アトラクション＋おすすめ＋食事＋自由時間のフルデイプランを返す。
    """
    must = optimize_route(
        conn, must_attractions, predicted_waits,
        start_hour, end_hour, objective="min_wait",
    )
    for s in must:
        s["type"] = "must"

    walk = _load_walk_matrix(conn)
    all_ids = predicted_waits.index.get_level_values("attraction_id").unique().tolist()
    used = set(must_attractions)
    filler = _GapFiller(
        [a for a in all_ids if a not in used], predicted_waits, walk, used
    )

    start_min = max(start_hour, PARK_OPEN_HOUR) * 60
    end_min   = min(end_hour, PARK_CLOSE_HOUR) * 60

    plan: list[dict[str, Any]] = []
    t, loc = start_min, "ENTRANCE"

    for s in must:
        cards, t, loc = filler.fill(t, loc, s["arrive_at"], s["attraction_id"])
        plan.extend(cards)

        wk_to_next = filler.wk(loc, s["attraction_id"])
        fb = _free_block(t, s["arrive_at"] - wk_to_next)
        if fb:
            plan.append(fb)
            t = fb["depart_at"]

        s["walk_from_prev"] = wk_to_next
        plan.append(s)
        t, loc = s["depart_at"], s["attraction_id"]

    cards, t, loc = filler.fill(t, loc, end_min, None)
    plan.extend(cards)
    fb = _free_block(t, end_min)
    if fb:
        plan.append(fb)

    return plan
