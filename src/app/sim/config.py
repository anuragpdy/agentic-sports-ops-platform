"""All simulator assumptions in one place, so a reviewer can see (and change) every number.

The book is modelled on the Australian market: one country (AU), one currency (AUD).
Every row still carries its currency column, so a multi-currency book needs no schema change.
Money values are in MAJOR units (dollars); the simulator converts to minor units (cents,
x100) when building rows. Medians/sigmas describe a log-normal
distribution: most values near the median, a long tail of larger ones, as with real stakes.
"""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.values import AccountStatus, DepositMethod

# Fixed start (D3): never now(), so the same seed gives the same timestamps forever.
START = datetime(2026, 1, 1, tzinfo=UTC)


class SimConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    accounts: int = Field(default=5_000, ge=1)
    days: int = Field(default=182, ge=30)

    # Accounts open between `history_days` before START and `last_signup_days` before the
    # end, so many customers are already established when the window starts.
    history_days: int = Field(default=365, ge=0)
    last_signup_days: int = Field(default=14, ge=1)

    country: str = "AU"
    currency: str = "AUD"
    # Assumed typical amounts for a recreational Australian sports bettor (whole dollars).
    deposit_median: float = Field(default=50, gt=0)  # A$50; long tail to a few hundred
    deposit_min: int = Field(default=10, ge=1)  # A$10: a usual minimum deposit
    stake_median: float = Field(default=10, gt=0)  # a typical customer's typical stake: A$10
    stake_min: int = Field(default=1, ge=1)  # A$1
    # Australia's 2024 ban covers credit cards and credit-linked wallets for online wagering,
    # so "card" = debit card and "wallet" = a debit/bank-funded wallet.
    method_weights: dict[DepositMethod, float] = {"card": 0.55, "bank": 0.30, "wallet": 0.15}
    status_weights: dict[AccountStatus, float] = {"active": 0.95, "suspended": 0.03, "closed": 0.02}

    # Fixture calendar: matches per day and kickoff hours (UTC, inclusive). 02-11 UTC is
    # about 12:00-21:00 in Sydney (AEST, UTC+10), so a match's UTC date is also its local
    # date and "weekend" means an Australian weekend. The calendar runs past the window's
    # end, so customers can bet on upcoming matches (open bets).
    calendar_extra_days: int = Field(default=3, ge=0)
    matches_weekday: int = Field(default=4, ge=1)
    matches_weekend: int = Field(default=12, ge=1)
    kickoff_hours: tuple[int, int] = (2, 11)
    settle_after_hours: int = 2

    # Ordinary customers.
    deposits_per_account: tuple[int, int] = (1, 12)
    bets_per_account: tuple[int, int] = (5, 60)
    deposit_sigma: float = 0.8  # spread of each deposit around deposit_median
    stake_profile_sigma: float = 0.7  # how much customers' typical stakes differ
    stake_bet_sigma: float = 0.4  # how much one customer's bets vary around their typical
    bet_lead_hours: tuple[int, int] = (1, 72)  # bet placed this long before kickoff
    odds_millis: tuple[int, int] = (1_200, 6_000)  # odds 1.200 to 6.000, in thousandths
    margin: str = "0.95"  # P(win) = margin / odds: a 5% bookmaker margin
    void_share: float = Field(default=0.02, ge=0, lt=1)
    long_odds_share: float = Field(default=0.01, ge=0, lt=1)  # ordinary long shots
    long_odds_millis: tuple[int, int] = (8_000, 25_000)  # "long odds" = 8.0 or more

    # --- Planted stories (S3; table in docs/cards/simulator.md) ---------------------------
    # Prevalence: share of all accounts per story, with a floor so M9 has enough to sample.
    fraud_share: float = Field(default=0.02, gt=0, lt=1)  # per fraud story (F1, F2)
    lookalike_share: float = Field(default=0.03, gt=0, lt=1)  # per look-alike (L1, L2)
    min_per_story: int = Field(default=50, ge=1)
    max_planted_share: float = Field(default=0.5, gt=0, le=1)  # most accounts stay ordinary

    new_account_days: int = 13  # N: created 0..13 days before the episode
    established_days: int = 60  # established: created at least this long before
    weekend_share_f1: float = 0.5  # F1 episodes on a weekend
    weekend_share_l1: float = 0.8  # L1 = busy match day, but not always a weekend

    # F1 deposit burst: 4-8 deposits in 10-30 min, then ONE big bet at long odds.
    f1_burst_deposits: tuple[int, int] = (4, 8)
    f1_burst_minutes: tuple[int, int] = (10, 30)
    f1_big_stake: tuple[int, int] = (300, 1_500)  # dollars
    f1_odds_millis: tuple[int, int] = (8_000, 25_000)

    # L1 busy match day: 3-6 deposits in 20-60 min, 2-4 bets that day; borrows at most ONE
    # signal (none/N/B/O/J in equal quotas), so no L1 has F1's full combination. J is not in
    # F1's signature but shows up in most F1s (small early bets, then the big one), so L1
    # must show it too or it would single out F1.
    l1_burst_deposits: tuple[int, int] = (3, 6)
    l1_burst_minutes: tuple[int, int] = (20, 60)
    l1_bets: tuple[int, int] = (2, 4)
    l1_big_stake: tuple[int, int] = (200, 600)
    l1_odds_millis: tuple[int, int] = (8_000, 15_000)
    l1_jump: tuple[int, int] = (8, 12)  # x own typical stake: clears the 5x-median test
    high_roller_stake_median: float = 150  # a high roller's typical stake (dollars)

    # F2 / L2: silent 50-90 days, then a return episode over 1-3 days.
    wake_gap_days: tuple[int, int] = (50, 90)
    wake_earliest_day: int = 130  # episode >= START + 130 d, so there is history before
    wake_deposits: tuple[int, int] = (1, 2)
    wake_bets: tuple[int, int] = (2, 4)
    f2_jump: tuple[int, int] = (15, 40)  # stakes x own typical
    f2_odds_millis: tuple[int, int] = (8_000, 20_000)
    # L2 borrows at most ONE F2 signal (none/J/O in equal quotas); 30% are high rollers.
    l2_jump: tuple[int, int] = (5, 8)
    l2_odds_millis: tuple[int, int] = (8_000, 15_000)
    l2_high_roller_share: float = 0.3

    @property
    def end(self) -> datetime:
        return START + timedelta(days=self.days)
