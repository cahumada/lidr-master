"""Symmetric encryption for credentials stored in the database.

Provider API keys live in `providers.api_key_ciphertext`, encrypted with a
master key that lives in the **environment** (`SECRETS_KEY`) and never in the
database. That split is the whole point: a leaked `pg_dump` carries ciphertext
and no way to read it.

Three rules this module enforces, because each one is a way the feature could
quietly stop being safe:

1. **No master key, no storage.** With `SECRETS_KEY` unset, writing a
   credential FAILS. There is deliberately no "store it as plaintext for now"
   path — that is how a dump ends up with live keys in it.
2. **One-way for callers.** ``encrypt`` is used by the write endpoint;
   ``decrypt`` only by the code that builds a provider client. Nothing in the
   API layer returns a decrypted value.
3. **A hint is not the secret.** ``hint`` returns the last four characters so
   a human can tell *which* key is loaded without the key being readable.

Fernet (AES-128-CBC + HMAC-SHA256, from `cryptography`) rather than something
hand-rolled: authenticated encryption means a tampered ciphertext fails loudly
instead of decrypting to garbage that gets sent to a provider as a key.

|| Cifrado simétrico para las credenciales guardadas en la base. Las claves de
API de los proveedores viven cifradas con una master key que está en el
ENTORNO (`SECRETS_KEY`) y nunca en la base: un `pg_dump` filtrado se lleva
ciphertext y ninguna forma de leerlo.

Tres reglas que este módulo hace cumplir: sin master key NO se guarda nada (no
existe el camino "por ahora en texto plano", que es justo como un dump termina
con claves vivas adentro); ``decrypt`` solo lo usa quien arma el cliente del
proveedor, nunca la capa de API; y el "hint" son los últimos cuatro caracteres,
para saber CUÁL clave está cargada sin que la clave sea legible.
"""

from __future__ import annotations

from functools import lru_cache

import structlog

from app.config import get_settings

log = structlog.get_logger()

# How many trailing characters a hint may reveal. Four is enough to tell two
# keys apart and not enough to be useful to anybody else.
# || Cuántos caracteres finales puede revelar un hint. Cuatro alcanzan para
# distinguir dos claves y no alcanzan para que le sirvan a nadie más.
_HINT_CHARS = 4


class SecretsDisabled(RuntimeError):
    """No master key is configured, so credentials cannot be stored.

    || No hay master key configurada, así que no se pueden guardar credenciales.
    """


class SecretsCorrupted(RuntimeError):
    """A stored ciphertext could not be decrypted with the current master key.

    Raised instead of returning garbage: an unreadable credential is a
    configuration problem to surface (the key was rotated, or the row came
    from another environment), not a value to pass to a provider.

    || Un ciphertext guardado no se pudo descifrar con la master key actual. Se
    lanza en vez de devolver basura: una credencial ilegible es un problema de
    configuración que hay que mostrar, no un valor para pasarle a un proveedor.
    """


@lru_cache
def _fernet():
    """The Fernet instance for the configured master key.

    || La instancia de Fernet para la master key configurada.
    """
    from cryptography.fernet import Fernet

    key = get_settings().SECRETS_KEY
    if not key:
        raise SecretsDisabled(
            "SECRETS_KEY is not set, so credentials cannot be stored in the database. "
            "Generate one with `python scripts/generate_secrets_key.py` and put it in "
            "the environment. || SECRETS_KEY no está definida, así que no se pueden "
            "guardar credenciales en la base."
        )
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise SecretsDisabled(
            "SECRETS_KEY is not a valid Fernet key (32 url-safe base64-encoded bytes). "
            "|| SECRETS_KEY no es una clave Fernet válida."
        ) from exc


def is_enabled() -> bool:
    """Whether credentials can be stored at all.

    || Si se pueden guardar credenciales.
    """
    try:
        _fernet()
    except SecretsDisabled:
        return False
    return True


def encrypt(plaintext: str) -> str:
    """Encrypt a credential for storage.

    || Cifra una credencial para guardarla.
    """
    if not plaintext:
        raise ValueError("refusing to encrypt an empty value || no se cifra un valor vacío")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored credential.

    || Descifra una credencial guardada.
    """
    from cryptography.fernet import InvalidToken

    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        # Deliberately says nothing about the value itself.
        # || A propósito no dice nada del valor en sí.
        log.error("stored_secret_undecryptable")
        raise SecretsCorrupted(
            "a stored credential could not be decrypted with the current SECRETS_KEY "
            "(rotated key, or a row from another environment) "
            "|| una credencial guardada no se pudo descifrar con la SECRETS_KEY actual"
        ) from exc


def hint(plaintext: str) -> str:
    """The last few characters of a credential, for telling keys apart.

    || Los últimos caracteres de una credencial, para distinguir claves.
    """
    tail = plaintext[-_HINT_CHARS:] if len(plaintext) > _HINT_CHARS else ""
    return f"…{tail}" if tail else "…"
