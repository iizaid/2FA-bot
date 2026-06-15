from __future__ import annotations

import logging
import sys


class SecretRedactionFilter(logging.Filter):
    REDACTED_WORDS = (
        "secret",
        "otp",
        "totp",
        "code",
        "pin",
        "passphrase",
        "password",
        "otpauth",
        "vault_master_key",
        "encrypted_secret",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        if any(word in message for word in self.REDACTED_WORDS):
            record.msg = "[sensitive log message redacted]"
            record.args = ()
        return True


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SecretRedactionFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)

