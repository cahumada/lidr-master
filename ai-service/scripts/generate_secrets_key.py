"""Genera una SECRETS_KEY para cifrar credenciales guardadas en la base.

    uv run python scripts/generate_secrets_key.py

Imprime una clave y NO la guarda en ningún lado: copiarla al entorno es a
propósito un paso manual. La clave es lo único que separa un `pg_dump` con
ciphertext de uno con credenciales legibles, así que no puede terminar en un
archivo del repo por descuido de este script.

Dos cosas que conviene saber antes de rotarla:

* Rotar la clave vuelve **ilegibles** las credenciales ya guardadas. El
  servicio lo reporta (las trata como "sin credencial") en vez de pasarle un
  valor roto al proveedor, pero hay que volver a cargarlas.
* Restaurar un dump en otro entorno necesita la MISMA clave, o las
  credenciales de ese dump no se pueden leer ahí. Eso es la propiedad, no un
  problema: es lo que hace que el dump solo no alcance.

|| Generates a SECRETS_KEY for encrypting credentials stored in the database.
Prints a key and stores it NOWHERE: copying it into the environment is a
deliberate manual step, because that key is the only thing separating a
`pg_dump` full of ciphertext from one full of readable credentials.

Rotating it makes already-stored credentials unreadable (reported as "no
credential", never passed to a provider broken), and restoring a dump
elsewhere needs the SAME key — which is the property, not a problem.
"""

from __future__ import annotations


def main() -> None:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("utf-8")
    print(key)
    print()
    print("Pegala en el entorno del servicio (no en el repo):")
    print(f"  SECRETS_KEY={key}")
    print()
    print("En Railway: Settings -> Variables. En local: el .env, que está gitignoreado.")
    print("Sin esta variable, guardar credenciales desde la consola queda deshabilitado")
    print("y las variables de entorno por proveedor siguen funcionando igual.")


if __name__ == "__main__":
    main()
