#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_bench.py  ―  轻量级 benchmark / profile 驱动脚本

示例：
    python -m cProfile -o freck.prof -s cumulative run_bench.py \
        --iters 150 --runs 5 -w 8 --seed 42
"""
from __future__ import annotations

import argparse
import random
import time
import statistics as stats
from pathlib import Path
import sys

# === 修改此行以对应你代码在包内的位置 =========================
# 假设你的 MCTS / GameState 放在 agent/program.py
# --------------------------------------------------------------
sys.path.append(str(Path(__file__).resolve().parent))          # 项目根进 PYTHONPATH
from agent.program import GameState, MCTS                      # noqa: E402
from referee.game import Board                                 # noqa: E402
# =============================================================

# ---------- util -------------------------------------------------------------


def play_random_moves(state: GameState, steps: int) -> GameState:
    """随机合法动作把棋盘推进 `steps` 步（不分胜负，只为了热身）"""
    current = state
    for _ in range(steps):
        if current.is_terminal():
            break
        actions = list(current.get_legal_actions())
        if not actions:      # 极端情况
            break
        act = random.choice(actions)
        current = current.move(act)
    return current


# ---------- main -------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iters", type=int, default=200,
                        help="MCTS iterations per search (default: 200)")
    parser.add_argument("--runs", type=int, default=3,
                        help="Independent searches to run (default: 3)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed (default: None)")
    parser.add_argument("-w", "--warmup", type=int, default=0,
                        help="Random moves before each run (default: 0)")
    parser.add_argument("--no-minimax", action="store_true",
                        help="Turn OFF hybrid Minimax simulation")
    parser.add_argument("--minimax-depth", type=int, default=3,
                        help="Depth for hybrid Minimax (default: 3)")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    # —— 初始棋盘，用裁判提供的 Board() 即标准开局 ——
    init_state = GameState(None, Board())

    print(f"[bench] iters={args.iters}, runs={args.runs}, "
          f"warmup={args.warmup}, minimax={'off' if args.no_minimax else 'on'} "
          f"(depth={args.minimax_depth})")

    wall_times: list[float] = []
    for run_idx in range(1, args.runs + 1):
        state = (play_random_moves(init_state, args.warmup)
                 if args.warmup else init_state)

        mcts = MCTS(state,
                    use_minimax=not args.no_minimax,
                    minimax_depth=args.minimax_depth)

        t0 = time.perf_counter()
        best_action = mcts.search(iterations=args.iters)
        wall_times.append(time.perf_counter() - t0)

        print(f"  run {run_idx:2d}: {wall_times[-1]:.4f}s   "
              f"best_action={best_action}")

    print("\n=== summary ===")
    print(f"mean   {stats.mean(wall_times):.4f}s")
    print(f"stdev  {stats.stdev(wall_times) if len(wall_times) > 1 else 0:.4f}s")
    print(f"min / max  {min(wall_times):.4f}s  /  {max(wall_times):.4f}s")


# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
