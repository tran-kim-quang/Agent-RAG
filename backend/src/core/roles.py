from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


def is_admin(role: str) -> bool:
    return role == UserRole.ADMIN
