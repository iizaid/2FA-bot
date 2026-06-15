from __future__ import annotations

import base64
import binascii
import hashlib
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

import pyotp


SUPPORTED_ALGORITHMS = {"SHA1": hashlib.sha1, "SHA256": hashlib.sha256, "SHA512": hashlib.sha512}


class TotpValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TotpSecret:
    secret: str
    issuer: str | None
    account_name: str | None
    algorithm: str = "SHA1"
    digits: int = 6
    period: int = 30


@dataclass(frozen=True)
class TotpCode:
    code: str
    expires_in: int


def _normalize_base32(secret: str) -> str:
    normalized = "".join(secret.strip().upper().split()).replace("-", "")
    if not normalized:
        raise TotpValidationError("setup key is empty")
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    try:
        base64.b32decode(normalized + padding, casefold=True)
    except (binascii.Error, ValueError) as exc:
        raise TotpValidationError("setup key is not valid Base32") from exc
    return normalized


def parse_setup_value(value: str) -> TotpSecret:
    candidate = value.strip()
    if candidate.lower().startswith("otpauth://"):
        return _parse_otpauth_uri(candidate)
    return TotpSecret(secret=_normalize_base32(candidate), issuer=None, account_name=None)


def _parse_otpauth_uri(uri: str) -> TotpSecret:
    parsed = urlparse(uri)
    if parsed.scheme != "otpauth" or parsed.netloc != "totp":
        raise TotpValidationError("only otpauth://totp URIs are supported")

    params = parse_qs(parsed.query)
    secret_values = params.get("secret")
    if not secret_values:
        raise TotpValidationError("otpauth URI is missing a secret")

    label = unquote(parsed.path.lstrip("/"))
    label_issuer: str | None = None
    account_name: str | None = label or None
    if ":" in label:
        label_issuer, account_name = label.split(":", 1)

    issuer = params.get("issuer", [label_issuer])[0] or label_issuer
    algorithm = params.get("algorithm", ["SHA1"])[0].upper()
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise TotpValidationError("unsupported TOTP algorithm")

    try:
        digits = int(params.get("digits", ["6"])[0])
        period = int(params.get("period", ["30"])[0])
    except ValueError as exc:
        raise TotpValidationError("TOTP digits and period must be numbers") from exc

    if digits not in (6, 7, 8):
        raise TotpValidationError("TOTP digits must be 6, 7, or 8")
    if period <= 0 or period > 300:
        raise TotpValidationError("TOTP period is invalid")

    return TotpSecret(
        secret=_normalize_base32(secret_values[0]),
        issuer=issuer,
        account_name=account_name,
        algorithm=algorithm,
        digits=digits,
        period=period,
    )


def build_totp(secret: str, *, algorithm: str = "SHA1", digits: int = 6, period: int = 30) -> pyotp.TOTP:
    digest = SUPPORTED_ALGORITHMS.get(algorithm.upper())
    if digest is None:
        raise TotpValidationError("unsupported TOTP algorithm")
    return pyotp.TOTP(secret, digits=digits, interval=period, digest=digest)


def verify_setup_code(parsed_secret: TotpSecret, code: str) -> bool:
    clean_code = code.strip().replace(" ", "")
    if not clean_code.isdigit() or len(clean_code) != parsed_secret.digits:
        return False
    totp = build_totp(
        parsed_secret.secret,
        algorithm=parsed_secret.algorithm,
        digits=parsed_secret.digits,
        period=parsed_secret.period,
    )
    return bool(totp.verify(clean_code, valid_window=1))


def current_code(secret: str, *, algorithm: str = "SHA1", digits: int = 6, period: int = 30) -> TotpCode:
    totp = build_totp(secret, algorithm=algorithm, digits=digits, period=period)
    now = int(time.time())
    expires_in = period - (now % period)
    return TotpCode(code=totp.now(), expires_in=expires_in)

