"""What role a table plays for a transaction, from declared signals only.

Ordered rules as DATA, not branches, same shape as ``taxonomy.py``: when a
counterexample shows up -- and it will -- a row is edited, not a function. A
table that matches nothing is ``unknown`` WITH ITS REASON, never a default.

**There is no `core` role, and that is a measurement result, not an omission.**
The plan proposed deriving it from a low global fan-in. Measured against the
four transactions the repo owner annotated by hand, that runs backwards:

    code     annotated table   fan-in      NOT annotated      fan-in
    CA014    COVER              1,037      NOPAYROLL              44
    CA025    CLIENT             1,925      CLIALLOPRO             42
    CA001    CERTIFICAT         1,989      CUR_ALLOW              30

A policy, a certificate and a client are touched by almost every routine in the
system BECAUSE they are the central entities. Rarity means peripheral, not
central. Nothing else declared separates them either -- routine kinds and
coverage rank the annotated tables high but do not isolate them -- so this
module emits what the dictionary declares and leaves the rest `unknown`,
ordered by coverage. Calling a table `core` on four annotated points would be
the manual calibration this repo refuses elsewhere.

|| Reglas ordenadas como DATOS, no ramas. Una tabla que no matchea nada es
``unknown`` CON SU RAZÓN. **No hay rol `core`, y eso es un resultado de
medición**: el fan-in bajo que proponía el plan corre al revés — las tablas que
el analista llama core son las de fan-in más alto del sistema.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

TableRole = Literal["reference", "historical", "message", "validation", "unknown"]

ROLES: tuple[TableRole, ...] = (
    "reference",
    "historical",
    "message",
    "validation",
    "unknown",
)

# Which kind of work a routine name announces. Ordered: the specific prefixes
# come before the generic `INS`, exactly like the code taxonomy.
# || Qué clase de trabajo anuncia el nombre de una rutina. Ordenado: los
# prefijos específicos antes del genérico `INS`.
RoutineKind = Literal["validation", "post", "pre", "execute", "copy", "read", "write", "unknown"]

ROUTINE_PREFIXES: tuple[tuple[str, RoutineKind], ...] = (
    ("INSVAL", "validation"),
    ("INSPOST", "post"),
    ("INSPRE", "pre"),
    ("INSEXECUTE", "execute"),
    ("INSCOPY", "copy"),
    ("REA", "read"),
    ("INS", "write"),
)

# `TABLE<n>` is a generic fixed-content table -- the `MAnnnn` of the corpus,
# validated in domain §6.1.
# || `TABLE<n>` es una tabla genérica de contenido fijo.
_GENERIC_TABLE = re.compile(r"^TABLE\d+$", re.IGNORECASE)

# The system's own message tables, domain §6.
# || Las tablas de mensajes del sistema.
_MESSAGE_TABLES = frozenset({"MESSAGE", "WIN_MESSAG"})

_FIXED_CONTENT = "contenido fijo"
_HISTORY_PREFIX = "historia"


def routine_kind(name: str) -> RoutineKind:
    """What the routine's name announces, or ``unknown`` when no prefix matches.

    445 of the anchored routines carry no known prefix or only the generic
    `INS`; this returns `write` for the generic one and `unknown` for the rest
    rather than guessing.

    || Lo que anuncia el nombre de la rutina, o ``unknown`` si ningún prefijo
    matchea.
    """
    upper = name.upper()
    for prefix, kind in ROUTINE_PREFIXES:
        if upper.startswith(prefix):
            return kind
    return "unknown"


def classify_role(
    *,
    table_name: str,
    description: str | None,
    via_routines: Sequence[str],
) -> tuple[TableRole, str]:
    """The role and the reason, from the dictionary first and the path second.

    Destination signals beat path signals: what the table IS outranks how it
    was reached. Returns ``("unknown", reason)`` when no rule applies -- the
    reason names what was seen, so a reader can tell "nothing matched" from
    "nothing was looked at".

    || El rol y su razón. Las señales del destino le ganan a las del camino.
    """
    upper = table_name.upper()
    text = (description or "").strip().lower()

    if _GENERIC_TABLE.match(upper):
        return "reference", f"{upper} es una tabla genérica de contenido fijo (TABLE<n>)"
    if _FIXED_CONTENT in text:
        return "reference", "el diccionario la declara de contenido fijo"
    if upper in _MESSAGE_TABLES:
        return "message", f"{upper} es una tabla de mensajes del sistema"
    if upper.endswith("_HIS"):
        return "historical", "el sufijo _HIS declara una tabla de historia"
    if text.startswith(_HISTORY_PREFIX):
        return "historical", "el diccionario la describe como historia"

    kinds = {routine_kind(name) for name in via_routines}
    if kinds and kinds == {"validation"}:
        return "validation", "solo la alcanzan rutinas de validación (INSVAL*)"

    seen = ", ".join(sorted(kinds)) if kinds else "ninguna rutina"
    return (
        "unknown",
        f"ninguna regla declarada aplica; rutinas vistas: {seen}",
    )
