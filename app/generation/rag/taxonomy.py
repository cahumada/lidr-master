"""Classify a VisualTIME transaction code by type.

The naming convention this implements is recorded in
`openspec/domain/visualtime-navigation-taxonomy.md` §4 and is TACIT knowledge:
it is documented in no table, so it cannot be verified automatically. Two
consequences shape this module:

* The rules live as ORDERED DATA, not as code branches, so a counterexample is
  a one-line edit and the whole convention is auditable in one glance.
* An unrecognized code yields ``unknown`` WITH a reason, never a default type.
  A fabricated type propagates as if it were evidence.

|| Clasifica un código de transacción de VisualTIME por tipo.

La convención de nomenclatura que implementa está registrada en
`openspec/domain/visualtime-navigation-taxonomy.md` §4 y es conocimiento
TÁCITO: no está documentada en ninguna tabla, así que no se puede verificar
automáticamente. Eso tiene dos consecuencias que dan forma a este módulo:

* Las reglas viven como DATOS ORDENADOS, no como ramas de código, así un
  contraejemplo es una edición de una línea y toda la convención se audita de
  un vistazo.
* Un código no reconocido devuelve ``unknown`` CON su razón, nunca un tipo por
  defecto. Un tipo fabricado se propaga como si fuera evidencia.
"""

from __future__ import annotations

import re
from typing import Literal, NamedTuple

TransactionType = Literal[
    "interface",
    "key_request",
    "process_report",
    "query",
    "maintenance",
    "functional_abm",
    "menu_node",
    "unknown",
]


class TransactionClassification(NamedTuple):
    """A code's type plus, when it is ``unknown``, why.

    || El tipo de un código y, cuando es ``unknown``, por qué.
    """

    transaction_type: TransactionType
    reason: str | None = None


# Ordered (pattern, type) rules. ORDER IS LOAD-BEARING: the specific patterns
# must precede the generic one, since `MA0001`, `AGL001`, `AGC001` and
# `INT54050` all also match the generic `functional_abm` shape.
# Counts are the distinct document_ids each rule matches in the current corpus,
# recorded so a future edit can tell whether it moved more than it meant to.
# || Reglas (patrón, tipo) ordenadas. EL ORDEN ES ESTRUCTURAL: los patrones
# específicos deben preceder al genérico, ya que `MA0001`, `AGL001`, `AGC001` e
# `INT54050` también matchean la forma genérica de `functional_abm`. Los
# conteos son los document_id distintos que cada regla matchea en el corpus
# actual, anotados para que una edición futura pueda ver si movió más de lo que
# quería.
_RULES: tuple[tuple[re.Pattern[str], TransactionType], ...] = (
    # Developed from the Interfaces module, which is a generator with fixed
    # execution rules — unlike an `L`, where the programmer decides freely. (107)
    (re.compile(r"^INT\d+$"), "interface"),
    # `_k` / `_K` (and the single bare-`k` case, CA001k) is the key-request
    # companion of a main transaction. Its family type is reachable through
    # `parent_transaction_code`, so it is not re-derived here. (106)
    (re.compile(r"^[A-Z]{2,4}\d{1,5}_?[kK]$"), "key_request"),
    # `[Módulo]L[código]`: report, or a large DB process that alters entities. (375)
    (re.compile(r"^[A-Z]{2}L\d+$"), "process_report"),
    # `[Módulo]C[código]`: read-only consultation. (176)
    (re.compile(r"^[A-Z]{2,3}C\d+$"), "query"),
    # `M[Módulo][código]`: parameterizes master data. See the note below on why
    # the digits matter for telling a maintenance leaf from a menu folder. (667)
    (re.compile(r"^M[A-Z]{1,3}\d+$"), "maintenance"),
    # `[Módulo][código]` with neither L nor C: runs functionality and alters
    # the entities it acts on. Must stay LAST. (366)
    (re.compile(r"^[A-Z]{2,4}\d+$"), "functional_abm"),
)


# Why `M...` returns `maintenance` here instead of `unknown`.
#
# The domain note warns that an `M` code can be a maintenance leaf OR a menu
# folder, and that only the `WINDOWS` tree settles it — so the first design
# said: without that tree, answer `unknown`. Measuring the corpus refined it.
# The menu folders the note cites (`MCONTA`, `MERCP`, `MCAJBA`, `MGENER`) carry
# NO digits, and no digitless `M` code has a functional-spec document at all —
# `MENU` is the only one, and it does not match this rule. Every one of the 667
# `M<letters><digits>` codes here comes from a document describing a
# transaction, which is itself evidence of a leaf: folders get no
# Función/Campos/Validaciones document.
#
# Answering `unknown` for 667 documents on an ambiguity the data does not show
# would be false caution. The `WINDOWS` check stays the authoritative
# confirmation and is group 3 of the change.
# || Por qué `M...` devuelve `maintenance` y no `unknown`. La nota de dominio
# advierte que un código `M` puede ser hoja de mantenimiento O carpeta de menú,
# y que solo el árbol `WINDOWS` lo resuelve — así que el primer diseño decía:
# sin ese árbol, responder `unknown`. Medir el corpus lo refinó. Las carpetas
# de menú que cita la nota (`MCONTA`, `MERCP`, `MCAJBA`, `MGENER`) NO llevan
# dígitos, y ningún código `M` sin dígitos tiene documento de especificación
# funcional — `MENU` es el único, y no matchea esta regla. Los 667 códigos
# `M<letras><dígitos>` de acá vienen de documentos que describen una
# transacción, lo que ya es evidencia de hoja: las carpetas no tienen documento
# con Función/Campos/Validaciones. Responder `unknown` para 667 documentos por
# una ambigüedad que los datos no muestran sería falsa cautela. El chequeo
# contra `WINDOWS` sigue siendo la confirmación autoritativa, y es el grupo 3
# del cambio.


def classify_transaction_type(
    code: str, *, is_menu_node: bool | None = None
) -> TransactionClassification:
    """Classify ``code``, or return ``unknown`` with the reason.

    ``is_menu_node`` comes from the `WINDOWS` tree
    (:mod:`app.generation.rag.navigation`) and OVERRIDES the code patterns when
    known, because the structural fact beats the naming convention: a code with
    children is a menu folder whatever it looks like. `MA6835` is the case that
    proves it — indistinguishable from the 941 maintenance leaves by pattern
    alone, and actually a folder. Pass None when the tree is unavailable and
    the patterns decide on their own.

    || ``is_menu_node`` viene del árbol `WINDOWS`
    (:mod:`app.generation.rag.navigation`) y PISA los patrones de código cuando
    se conoce, porque el hecho estructural le gana a la convención de nombres:
    un código con hijos es carpeta de menú, sea cual sea su forma. `MA6835` es
    el caso que lo prueba — indistinguible de las 941 hojas de mantenimiento
    solo por patrón, y en realidad una carpeta. Pasar None cuando el árbol no
    está disponible y los patrones deciden solos.
    """
    candidate = code.strip()
    if not candidate:
        return TransactionClassification("unknown", "empty code")

    if is_menu_node:
        return TransactionClassification("menu_node")

    for pattern, transaction_type in _RULES:
        if pattern.match(candidate):
            return TransactionClassification(transaction_type)

    return TransactionClassification(
        "unknown", "matches no known code pattern (see openspec/domain §4)"
    )
