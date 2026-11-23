import base64
import hashlib
import os
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from src.config import settings


class CryptoService:
    def __init__(self, secret_key: str = settings.TOKEN_ENCRYPTION_KEY):
        # Derive a stable 32-byte (256-bit) key using SHA-256
        self._key = hashlib.sha256(secret_key.encode("utf-8")).digest()
        self._aesgcm = AESGCM(self._key)

    def encrypt_token(self, token: str) -> str:
        """Encrypts a plaintext token string with AES-256-GCM and returns a base64 string."""
        if not token:
            return ""
        nonce = os.urandom(12)  # 96-bit nonce
        token_bytes = token.encode("utf-8")
        ciphertext = self._aesgcm.encrypt(nonce, token_bytes, None)
        combined = nonce + ciphertext
        return base64.urlsafe_b64encode(combined).decode("utf-8")

    def decrypt_token(self, encrypted_token_b64: str) -> str:
        """Decrypts a base64 encoded AES-256-GCM ciphertext back into a plaintext token."""
        if not encrypted_token_b64:
            return ""
        try:
            combined = base64.urlsafe_b64decode(encrypted_token_b64.encode("utf-8"))
            nonce = combined[:12]
            ciphertext = combined[12:]
            decrypted = self._aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decrypt token: {e}")

    @staticmethod
    def generate_random_token(length_bytes: int = 32) -> str:
        """Generates a cryptographically secure URL-safe random string."""
        return secrets.token_urlsafe(length_bytes)


crypto_service = CryptoService()
