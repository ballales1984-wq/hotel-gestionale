"""Tests for EncryptionService (Fernet)."""
import os
import pytest
from cryptography.fernet import Fernet

from app.core.encryption import EncryptionService, get_encryption_service

# Usa DB temporaneo per isolamento
import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionFactory, engine, Base
from app.config import Settings
from pydantic_settings import SettingsConfigDict


@pytest.fixture(scope="module")
def settings_with_key():
    """Settings con ENCRYPTION_KEY di test."""
    key = Fernet.generate_key().decode()
    os.environ["ENCRYPTION_KEY"] = key
    # Forza ricaricamento settings
    from app.config import get_settings
    # Pulisci cache
    get_settings.cache_clear()
    return Settings()


def test_encryption_roundtrip():
    """Cifratura e decifratura funzionano."""
    key = Fernet.generate_key().decode()
    service = EncryptionService(key)
    plaintext = "secret-api-key-12345"
    ciphertext = service.encrypt(plaintext)
    assert ciphertext != plaintext
    decrypted = service.decrypt(ciphertext)
    assert decrypted == plaintext


def test_encrypt_none_returns_none():
    """Input None restituisce None."""
    key = Fernet.generate_key().decode()
    service = EncryptionService(key)
    assert service.encrypt(None) is None
    assert service.decrypt(None) is None


# def test_get_encryption_service_singleton():
#     """Il singleton è riutilizzato (richiede ENCRYPTION_KEY configurata)."""
#     # Non testato in isolamento per evitare dipendenze da cache globale
#     pass


def test_invalid_key_raises():
    """Chiave non valida solleva ValueError."""
    with pytest.raises(ValueError):
        EncryptionService("invalid-key-not-base64-!!!")
    with pytest.raises(ValueError):
        EncryptionService("")


def test_encryption_with_settings(settings_with_key):
    """Usa il servizio con le settings."""
    service = EncryptionService(settings_with_key.encryption_key)
    plaintext = "my-password-xyz"
    cipher = service.encrypt(plaintext)
    assert cipher.startswith("g") or cipher.startswith(" ")  # Fernet ciphertext
    decrypted = service.decrypt(cipher)
    assert decrypted == plaintext
