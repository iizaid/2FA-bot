from app.services.encryption import EncryptionService


def test_encrypt_decrypt_roundtrip() -> None:
    service = EncryptionService(EncryptionService.generate_master_key())
    encrypted = service.encrypt_text("JBSWY3DPEHPK3PXP")

    assert encrypted != "JBSWY3DPEHPK3PXP"
    assert service.decrypt_text(encrypted) == "JBSWY3DPEHPK3PXP"


def test_plain_master_key_is_derived() -> None:
    service = EncryptionService("local-development-master-key")
    encrypted = service.encrypt_text("JBSWY3DPEHPK3PXP")

    assert service.decrypt_text(encrypted) == "JBSWY3DPEHPK3PXP"

