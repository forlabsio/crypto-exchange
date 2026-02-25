import httpx
from decimal import Decimal
from typing import Optional

from app.config import settings

POLYGON_RPC = settings.POLYGON_RPC_URL
PLATFORM_ADDRESS = settings.PLATFORM_DEPOSIT_ADDRESS.lower()
USDT_CONTRACT = settings.POLYGON_USDT_CONTRACT.lower()
USDT_DECIMALS = 6  # Polygon USDT has 6 decimals

# USDT Transfer event topic
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


async def get_tx_receipt(tx_hash: str) -> Optional[dict]:
    """Fetch transaction receipt from Polygon RPC."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(POLYGON_RPC, json={
            "jsonrpc": "2.0", "method": "eth_getTransactionReceipt",
            "params": [tx_hash], "id": 1,
        })
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise httpx.HTTPError(f"RPC error: {data['error']}")
        return data.get("result")


async def get_current_block() -> int:
    """Get latest block number."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(POLYGON_RPC, json={
            "jsonrpc": "2.0", "method": "eth_blockNumber",
            "params": [], "id": 1,
        })
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise httpx.HTTPError(f"RPC error: {data['error']}")
        return int(data["result"], 16)


async def verify_usdt_deposit(tx_hash: str) -> dict:
    """
    Verify a Polygon USDT deposit transaction.
    Returns: {"valid": bool, "amount_usdt": Decimal, "from_address": str, "error": str}
    """
    try:
        receipt = await get_tx_receipt(tx_hash)
    except Exception as e:
        return {"valid": False, "error": f"RPC error: {e}"}

    if not receipt:
        return {"valid": False, "error": "Transaction not found"}
    if receipt.get("status") != "0x1":
        return {"valid": False, "error": "Transaction failed on-chain"}

    # Check 6 block confirmations
    tx_block = int(receipt.get("blockNumber", "0x0"), 16)

    try:
        current_block = await get_current_block()
    except Exception as e:
        return {"valid": False, "error": f"Could not fetch block number: {e}"}

    if current_block - tx_block < 6:
        return {"valid": False, "error": f"Waiting for confirmations ({current_block - tx_block}/6)"}

    # Parse USDT Transfer logs
    for log in receipt.get("logs", []):
        if log.get("address", "").lower() != USDT_CONTRACT:
            continue
        topics = log.get("topics", [])
        if len(topics) < 3:
            continue
        if topics[0].lower() != TRANSFER_TOPIC:
            continue

        to_address = "0x" + topics[2][-40:]
        if to_address.lower() != PLATFORM_ADDRESS:
            continue

        from_address = "0x" + topics[1][-40:]
        # Amount is in log data (hex)
        raw_amount = int(log.get("data", "0x0"), 16)
        amount_usdt = Decimal(raw_amount) / Decimal(10 ** USDT_DECIMALS)

        return {
            "valid": True,
            "amount_usdt": amount_usdt,
            "from_address": from_address,
        }

    return {"valid": False, "error": "No USDT Transfer to platform address found in this transaction"}
