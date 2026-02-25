import secrets
from eth_account import Account
from eth_account.messages import encode_defunct


def generate_nonce() -> str:
    """Generate a random nonce for MetaMask signing."""
    return secrets.token_hex(32)


def verify_signature(address: str, nonce: str, signature: str) -> bool:
    """
    Verify that `signature` is a personal_sign of `nonce` by `address`.
    Returns True if valid.
    """
    message = f"ForLabsEX 로그인 확인\nNonce: {nonce}"
    try:
        msg = encode_defunct(text=message)
        recovered = Account.recover_message(msg, signature=signature)
        return recovered.lower() == address.lower()
    except Exception:
        return False


def get_login_message(nonce: str) -> str:
    return f"ForLabsEX 로그인 확인\nNonce: {nonce}"
