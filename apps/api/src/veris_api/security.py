from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import secrets
import unicodedata
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from email_validator import EmailNotValidError, validate_email
from fastapi import Request
from pwdlib import PasswordHash

from veris_api.config import Settings, get_settings

COMMON_PASSWORDS = {
    "123456789012345",
    "cephalon thesos",
    "cephalonthesos",
    "letmeinletmeinletmein",
    "password123456789",
    "passwordpassword",
    "qwertyuiopasdfgh",
    "thesospassword",
    "warframepassword",
}


class PasswordPolicyError(ValueError):
    pass


def normalize_email(value: str) -> str:
    candidate = value.strip()
    try:
        validate_email(candidate, check_deliverability=False)
    except EmailNotValidError as error:
        raise ValueError("Enter a valid email address") from error
    return candidate.casefold()


def normalize_password(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    if len(normalized) < 8:
        raise PasswordPolicyError("Password must contain at least 8 characters")
    if len(normalized) > 128:
        raise PasswordPolicyError("Password must contain at most 128 characters")
    missing: list[str] = []
    if not any(character.isupper() for character in normalized):
        missing.append("an uppercase letter")
    if not any(character.islower() for character in normalized):
        missing.append("a lowercase letter")
    if not any(character.isdigit() for character in normalized):
        missing.append("a number")
    if not any(not character.isalnum() and not character.isspace() for character in normalized):
        missing.append("a symbol")
    if missing:
        raise PasswordPolicyError(f"Password must include {', '.join(missing)}")
    if normalized.casefold() in COMMON_PASSWORDS:
        raise PasswordPolicyError("Choose a less common password")
    return normalized


@lru_cache
def password_hasher() -> PasswordHash:
    return PasswordHash.recommended()


@lru_cache
def dummy_password_hash() -> str:
    return password_hasher().hash("not-a-real-account-password")


def hash_password(password: str) -> str:
    return password_hasher().hash(normalize_password(password))


def verify_password(password: str, verifier: str) -> tuple[bool, str | None]:
    try:
        normalized = unicodedata.normalize("NFC", password)
        return password_hasher().verify_and_update(normalized, verifier)
    except (TypeError, ValueError):
        return False, None


def random_token(bytes_count: int = 32) -> str:
    return secrets.token_urlsafe(bytes_count)


def keyed_digest(value: str, purpose: str, *, settings: Settings | None = None) -> str:
    runtime = settings or get_settings()
    return hmac.new(
        runtime.session_digest_key.encode("utf-8"),
        f"{purpose}\0{value}".encode(),
        hashlib.sha256,
    ).hexdigest()


def device_digest(value: str, *, settings: Settings | None = None) -> str:
    return keyed_digest(value, "device", settings=settings)


def client_ip(request: Request, *, settings: Settings | None = None) -> str:
    runtime = settings or get_settings()
    direct = request.client.host if request.client else "0.0.0.0"
    try:
        direct_ip = ipaddress.ip_address(direct)
    except ValueError:
        return "0.0.0.0"

    trusted = any(
        direct_ip in ipaddress.ip_network(cidr, strict=False)
        for cidr in runtime.trusted_proxy_cidrs
    )
    if trusted:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded)) if forwarded else str(direct_ip)
        except ValueError:
            return str(direct_ip)
    return str(direct_ip)


def ip_pseudonym(request: Request, *, settings: Settings | None = None) -> str:
    runtime = settings or get_settings()
    return hmac.new(
        runtime.ip_hmac_key.encode("utf-8"),
        client_ip(request, settings=runtime).encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def _mfa_key(settings: Settings) -> bytes:
    return hashlib.sha256(settings.admin_mfa_encryption_key.encode("utf-8")).digest()


def encrypt_mfa_secret(secret: str, *, settings: Settings | None = None) -> str:
    runtime = settings or get_settings()
    nonce = secrets.token_bytes(12)
    encrypted = AESGCM(_mfa_key(runtime)).encrypt(
        nonce, secret.encode("ascii"), b"thesos-admin-mfa"
    )
    return base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")


def decrypt_mfa_secret(value: str, *, settings: Settings | None = None) -> str:
    runtime = settings or get_settings()
    raw = base64.urlsafe_b64decode(value.encode("ascii"))
    return (
        AESGCM(_mfa_key(runtime)).decrypt(raw[:12], raw[12:], b"thesos-admin-mfa").decode("ascii")
    )


def secure_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
