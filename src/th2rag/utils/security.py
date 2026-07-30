import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from passlib.context import CryptContext
from th2rag.config import settings
from cryptography.fernet import Fernet


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    sha = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return pwd_context.hash(sha)


@dataclass
class SolveBugBcryptWarning:
    __version__: str = bcrypt.__version__


bcrypt.__about__ = SolveBugBcryptWarning()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



def verify_password(plain_password, hashed_password):
    sha = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return pwd_context.verify(sha, hashed_password)


def get_password_hash(password):
    return hash_password(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.encrypt_key, algorithm=settings.algorithm)
    return encoded_jwt

def get_fernet():
    """
    Generates a valid Fernet key derived from the app's secret_key.
    Fernet requires a 32-byte url-safe base64-encoded key.
    """
    # Take first 32 chars of secret_key, pad with 0 if too short
    key_material = settings.secret_key[:32]
    final_key = key_material.ljust(32, '0')
    
    # Convert to base64 format required by Fernet
    encoded_key = base64.urlsafe_b64encode(final_key.encode())
    return Fernet(encoded_key)

def encrypt_key(plain_key: str) -> str:
    """Encrypts a raw API key (e.g. 'sk-ant-...') into a safe string."""
    if not plain_key:
        return ""
    f = get_fernet()
    # Encrypt and return as string (not bytes)
    return f.encrypt(plain_key.encode()).decode()

def decrypt_key(encrypted_key: str) -> str:
    """Decrypts a safe string back into the raw API key."""
    if not encrypted_key:
        return ""
    f = get_fernet()
    return f.decrypt(encrypted_key.encode()).decode()
