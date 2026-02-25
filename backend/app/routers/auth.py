from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
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
async def metamask_nonce(body: dict, db: AsyncSession = Depends(get_db)):
    """Return a nonce for the given wallet address to sign."""
    address = body.get("address", "").lower().strip()
    if not address or not address.startswith("0x") or len(address) != 42:
        raise HTTPException(400, "Invalid wallet address")

    nonce = generate_nonce()
    # Find or create user by wallet_address
    user = await db.scalar(select(User).where(User.wallet_address == address))
    if not user:
        # Auto-create user with wallet address
        user = User(wallet_address=address, nonce=nonce,
                    email=None, password_hash=None)
        db.add(user)
        await db.flush()
        db.add(Wallet(user_id=user.id, asset="USDT", balance=0))
    else:
        user.nonce = nonce
    await db.commit()
    return {"nonce": nonce, "message": get_login_message(nonce)}


@router.post("/metamask/verify")
async def metamask_verify(body: dict, db: AsyncSession = Depends(get_db)):
    """Verify MetaMask signature and return JWT."""
    address = body.get("address", "").lower().strip()
    signature = body.get("signature", "").strip()

    if not address or not signature:
        raise HTTPException(400, "address and signature required")

    user = await db.scalar(select(User).where(User.wallet_address == address))
    if not user or not user.nonce:
        raise HTTPException(404, "Address not found — call /nonce first")

    if not verify_signature(address, user.nonce, signature):
        raise HTTPException(401, "Invalid signature")

    # Invalidate nonce after use
    user.nonce = None
    await db.commit()

    return TokenResponse(access_token=create_access_token(user.id))
