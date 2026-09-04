"""Credential encryption: the master key rules, and what a hint may reveal.

|| Cifrado de credenciales: las reglas de la master key, y qué puede revelar un hint.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.foundation import secrets
from app.foundation.secrets import SecretsCorrupted, SecretsDisabled


def _use_key(monkeypatch, key: str) -> None:
    monkeypatch.setattr(secrets, "get_settings", lambda: Settings(SECRETS_KEY=key))
    secrets._fernet.cache_clear()


@pytest.fixture
def a_key(monkeypatch) -> str:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("utf-8")
    _use_key(monkeypatch, key)
    yield key
    secrets._fernet.cache_clear()


class TestWithoutAMasterKey:
    def test_storage_is_reported_disabled(self, monkeypatch):
        _use_key(monkeypatch, "")

        assert secrets.is_enabled() is False

        secrets._fernet.cache_clear()

    def test_encrypting_fails_instead_of_falling_back_to_plaintext(self, monkeypatch):
        # The property that matters: there is no "store it in the clear for
        # now" path, because that is how a database dump ends up carrying live
        # credentials.
        # || La propiedad que importa: no existe el camino "por ahora en
        # claro", porque así es como un dump termina con credenciales vivas.
        _use_key(monkeypatch, "")

        with pytest.raises(SecretsDisabled, match="SECRETS_KEY"):
            secrets.encrypt("sk-live-abcd")

        secrets._fernet.cache_clear()

    def test_a_malformed_master_key_is_refused_as_disabled(self, monkeypatch):
        _use_key(monkeypatch, "not-a-fernet-key")

        assert secrets.is_enabled() is False

        secrets._fernet.cache_clear()


class TestRoundTrip:
    def test_a_credential_survives_encrypt_then_decrypt(self, a_key):
        token = secrets.encrypt("sk-live-abcd1234")

        assert secrets.decrypt(token) == "sk-live-abcd1234"

    def test_the_ciphertext_does_not_contain_the_plaintext(self, a_key):
        token = secrets.encrypt("sk-live-abcd1234")

        assert "sk-live" not in token
        assert "abcd1234" not in token

    def test_encrypting_twice_gives_different_ciphertext(self, a_key):
        # Fernet includes an IV and a timestamp, so equal plaintexts do not
        # produce equal rows — a dump does not reveal which providers share a
        # key.
        # || Fernet incluye IV y timestamp, así que dos plaintexts iguales no
        # producen filas iguales.
        assert secrets.encrypt("same-key") != secrets.encrypt("same-key")

    def test_refusing_to_encrypt_nothing(self, a_key):
        with pytest.raises(ValueError, match="empty"):
            secrets.encrypt("")


class TestWrongMasterKey:
    def test_a_ciphertext_from_another_key_raises_rather_than_returning_garbage(
        self, monkeypatch
    ):
        # Rotating the key, or restoring a dump from another environment,
        # leaves rows that cannot be read. Reporting that beats handing a
        # provider a broken value and getting a confusing 401 from them.
        # || Rotar la clave, o restaurar un dump de otro entorno, deja filas
        # ilegibles. Reportarlo le gana a pasarle al proveedor un valor roto.
        from cryptography.fernet import Fernet

        _use_key(monkeypatch, Fernet.generate_key().decode("utf-8"))
        token = secrets.encrypt("sk-live-abcd")

        _use_key(monkeypatch, Fernet.generate_key().decode("utf-8"))

        with pytest.raises(SecretsCorrupted, match="SECRETS_KEY"):
            secrets.decrypt(token)

        secrets._fernet.cache_clear()


class TestHint:
    def test_a_hint_reveals_only_the_last_four_characters(self, a_key):
        assert secrets.hint("sk-live-super-secret-9xyz") == "…9xyz"

    def test_a_short_value_reveals_nothing(self, a_key):
        # Four characters of a five-character value is most of it, so a value
        # too short to hint about gets no hint.
        # || Cuatro caracteres de un valor de cinco es casi todo.
        assert secrets.hint("abc") == "…"
