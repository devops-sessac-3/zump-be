import hashlib


def sha512Hash(plain_text: str) -> str:
    """Return a SHA-512 hash for the provided plain-text string."""
    if plain_text == "":
        return ""

    return hashlib.sha512(plain_text.encode("utf-8")).hexdigest()