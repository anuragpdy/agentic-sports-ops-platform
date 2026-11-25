"""Allowed values for status-like columns: the single source of truth.

The database CHECK constraints (app.db.models) and the Pydantic models are both built from
these Literal types, so the two can't drift apart. Changing a list here needs a migration.
"""

from typing import Literal

AccountStatus = Literal["active", "suspended", "closed"]
DepositMethod = Literal["card", "upi", "bank", "wallet"]
BetStatus = Literal["open", "won", "lost", "void"]
AlertSeverity = Literal["low", "medium", "high"]
CaseStatus = Literal["open", "investigating", "closed"]
FraudLabel = Literal["fraud", "benign"]
