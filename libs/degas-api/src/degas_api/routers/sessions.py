from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from degas_api.db import get_db
from degas_api.models.session import OptimizationSession
from degas_api.settings import app_settings
from loguru import logger

router = APIRouter(prefix="/sessions", tags=["sessions"])

DbSession = Annotated[Session, Depends(get_db)]


def degas_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CreateSessionRequest(BaseModel):
    loss_mode: str
    loss_name: str
    request: str  # full OptimizationRequest JSON


class PatchSessionRequest(BaseModel):
    steps: list | None = None
    status: str | None = None
    outcome: str | None = None
    name: str | None = None  # requires X-Owner-Token header


class SessionResponse(BaseModel):
    id: str
    created_at: datetime
    expires_at: datetime
    loss_mode: str
    loss_name: str
    name: str | None
    request: str
    steps: list
    status: str
    outcome: str | None


class SessionCreateResponse(SessionResponse):
    owner_token: str


class SessionSummary(BaseModel):
    id: str
    created_at: datetime
    loss_mode: str
    loss_name: str
    name: str | None
    status: str
    outcome: str | None


def _to_response(s: OptimizationSession) -> SessionResponse:
    return SessionResponse(
        id=s.id,
        created_at=s.created_at,
        expires_at=s.expires_at,
        loss_mode=s.loss_mode,
        loss_name=s.loss_name,
        name=s.name,
        request=s.request,
        steps=json.loads(s.steps),
        status=s.status,
        outcome=s.outcome,
    )


@router.post("", response_model=SessionCreateResponse, status_code=201)
def create_session(body: CreateSessionRequest, db: DbSession) -> SessionCreateResponse:
    token = secrets.token_urlsafe(16)
    session = OptimizationSession(
        id=secrets.token_urlsafe(6),
        expires_at=degas_now() + timedelta(days=app_settings.session_ttl_days),
        owner_token=token,
        loss_mode=body.loss_mode,
        loss_name=body.loss_name,
        request=body.request,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("session created id={}", session.id)
    base = _to_response(session)
    return SessionCreateResponse(**base.model_dump(), owner_token=token)


@router.get("", response_model=list[SessionSummary])
def list_sessions(db: DbSession, limit: int = 50) -> list[SessionSummary]:
    now = degas_now()
    rows = db.exec(
        select(OptimizationSession)
        .where(OptimizationSession.expires_at > now)
        .order_by(OptimizationSession.created_at.desc())
        .limit(min(limit, 100))
    ).all()
    return [
        SessionSummary(
            id=r.id,
            created_at=r.created_at,
            loss_mode=r.loss_mode,
            loss_name=r.loss_name,
            name=r.name,
            status=r.status,
            outcome=r.outcome,
        )
        for r in rows
    ]


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: DbSession) -> SessionResponse:
    row = db.get(OptimizationSession, session_id)
    if row is None or row.expires_at < degas_now():
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    row.bump_ttl(app_settings.session_ttl_days)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.patch("/{session_id}", response_model=SessionResponse)
def patch_session(
    session_id: str,
    body: PatchSessionRequest,
    db: DbSession,
    x_owner_token: str | None = Header(default=None),
) -> SessionResponse:
    row = db.get(OptimizationSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if body.name is not None:
        if not x_owner_token or row.owner_token != x_owner_token:
            raise HTTPException(status_code=403, detail="Invalid owner token.")
        row.name = body.name.strip() or None
    if body.steps is not None:
        row.steps = json.dumps(body.steps)
    if body.status is not None:
        row.status = body.status
    if body.outcome is not None:
        row.outcome = body.outcome
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    db: DbSession,
    x_owner_token: str | None = Header(default=None),
) -> None:
    row = db.get(OptimizationSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not x_owner_token or row.owner_token != x_owner_token:
        raise HTTPException(status_code=403, detail="Invalid owner token.")
    db.delete(row)
    db.commit()
