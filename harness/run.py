"""CLI: run harness levels against one or more models and print a scoreboard.

  python -m harness.run --model $WEAK_MODEL --level 2              # one live run
  python -m harness.run --model $WEAK_MODEL --model $STRONG_MODEL \
                        --level 0 1 2 3 --trials 5 --quiet --jobs 4  # the benchmark
"""

import argparse
import asyncio
import os
from collections import defaultdict

from .levels import LEVELS, RunResult, run_level


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--model", action="append",
                   help="model id (repeatable). Defaults to $WEAK_MODEL.")
    p.add_argument("--level", type=int, nargs="+", default=[0, 1, 2, 3], choices=sorted(LEVELS))
    p.add_argument("--trials", type=int, default=1)
    p.add_argument("--jobs", type=int, default=1, help="runs in parallel")
    p.add_argument("--quiet", action="store_true", help="hide per-run transcripts")
    args = p.parse_args()
    args.model = args.model or [m for m in [os.environ.get("WEAK_MODEL")] if m]
    if not args.model:
        p.error("pass --model or set WEAK_MODEL")
    return args


def summarize(results: list[RunResult]):
    by_cell = defaultdict(list)
    for r in results:
        by_cell[(r.model, r.level)].append(r)

    print("\n" + "=" * 92)
    print(f"{'model':<24}{'level':<20}{'solved':>8}{'avg tests':>12}"
          f"{'avg turns':>11}{'avg $':>9}{'avg s':>8}")
    print("-" * 92)
    for (model, level), rs in sorted(by_cell.items()):
        n = len(rs)
        solved = sum(r.grade.ok for r in rs)
        total = rs[0].grade.total or 1
        tests = sum(r.grade.passed for r in rs) / n
        print(f"{model:<24}{f'L{level} {LEVELS[level]}':<20}{f'{solved}/{n}':>8}"
              f"{f'{tests:.0f}/{total}':>12}{sum(r.turns for r in rs) / n:>11.1f}"
              f"{sum(r.cost_usd for r in rs) / n:>9.3f}{sum(r.seconds for r in rs) / n:>8.0f}")
    print("=" * 92)


async def main():
    args = parse_args()
    jobs = [(m, lvl, t) for m in args.model for lvl in args.level for t in range(args.trials)]
    sem = asyncio.Semaphore(args.jobs)
    verbose = not args.quiet and args.jobs == 1

    async def one(model, level, trial):
        async with sem:
            if verbose:
                print(f"\n▶ {model} | L{level} {LEVELS[level]} | trial {trial + 1}")
            r = await run_level(level, model, verbose=verbose)
            print(f"  {'✅' if r.grade.ok else '❌'} {model} L{level} #{trial + 1}: "
                  f"{r.grade.passed}/{r.grade.total} tests, {r.turns} turns, "
                  f"{r.gate_blocks} gate blocks, ${r.cost_usd:.3f}")
            return r

    results = await asyncio.gather(*(one(*j) for j in jobs))
    summarize(results)


if __name__ == "__main__":
    asyncio.run(main())
