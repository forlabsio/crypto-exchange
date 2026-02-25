import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.redis import get_redis
from app.models.user import User
from app.models.wallet import Wallet
from app.models.deposit import DepositTransaction, DepositStatus
from app.services.polygon import verify_usdt_deposit

router = APIRouter(prefix="/api/wallet", tags=["wallet"])

@router.get("")
async def get_wallet(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    wallets = list(await db.scalars(select(Wallet).where(Wallet.user_id == user.id)))
    redis = await get_redis()
    result = []
    for w in wallets:
        price_usdt = 1.0
        if w.asset != "USDT":
            ticker = await redis.get(f"market:{w.asset}_USDT:ticker")
            if ticker:
                price_usdt = float(json.loads(ticker)["last_price"])
        balance = float(w.balance or 0)
        locked = float(w.locked_balance or 0)
        result.append({
            "asset": w.asset,
            "balance": str(w.balance),
            "locked": str(w.locked_balance or 0),
            "price_usdt": price_usdt,
            "value_usdt": (balance + locked) * price_usdt,
        })
    return result

@router.post("/deposit")
async def deposit(body: dict, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    target_user_id = body["user_id"]
    asset = body["asset"]
    amount = float(body["amount"])
    wallet = await db.scalar(select(Wallet).where(Wallet.user_id == target_user_id, Wallet.asset == asset))
    if wallet:
        wallet.balance += amount
    else:
        db.add(Wallet(user_id=target_user_id, asset=asset, balance=amount))
    await db.commit()
    return {"message": "deposited"}


@router.get("/deposit/address")
async def deposit_address(user: User = Depends(get_current_user)):
    """Return the platform's Polygon USDT deposit address."""
    return {
        "address": settings.PLATFORM_DEPOSIT_ADDRESS,
        "network": "Polygon",
        "token": "USDT (USDT-PoS)",
        "contract": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "min_confirmations": 6,
    }


@router.post("/deposit/verify")
async def verify_deposit(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a TX hash to verify and credit a USDT deposit."""
    tx_hash = body.get("tx_hash", "").strip().lower()
    if not tx_hash or not tx_hash.startswith("0x") or len(tx_hash) != 66:
        raise HTTPException(400, "Invalid TX hash (must be 66 hex characters)")

    # Prevent duplicate submissions — filter by user_id so users only see their own records
    existing = await db.scalar(
        select(DepositTransaction).where(
            DepositTransaction.tx_hash == tx_hash,
            DepositTransaction.user_id == user.id,
        )
    )
    if existing:
        if existing.status == DepositStatus.confirmed:
            raise HTTPException(409, "This transaction has already been credited")
        if existing.status == DepositStatus.pending:
            raise HTTPException(409, "This transaction is already being processed")
        # If failed, allow retry — delete old record and proceed
        await db.delete(existing)
        await db.flush()

    # Create pending record
    deposit = DepositTransaction(
        user_id=user.id,
        tx_hash=tx_hash,
        amount_usdt=0,
        from_address="",
        status=DepositStatus.pending,
    )
    db.add(deposit)
    await db.flush()

    # Verify on-chain
    result = await verify_usdt_deposit(tx_hash)
    if not result["valid"]:
        deposit.status = DepositStatus.failed
        await db.commit()
        raise HTTPException(400, result["error"])

    # Credit user's USDT wallet
    wallet = await db.scalar(
        select(Wallet).where(Wallet.user_id == user.id, Wallet.asset == "USDT")
    )
    if not wallet:
        wallet = Wallet(user_id=user.id, asset="USDT", balance=0)
        db.add(wallet)
        await db.flush()

    wallet.balance += result["amount_usdt"]
    deposit.amount_usdt = result["amount_usdt"]
    deposit.from_address = result["from_address"]
    deposit.status = DepositStatus.confirmed
    deposit.confirmed_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "message": "입금이 확인됐습니다.",
        "amount_usdt": float(result["amount_usdt"]),
        "new_balance": float(wallet.balance),
    }


@router.get("/deposits")
async def get_deposits(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return user's deposit history."""
    deposits = list(await db.scalars(
        select(DepositTransaction)
        .where(DepositTransaction.user_id == user.id)
        .order_by(DepositTransaction.created_at.desc())
        .limit(20)
    ))
    return [
        {
            "tx_hash": d.tx_hash,
            "amount_usdt": float(d.amount_usdt),
            "status": d.status,
            "confirmed_at": d.confirmed_at.isoformat() if d.confirmed_at else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in deposits
    ]
