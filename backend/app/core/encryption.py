"""
Encryption Service — Cifratura dati sensibili
Usa Fernet (AES-128-CBC) per cifrare/decifrare stringhe.
"""
from __future__ import annotations

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import get_settings

settings = get_settings()


class EncryptionService:
    """Servizio per cifrare/decifrare dati sensibili."""
    
    def __init__(self, key: str):
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY non configurata. "
                "Genera una chiave con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        try:
            # Fernet key must be 32 url-safe base64-encoded bytes
            self.fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            raise ValueError(f"Chiave di cifratura non valida: {e}")

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """Cifra una stringa plaintext. Restituisce None se input è None."""
        if plaintext is None:
            return None
        if not isinstance(plaintext, str):
            raise TypeError("plaintext deve essere una stringa")
        encrypted = self.fernet.encrypt(plaintext.encode("utf-8"))
        return encrypted.decode("utf-8")

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        """Decifra una stringa cifrata. Restituisce None se input è None."""
        if ciphertext is None:
            return None
        if not isinstance(ciphertext, str):
            raise TypeError("ciphertext deve essere una stringa")
        try:
            decrypted = self.fernet.decrypt(ciphertext.encode("utf-8"))
            return decrypted.decode("utf-8")
        except InvalidToken:
            # Could be old/unencrypted data or wrong key
            # In dev mode we might return as-is; in prod we should log and raise
            return None


# ── Singleton (inizializzato una volta all'avvio) ────────────────────────────
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Restituisce l'istanza singleton del servizio di cifratura."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService(settings.encryption_key)
    return _encryption_service
