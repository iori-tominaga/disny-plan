"""
engine/optimizer.py — OR-Tools CP-SAT による時間枠付き巡回ルート最適化

定式化（TSPTW の変形）:
  - ノード = 入園ゲート(仮想) + 希望アトラクション群
  - AddCircuit で巡回順序を決定
  - 各アトラクションの待ち時間は「到着した時刻の予測値」を
    AddElement（テーブル参照制約）で参照する時間依存コスト
  - 目的関数 = 最終アトラクションの体験終了時刻の最小化

ハーバーショー補正:
  19〜21 時台は全体の待ち時間が緩和する傾向のため、
  該当時間帯の予測値に HARBOR_SHOW_BIAS を乗算してからソルバーに渡す。
"""
from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd
from ortools.sat.python import cp_model

from engine.park_data import ride_minutes

PARK_OPEN_HOUR  = 8
PARK_CLOSE_HOUR = 22

# ハーバーショー時間帯の待ち時間緩和係数
HARBOR_SHOW_HOURS = range(19, 22)
HARBOR_SHOW_BIAS  = 0.7

# 入園ゲートはメディテレーニアンハーバー側にあるため、
# 同エリアの fortress を距離計算の代理ノードとして使う（+ゲート通過3分）
_ENTRANCE_PROXY = "fortress"
_GATE_MINUTES   = 3

_DEFAULT_WALK = 15
_DEFAULT_WAIT = 30
_SOLVER_TIME_LIMIT_SEC = 10


class RouteInfeasibleError(Exception):
    """滞在時間枠内に全アトラクションを巡回できない場合に送出。"""


def _load_walk_matrix(conn: sqlite3.Connection) -> dict[tuple[str, str], int]:
    rows = conn.execute(
        "SELECT from_attraction, to_attraction, walk_minutes FROM movement_matrix"
    ).fetchall()
    return {(f, t): w for f, t, w in rows}


def _build_wait_tables(
    target_attractions: list[str],
    predicted_waits: pd.DataFrame,
) -> list[list[int]]:
    """アトラクションごとに hour=8..22 の待ち時間テーブル（バイアス適用済み）を作る。"""
    tables = []
    for aid in target_attractions:
        row = []
        for h in range(PARK_OPEN_HOUR, PARK_CLOSE_HOUR + 1):
            try:
                w = float(predicted_waits.loc[(aid, h), "wait_median"])
            except KeyError:
                w = _DEFAULT_WAIT
            if h in HARBOR_SHOW_HOURS:
                w *= HARBOR_SHOW_BIAS
            row.append(int(round(w)))
        tables.append(row)
    return tables


def optimize_route(
    conn: sqlite3.Connection,
    target_attractions: list[str],
    predicted_waits: pd.DataFrame,
    start_hour: int,
    end_hour: int,
) -> list[dict[str, Any]]:
    """
    最適巡回ルートを計算する。

    Returns
    -------
    list[dict]
        巡回順の各ステップ:
        {attraction_id, walk_from_prev, arrive_at, wait_minutes,
         ride_minutes, depart_at}（時刻はすべて分単位、0:00起点）

    Raises
    ------
    RouteInfeasibleError
        時間枠内に全アトラクションを巡回できない場合。
    """
    start_hour = max(start_hour, PARK_OPEN_HOUR)
    end_hour   = min(end_hour, PARK_CLOSE_HOUR)
    start_min, end_min = start_hour * 60, end_hour * 60

    n = len(target_attractions)
    if n == 0:
        return []

    walk = _load_walk_matrix(conn)
    tables = _build_wait_tables(target_attractions, predicted_waits)
    rides = [ride_minutes(a) for a in target_attractions]

    model = cp_model.CpModel()

    # ── ノード0=入園ゲート、1..n=アトラクション ────────────────────
    N = n + 1
    lit: dict[tuple[int, int], cp_model.IntVar] = {}
    arcs = []
    for i in range(N):
        for j in range(N):
            if i == j:
                continue
            l = model.NewBoolVar(f"arc_{i}_{j}")
            lit[(i, j)] = l
            arcs.append((i, j, l))
    model.AddCircuit(arcs)

    # ── 時刻変数（分） ─────────────────────────────────────────────
    arrival, wait_v, depart = [], [], []
    for k in range(n):
        a = model.NewIntVar(start_min, end_min, f"arr_{k}")
        # 到着時刻の「時」でテーブルを引く: idx = arrival//60 - 8
        hh  = model.NewIntVar(start_hour, end_hour, f"hh_{k}")
        model.AddDivisionEquality(hh, a, 60)
        idx = model.NewIntVar(0, PARK_CLOSE_HOUR - PARK_OPEN_HOUR, f"idx_{k}")
        model.Add(idx == hh - PARK_OPEN_HOUR)
        w = model.NewIntVar(0, 180, f"wait_{k}")
        model.AddElement(idx, tables[k], w)

        d = model.NewIntVar(start_min, end_min, f"dep_{k}")
        model.Add(d == a + w + rides[k])

        arrival.append(a)
        wait_v.append(w)
        depart.append(d)

    # ── 移動時間制約 ───────────────────────────────────────────────
    def walk_min(a_from: str, a_to: str) -> int:
        return walk.get((a_from, a_to), _DEFAULT_WALK)

    for j in range(n):
        ent = walk_min(_ENTRANCE_PROXY, target_attractions[j]) + _GATE_MINUTES
        model.Add(arrival[j] >= start_min + ent).OnlyEnforceIf(lit[(0, j + 1)])

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            wm = walk_min(target_attractions[i], target_attractions[j])
            model.Add(arrival[j] >= depart[i] + wm).OnlyEnforceIf(lit[(i + 1, j + 1)])
    # ゲートへ戻るアーク (i+1, 0) は終了を意味するだけなので制約なし

    # ── 目的関数: 最終体験終了時刻の最小化 ─────────────────────────
    makespan = model.NewIntVar(start_min, end_min, "makespan")
    model.AddMaxEquality(makespan, depart)
    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = _SOLVER_TIME_LIMIT_SEC
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RouteInfeasibleError(
            f"{start_hour}時〜{end_hour}時の枠内に {n} 件すべてを巡回する"
            "ルートが見つかりませんでした。滞在時間を延ばすか、"
            "アトラクションを減らしてください。"
        )

    # ── 巡回順の復元（ゲートから順にアークを辿る） ──────────────────
    nxt = {i: j for (i, j), l in lit.items() if solver.Value(l) == 1}
    schedule: list[dict[str, Any]] = []
    prev_node, node = 0, nxt[0]
    while node != 0:
        k = node - 1
        if prev_node == 0:
            wm = walk_min(_ENTRANCE_PROXY, target_attractions[k]) + _GATE_MINUTES
        else:
            wm = walk_min(target_attractions[prev_node - 1], target_attractions[k])
        schedule.append({
            "attraction_id":  target_attractions[k],
            "walk_from_prev": wm,
            "arrive_at":      solver.Value(arrival[k]),
            "wait_minutes":   solver.Value(wait_v[k]),
            "ride_minutes":   rides[k],
            "depart_at":      solver.Value(depart[k]),
        })
        prev_node, node = node, nxt[node]

    return schedule
