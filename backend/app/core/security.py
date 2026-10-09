import hashlib
import hmac


def hash_identifier(value: str, secret: str) -> str:
    """Create a stable, non-reversible identifier for sensitive external IDs."""

    return hmac.new(
        secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
