"""Authentication routes: register, login, refresh, logout, profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import User, get_session
from ..schemas import (
    LoginIn, PreferencesIn, RefreshIn, RegisterIn, TokenOut, UserOut,
)
from ..security import (
    audit, create_access_token, get_current_user, hash_password,
    new_refresh_token, redeem_refresh_token, store_refresh_token, verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, name=user.name,
        role=user.role, preferences=user.preferences or {},
    )


async def _issue_tokens(session: AsyncSession, user: User) -> TokenOut:
    access = create_access_token(user.id, user.role)
    raw_refresh, token_hash = new_refresh_token()
    await store_refresh_token(session, user.id, token_hash)
    return TokenOut(access_token=access, refresh_token=raw_refresh, user=_user_out(user))


@router.post("/register", response_model=TokenOut)
async def register(body: RegisterIn, request: Request, session: AsyncSession = Depends(get_session)):
    if not settings.allow_registration:
        # Still allow the very first user (owner bootstrap).
        existing = (await session.execute(select(User).limit(1))).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=403, detail="Registration is disabled")
    dupe = (
        await session.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    if dupe is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    is_first = (await session.execute(select(User).limit(1))).scalar_one_or_none() is None
    user = User(
        email=body.email.lower(), name=body.name,
        password_hash=hash_password(body.password),
        role="owner" if is_first else "member",
    )
    session.add(user)
    await session.commit()
    await audit("user.register", user.id, request.client.host if request.client else "", email=user.email)
    return await _issue_tokens(session, user)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, session: AsyncSession = Depends(get_session)):
    user = (
        await session.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        await audit("user.login_failed", None, request.client.host if request.client else "", email=body.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    await audit("user.login", user.id, request.client.host if request.client else "")
    return await _issue_tokens(session, user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, session: AsyncSession = Depends(get_session)):
    user = await redeem_refresh_token(session, body.refresh_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return await _issue_tokens(session, user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.put("/preferences", response_model=UserOut)
async def update_preferences(
    body: PreferencesIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    merged = {**(user.preferences or {}), **body.preferences}
    user.preferences = merged
    await session.commit()
    return _user_out(user)
