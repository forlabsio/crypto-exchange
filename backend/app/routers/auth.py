import re
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse,
    MetaMaskNonceRequest, MetaMaskVerifyRequest,
)
from app.core.security import hash_password, verify_password, create_access_token
from app.services.metamask import generate_nonce, verify_signature, get_login_message

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(400, "Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()
    db.add(Wallet(user_id=user.id, asset="USDT", balance=10000))
    await db.commit()
    return {"message": "registered"}

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.id))

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_subscribed": user.is_subscribed,
        "wallet_address": user.wallet_address,
    }


@router.post("/metamask/nonce")
async def metamask_nonce(body: MetaMaskNonceRequest, db: AsyncSession = Depends(get_db)):
    """Return a nonce for the given wallet address to sign."""
    address = body.address.lower().strip()
    if not re.match(r"^0x[0-9a-f]{40}$", address):
        raise HTTPException(400, "Invalid wallet address")

    nonce = generate_nonce()
    now = datetime.now(timezone.utc)

    # Find or create user by wallet_address
    user = await db.scalar(select(User).where(User.wallet_address == address))
    if not user:
        try:
            user = User(wallet_address=address, nonce=nonce, nonce_created_at=now,
                        email=None, password_hash=None)
            db.add(user)
            await db.flush()
            db.add(Wallet(user_id=user.id, asset="USDT", balance=0))
        except IntegrityError:
            await db.rollback()
            user = await db.scalar(select(User).where(User.wallet_address == address))
            user.nonce = nonce
            user.nonce_created_at = now
    else:
        user.nonce = nonce
        user.nonce_created_at = now
    await db.commit()
    return {"nonce": nonce, "message": get_login_message(nonce)}


@router.post("/metamask/verify", response_model=TokenResponse)
async def metamask_verify(body: MetaMaskVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Verify MetaMask signature and return JWT."""
    address = body.address.lower().strip()
    signature = body.signature.strip()

    user = await db.scalar(select(User).where(User.wallet_address == address))
    if not user or not user.nonce:
        raise HTTPException(404, "Address not found — call /nonce first")

    nonce_created_at = user.nonce_created_at
    if nonce_created_at is None:
        raise HTTPException(400, "Nonce expired — call /nonce again")
    # Make timezone-aware if naive (SQLite returns naive datetimes)
    if nonce_created_at.tzinfo is None:
        nonce_created_at = nonce_created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - nonce_created_at > timedelta(minutes=10):
        raise HTTPException(400, "Nonce expired — call /nonce again")

    if not verify_signature(address, user.nonce, signature):
        raise HTTPException(401, "Invalid signature")

    # Invalidate nonce after use
    user.nonce = None
    user.nonce_created_at = None
    await db.commit()

    return TokenResponse(access_token=create_access_token(user.id))
