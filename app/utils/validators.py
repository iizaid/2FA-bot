from __future__ import annotations


def clean_name(value: str, *, max_length: int = 120) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValueError("value cannot be empty")
    if len(cleaned) > max_length:
        raise ValueError(f"value cannot be longer than {max_length} characters")
    return cleaned


def clean_pin(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) < 6:
        raise ValueError("PIN/passphrase must be at least 6 characters")
    if len(cleaned) > 256:
        raise ValueError("PIN/passphrase is too long")
    return cleaned
