from __future__ import annotations

from app.models import User


class AdminSafetyError(PermissionError):
    pass


class AdminService:
    def ensure_admin(self, user: User) -> None:
        if user.role != "admin":
            raise AdminSafetyError("admin access required")

    def decrypt_user_secret(self, *_args, **_kwargs) -> None:
        raise AdminSafetyError("admins cannot decrypt user vault secrets")

    def generate_user_code(self, *_args, **_kwargs) -> None:
        raise AdminSafetyError("admins cannot generate user OTP codes")
