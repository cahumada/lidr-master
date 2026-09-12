"""Assign an owner to the conversations that predate ownership.

`add-conversation-ownership` gave `conversation_sessions` an `owner_id`, and
the rows that already existed came out `NULL`. With the store's rule —absence
of identity is its own bucket, never a wildcard— those rows are invisible in
the console and intact in the database. This adjudicates them.

Assigning and not deleting: assigning is reversible and explicit, deleting is
neither. Run it with the console user id of whoever those conversations
actually belong to; `SELECT id, email FROM "User"` in the console's database is
where that id lives.

Idempotent: it only touches rows where `owner_id IS NULL`, so a second run
reports zero and changes nothing.

Usage:
    uv run python scripts/backfill_conversation_owner.py <owner_id>
    uv run python scripts/backfill_conversation_owner.py <owner_id> --yes

Without `--yes` it counts and exits without writing. Adjudicating somebody's
conversations is a decision, not a side effect of having typed a command.

|| Adjudica un dueño a las conversaciones anteriores a que hubiera dueños.
Las filas que ya existían quedaron en `NULL` y, por la regla del store, son
invisibles en la consola y están intactas en la base. Adjudicar es reversible
y explícito; borrar no es ninguna de las dos. Es idempotente: solo toca las
filas con `owner_id IS NULL`. Sin `--yes` cuenta y sale sin escribir.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings

# Same ceiling the header dependency enforces. An id that would not be accepted
# on a request must not be writable by a script either, or the backfill could
# create an owner nobody can ever present.
# || El mismo techo que impone la dependencia del header: un id que no se
# aceptaría en un request tampoco se puede escribir por script, o el backfill
# crearía un dueño que nadie puede presentar nunca.
MAX_OWNER_ID_CHARS = 64


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "owner_id",
        help="Console user id to assign. || Id de usuario de la consola a asignar.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually write. || Escribir de verdad.",
    )
    args = parser.parse_args()

    owner_id = args.owner_id.strip()
    if not owner_id:
        print("owner_id vacío.", file=sys.stderr)
        return 1
    if len(owner_id) > MAX_OWNER_ID_CHARS:
        print(
            f"owner_id supera los {MAX_OWNER_ID_CHARS} caracteres.",
            file=sys.stderr,
        )
        return 1

    import psycopg

    settings = get_settings()
    url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM conversation_sessions WHERE owner_id IS NULL"
        )
        row = cursor.fetchone()
        pending = int(row[0]) if row else 0

        print(f"conversaciones sin dueño: {pending}")
        if pending == 0:
            print("nada que adjudicar.")
            return 0

        if not args.yes:
            print(
                f"se adjudicarían a owner_id={owner_id!r}. "
                "Volvé a correrlo con --yes para escribir."
            )
            return 0

        cursor.execute(
            "UPDATE conversation_sessions SET owner_id = %s WHERE owner_id IS NULL",
            (owner_id,),
        )
        updated = cursor.rowcount
        connection.commit()

    print(f"adjudicadas a owner_id={owner_id!r}: {updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
