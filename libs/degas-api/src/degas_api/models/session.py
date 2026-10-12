from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Field, SQLModel


class OptimizationSession(SQLModel, table=True):
    __tablename__ = "optimization_sessions"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    expires_at: datetime

    owner_token: str = Field(default="")  # set on create, used to authorize rename/delete
    name: str | None = Field(default=None)  # user-supplied display name

    # UI state needed to restore the editors
    loss_mode: str  # "builtin" | "custom"
    loss_name: str

    # Full OptimizationRequest as JSON (program, loss_source, optimizer, params…)
    request: str

    # Compact step array JSON: [{step, loss, params, elapsed_ms, dist}]
    steps: str = Field(default="[]")

    status: str = Field(default="running")  # running | done | error | aborted
    outcome: str | None = Field(default=None)

    def bump_ttl(self, days: int) -> None:
        self.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            days=days
        )
