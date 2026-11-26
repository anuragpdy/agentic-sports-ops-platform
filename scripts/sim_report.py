"""Simulator report: where alerts land, and how often ordinary customers look like fraud.

Usage: uv run python scripts/sim_report.py [--seed 42] [--accounts 5000]

A dev tool for tuning the simulator (not a test, not used by the app). It reads the
registry, so it can see the answer key; never use it as an input to the alert rules.
"""

import argparse
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from app.schemas.create import AlertCreate
from app.sim.build import SimResult, generate
from app.sim.config import SimConfig
from app.sim.signals import BIG_STAKE_MINOR, LONG_ODDS, QUIET_DAYS, Rows, measure
from app.sim.stories import F1_SIGNALS, F2_SIGNALS, PlantedStory

COLUMNS = ["F1 in-ep", "F2 in-ep", "F outside", "L1", "L2", "ordinary"]


def bucket(alert: AlertCreate, story: dict[uuid.UUID, PlantedStory]) -> str:
    s = story.get(alert.account_id)
    if s is None:
        return "ordinary"
    if s.story in ("L1", "L2"):
        return s.story
    inside = s.episode_start <= alert.created_at <= s.episode_end
    return f"{s.story} in-ep" if inside else "F outside"


def alert_table(result: SimResult) -> None:
    story = {s.account_id: s for s in result.registry}
    by_rule: dict[str, Counter[str]] = defaultdict(Counter)
    for a in result.alerts:
        by_rule[a.rule][bucket(a, story)] += 1
    total: Counter[str] = Counter()
    for counts in by_rule.values():
        total.update(counts)

    print(f"{'rule':22}{'total':>7}" + "".join(f"{c:>11}" for c in COLUMNS))
    for rule in sorted(by_rule):
        c = by_rule[rule]
        print(f"{rule:22}{sum(c.values()):>7}" + "".join(f"{c[k]:>11}" for k in COLUMNS))
    n = sum(total.values())
    print(f"{'ALL':22}{n:>7}" + "".join(f"{total[k]:>11}" for k in COLUMNS))
    fraud = total["F1 in-ep"] + total["F2 in-ep"]
    lookalike = total["L1"] + total["L2"]
    print(
        f"\nmix: fraud-in-episode {fraud / n:.1%} · look-alikes {lookalike / n:.1%} · "
        f"ordinary {total['ordinary'] / n:.1%} · fraud outside episode {total['F outside'] / n:.1%}"
    )

    alerted = {a.account_id for a in result.alerts}
    for name in ("F1", "L1", "F2", "L2"):
        ids = [s.account_id for s in result.registry if s.story == name]
        print(f"  {name}: {sum(i in alerted for i in ids)}/{len(ids)} accounts alerted")
    ordinary = [a.id for a in result.population.accounts if a.id not in story]
    print(f"  ordinary: {sum(i in alerted for i in ordinary)}/{len(ordinary)} accounts alerted")


def ordinary_full_combinations(result: SimResult) -> None:
    """Ordinary accounts that, somewhere in their history, show a full F1 or F2 combination.

    Candidate windows (ordinary accounts have no episode):
    - F1: each bet with a big stake at long odds; window = the 2 hours up to that bet.
    - F2: each first event after >= QUIET_DAYS of silence; window = the next 3 days.
    """
    rows = Rows(result.population)
    planted = {s.account_id for s in result.registry}
    f1_hits: set[uuid.UUID] = set()
    f2_hits: set[uuid.UUID] = set()

    for account_id in rows.accounts:
        if account_id in planted:
            continue
        for b in rows.bets[account_id]:
            if b.stake_minor >= BIG_STAKE_MINOR and b.odds >= LONG_ODDS:
                window = _window(account_id, b.placed_at - timedelta(hours=2), b.placed_at)
                if measure(rows, window) >= F1_SIGNALS:
                    f1_hits.add(account_id)
        times = sorted(
            [d.created_at for d in rows.deposits[account_id]]
            + [b.placed_at for b in rows.bets[account_id]]
        )
        for before, after in zip(times, times[1:], strict=False):
            if after - before >= timedelta(days=QUIET_DAYS):
                window = _window(account_id, after, after + timedelta(days=3))
                if measure(rows, window) >= F2_SIGNALS:
                    f2_hits.add(account_id)

    n = len(rows.accounts) - len(planted)
    print(f"\nordinary accounts showing a full F1 combination: {len(f1_hits)}/{n}")
    print(f"ordinary accounts showing a full F2 combination: {len(f2_hits)}/{n}")


def _window(account_id: uuid.UUID, start: datetime, end: datetime) -> PlantedStory:
    # `measure` takes a story-shaped window; story/signals are unused for the measurement.
    return PlantedStory(account_id, "F1", start, end, frozenset())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--accounts", type=int, default=SimConfig().accounts)
    args = parser.parse_args()

    started = time.perf_counter()
    result = generate(args.seed, SimConfig(accounts=args.accounts))
    took = time.perf_counter() - started
    pop = result.population
    print(
        f"seed {args.seed}, {args.accounts} accounts: generated in {took:.2f} s · "
        f"{len(pop.deposits)} deposits · {len(pop.bets)} bets · {len(result.alerts)} alerts\n"
    )
    alert_table(result)
    ordinary_full_combinations(result)


if __name__ == "__main__":
    main()
