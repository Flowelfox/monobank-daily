import base64
import hashlib

from cryptography.fernet import Fernet

from src.settings import PROJECT_ROOT

SECRET_KEY_FILE = PROJECT_ROOT / "data" / ".secret_key"


def _get_or_create_master_key() -> bytes:
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_bytes()

    key = Fernet.generate_key()
    SECRET_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRET_KEY_FILE.write_bytes(key)
    return key


def _derive_user_key(user_id: int) -> bytes:
    master_key = _get_or_create_master_key()
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        master_key,
        str(user_id).encode(),
        100000,
    )
    return base64.urlsafe_b64encode(derived)


def encrypt_token(token: str, user_id: int) -> str:
    key = _derive_user_key(user_id)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(token.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_token(encrypted_token: str, user_id: int) -> str | None:
    try:
        key = _derive_user_key(user_id)
        fernet = Fernet(key)
        decrypted = fernet.decrypt(base64.urlsafe_b64decode(encrypted_token.encode()))
        return decrypted.decode()
    except Exception:
        return None
