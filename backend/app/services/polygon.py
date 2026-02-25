import os
import httpx
from decimal import Decimal
from typing import Optional

POLYGON_RPC = os.environ.get("POLYGON_RPC_URL", "https://polygon-rpc.com")
PLATFORM_ADDRESS = os.environ.get("PLATFORM_DEPOSIT_ADDRESS", "").lower()
USDT_CONTRACT = os.environ.get("POLYGON_USDT_CONTRACT", "0xc2132D05D31c914a87C6611C10748AEb04B58e8F").lower()
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
        result = resp.json().get("result")
        return result


async def get_current_block() -> int:
    """Get latest block number."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(POLYGON_RPC, json={
            "jsonrpc": "2.0", "method": "eth_blockNumber",
            "params": [], "id": 1,
        })
        return int(resp.json()["result"], 16)


async def verify_usdt_deposit(tx_hash: str) -> dict:
    """
    Verify a Polygon USDT deposit transaction.
    Returns: {"valid": bool, "amount_usdt": Decimal, "from_address": str, "error": str}
    """
    receipt = await get_tx_receipt(tx_hash)
    if not receipt:
        return {"valid": False, "error": "Transaction not found"}
    if receipt.get("status") != "0x1":
        return {"valid": False, "error": "Transaction failed on-chain"}

    # Check 6 block confirmations
    tx_block = int(receipt["blockNumber"], 16)
    current_block = await get_current_block()
    if current_block - tx_block < 6:
        return {"valid": False, "error": f"Waiting for confirmations ({current_block - tx_block}/6)"}

    # Parse USDT Transfer logs
    for log in receipt.get("logs", []):
        if log["address"].lower() != USDT_CONTRACT:
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
        raw_amount = int(log["data"], 16)
        amount_usdt = Decimal(raw_amount) / Decimal(10 ** USDT_DECIMALS)

        return {
            "valid": True,
            "amount_usdt": amount_usdt,
            "from_address": from_address,
        }

    return {"valid": False, "error": "No USDT Transfer to platform address found in this transaction"}
