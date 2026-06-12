import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

# Security Configuration
SECRET_KEY = "SUPER_SECRET_SECURITY_KEY_FOR_INSPECT_SHIELD_PRO_METROLOGY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours (1 day)
PBKDF2_ITERATIONS = 100000

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a stored PBKDF2-HMAC-SHA256 hash."""
    try:
        if not hashed_password or "." not in hashed_password:
            return False
            
        salt_hex, key_hex = hashed_password.split(".", 1)
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        
        # Hash plain password with the same salt and iteration count
        new_key = hashlib.pbkdf2_hmac(
            'sha256', 
            plain_password.encode('utf-8'), 
            salt, 
            PBKDF2_ITERATIONS
        )
        return new_key == key
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Generates a secure PBKDF2-HMAC-SHA256 hash using a cryptographically random salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt, 
        PBKDF2_ITERATIONS
    )
    # Store salt and key joined by a period in hexadecimal representation
    return f"{salt.hex()}.{key.hex()}"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a secure JWT authentication token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decodes a JWT token, returns the payload if valid, else None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
