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
    # "card" means debit card: credit cards can't fund online wagering in Australia.
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

    @property
    def end(self) -> datetime:
        return START + timedelta(days=self.days)
