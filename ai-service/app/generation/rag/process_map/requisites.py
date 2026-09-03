"""Extract declared execution precedence from a document's ``Requisitos`` section.

The map will be used to answer *"what do I have to run first"*, so an invented
edge here is worse than a missing one. Nothing is inferred: an edge exists only
where a document says so.

The declaration is split in two in the source -- the lead-in carries the meaning
(*"requiere que previamente se ejecute"*) and what follows carries the codes --
so it is read in two steps, and over the whole SECTION rather than chunk by
chunk. The ``Requisitos`` section of ``COL502`` becomes four chunks: three table
rows holding the codes and one narrative holding the lead-in, so chunk by chunk
the two never meet. Per chunk this yields 9 edges; per section, 39.

Measured scope: of 228 ``Requisitos`` sections, 122 say ``No aplica.``, 105 are
requirements of another kind (permissions, loaded data, "should run at night")
and **25 declare precedence**.

|| Extrae la precedencia de ejecución declarada en la sección ``Requisitos``.

El mapa se va a usar para responder *"qué tengo que correr antes"*, así que una
arista inventada acá es peor que una faltante. No se infiere nada: una arista
existe solo donde un documento lo dice.

La declaración está partida en dos en el fuente —el enunciado lleva el
significado y lo que sigue lleva los códigos— así que se lee en dos pasos, y
sobre la SECCIÓN completa y no chunk por chunk. La sección ``Requisitos`` de
``COL502`` son cuatro chunks: tres filas de tabla con los códigos y uno narrativo
con el enunciado, así que chunk por chunk los dos nunca se encuentran. Por chunk
esto rinde 9 aristas; por sección, 39.

Alcance medido: de 228 secciones ``Requisitos``, 122 dicen ``No aplica.``, 105
son requisitos de otra clase y **25 declaran precedencia**.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

# The section this reads. Matched case-insensitively on its prefix, because the
# corpus writes both `Requisitos` and `Requisitos de ejecución`.
# || La sección que esto lee. Se matchea sin distinguir mayúsculas y por
# prefijo, porque el corpus escribe `Requisitos` y `Requisitos de ejecución`.
SECTION_PREFIX = "requisito"

# Lead-ins that declare precedence, all taken from the corpus. A `Requisitos`
# section without one of these carries a requirement of another kind --
# permissions, loaded data, "should be a nightly process" -- which is NOT
# precedence between processes and must not produce an edge.
# || Enunciados que declaran precedencia, todos tomados del corpus. Una sección
# `Requisitos` sin uno de estos lleva un requisito de otra clase —permisos,
# datos cargados, "debería ser un proceso nocturno"— que NO es precedencia entre
# procesos y no debe producir una arista.
PRECEDENCE_LEAD_IN = re.compile(
    r"requiere\s+que\s+previamente"
    r"|requiere\s+que\s+se\s+ejecute"
    r"|requiere\s+la\s+ejecuci[oó]n"
    r"|previamente\s+se\s+debe"
    r"|se\s+deben?\s+ejecutar\s+antes"
    r"|antes\s+de\s+ejecutar"
    # `CRL663` writes "Antes de la ejecución de este proceso se deben ejecutar
    # los siguiemtes otros" -- typo and all. Matching the lead-in verb phrase
    # rather than the list phrase is what survives that.
    # || `CRL663` escribe "Antes de la ejecución de este proceso se deben
    # ejecutar los siguiemtes otros" — con typo. Matchear el enunciado y no la
    # frase de la lista es lo que sobrevive a eso.
    r"|antes\s+de\s+la\s+ejecuci[oó]n"
    r"|se\s+debe\s+haber\s+ejecutado",
    re.IGNORECASE,
)

# A code inside a markdown link: the corpus links a dependency as
# `[COL500](col500.html)`.
# || Un código dentro de un enlace markdown.
_LINKED_CODE = re.compile(r"\[[^\]]*\]\(([^)]*?)\.html[^)]*\)", re.IGNORECASE)

# A bare transaction code. `COL520` writes its dependencies as plain text
# (`Código: COL500 Descripción: Generación de cobranzas`) with no link at all,
# and skipping those cost 24 of the 39 edges.
# || Un código de transacción suelto. `COL520` escribe sus dependencias como
# texto plano, sin ningún enlace, y saltearlas costaba 24 de las 39 aristas.
_BARE_CODE = re.compile(r"\b([A-Z]{2,4}\d{2,5}(?:[_-]?[A-Za-z0-9]{1,3})?)\b")


@dataclass(frozen=True)
class Precedence:
    """What one document declares it needs run first.

    || Lo que un documento declara que necesita corrido antes.
    """

    document_id: str
    requires: tuple[str, ...]
    # Declared but with no code named: `SIL500` says "previamente se debe
    # ejecutar la interfaz que alimenta la tabla temporal de siniestros". That
    # is a real dependency whose target cannot be resolved, and dropping it
    # would hide a declaration the document made.
    # || Declarada pero sin código nombrado: es una dependencia real cuyo
    # destino no se puede resolver, y descartarla esconderia una declaracion
    # que el documento hizo.
    unresolved: bool = False
    # The lead-in that justified the extraction, so any edge can be audited
    # back to the sentence that produced it.
    # || El enunciado que justificó la extracción, así cualquier arista se puede
    # auditar hasta la oración que la produjo.
    evidence: str = ""


def section_text(chunks) -> str:
    """Join a document's ``Requisitos`` chunks back into one section.

    The header is stripped from each: it repeats the document title and section
    name, and the title would contribute its own codes.

    || Vuelve a juntar los chunks de ``Requisitos`` de un documento en una
    sección. A cada uno se le quita el header: repite el título del documento y
    el nombre de la sección, y el título aportaría códigos propios.
    """
    bodies = []
    for chunk in chunks:
        text = chunk["text"] if isinstance(chunk, dict) else chunk.text
        bodies.append(text.split("\n", 2)[-1])
    return "\n".join(bodies)


def declares_precedence(text: str) -> bool:
    """Whether this section declares that something must run first.

    || Si esta sección declara que algo tiene que correr antes.
    """
    return PRECEDENCE_LEAD_IN.search(text) is not None


def _evidence(text: str) -> str:
    match = PRECEDENCE_LEAD_IN.search(text)
    if match is None:
        return ""
    start = text.rfind("\n", 0, match.start()) + 1
    end = text.find("\n", match.end())
    line = text[start : end if end != -1 else len(text)]
    return " ".join(line.split())[:200]


def extract_codes(text: str, *, exclude: str, known: set[str]) -> tuple[str, ...]:
    """Codes named in the section, restricted to documents that exist.

    Restricted on purpose: an unknown code is a typo in the source or a
    transaction outside this corpus, and either way an edge pointing at nothing
    would make the map look more connected than it is.

    || Códigos nombrados en la sección, restringidos a documentos que existen.
    Restringido a propósito: un código desconocido es un typo del fuente o una
    transacción fuera de este corpus, y en cualquier caso una arista que apunta
    a la nada haría ver el mapa más conectado de lo que está.
    """
    found = {match.group(1).rsplit("/", 1)[-1].upper() for match in _LINKED_CODE.finditer(text)}
    found |= {match.group(1).upper() for match in _BARE_CODE.finditer(text)}
    found.discard(exclude.upper())
    return tuple(sorted(code for code in found if code in known))


def extract_precedence(
    document_id: str, requisitos_chunks, *, known_documents: set[str]
) -> Precedence | None:
    """The precedence one document declares, or ``None`` when it declares none.

    || La precedencia que declara un documento, o ``None`` si no declara ninguna.
    """
    if not requisitos_chunks:
        return None

    text = section_text(requisitos_chunks)
    if not declares_precedence(text):
        return None

    codes = extract_codes(text, exclude=document_id, known=known_documents)
    if not codes:
        logger.info("precedence_declared_without_target", document_id=document_id)
        return Precedence(document_id=document_id, requires=(), unresolved=True,
                          evidence=_evidence(text))
    return Precedence(document_id=document_id, requires=codes, evidence=_evidence(text))
