import pytest

from app.services.totp import TotpValidationError, build_totp, parse_setup_value


def test_known_rfc_totp_vector() -> None:
    totp = build_totp(
        "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",
        algorithm="SHA1",
        digits=8,
        period=30,
    )

    assert totp.at(59) == "94287082"


def test_parse_otpauth_uri() -> None:
    parsed = parse_setup_value(
        "otpauth://totp/GitHub:Personal?secret=JBSWY3DPEHPK3PXP&issuer=GitHub&algorithm=SHA1&digits=6&period=30"
    )

    assert parsed.secret == "JBSWY3DPEHPK3PXP"
    assert parsed.issuer == "GitHub"
    assert parsed.account_name == "Personal"
    assert parsed.digits == 6


def test_invalid_setup_key_fails_safely() -> None:
    with pytest.raises(TotpValidationError):
        parse_setup_value("not a valid setup key")

