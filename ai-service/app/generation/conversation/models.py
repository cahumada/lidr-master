"""The shapes a session keeps between turns.

Three storage slots, and the difference between them is what each one costs
when it is lost:

* ``facts`` — structured, small, and the only thing the resolver reads. They
  are re-rendered into the system prompt every turn rather than stored as
  messages, so no trim can evict them.
* ``anchors`` — scope constraints the user pinned on purpose. Evicting one
  silently changes what the next turn retrieves, so the sliding window never
  touches them.
* ``turns`` — the recent window. Losing one costs a repeated sentence, which
  is why this is the slot the budget trims first.

|| Las formas que una sesión conserva entre turnos. Tres slots, y lo que los
distingue es cuánto cuesta perder cada uno: los ``facts`` son chicos y son lo
único que lee el resolver; los ``anchors`` son restricciones que el usuario
fijó a propósito y desalojarlos cambiaría en silencio lo que recupera el
turno siguiente; los ``turns`` son la ventana reciente, y perder uno cuesta
una frase repetida — por eso es lo primero que recorta el presupuesto.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

# What an anchor can pin. Deliberately the two filters the retriever already
# understands: an anchor that named something `SearchFilters` cannot express
# would be a promise the pipeline has no way to keep.
# || Lo que un anchor puede fijar. A propósito, los dos filtros que el
# retriever ya entiende: un anchor que nombrara algo que `SearchFilters` no
# sabe expresar sería una promesa que el pipeline no puede cumplir.
AnchorKind = Literal["module_code", "window_type_name"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ConversationFacts(BaseModel):
    """The durable facts of a session, re-rendered into the prompt each turn.

    The analogue of the course's ``ProjectMetadata``, with this domain's
    content: which filters are in play, which transaction codes have been
    named, and what the previous answer actually cited.

    ``last_document_ids`` is the referent the resolver reaches for. It is
    REPLACED each turn rather than accumulated — "the documents the previous
    answer cited" stops being true the moment it means "the documents some
    earlier answer cited".

    || Los hechos durables de una sesión, re-renderizados en el prompt cada
    turno. El análogo de la ``ProjectMetadata`` del curso con el contenido de
    este dominio. ``last_document_ids`` es el referente que busca el resolver
    y se REEMPLAZA cada turno en vez de acumularse: «los documentos que citó
    la respuesta anterior» deja de ser cierto apenas significa «los que citó
    alguna respuesta anterior».
    """

    module_code: list[str] = Field(default_factory=list)
    window_type_name: list[str] = Field(default_factory=list)
    transaction_codes: list[str] = Field(default_factory=list)
    last_document_ids: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        """No fact has been established yet. || Todavía no hay ningún hecho."""
        return not (
            self.module_code
            or self.window_type_name
            or self.transaction_codes
            or self.last_document_ids
        )

    def merge_with(self, update: ConversationFacts) -> ConversationFacts:
        """Union the accumulating lists; replace what describes only the last turn.

        Filters and transaction codes accumulate: naming a second module does
        not un-name the first. ``last_document_ids`` is overwritten, and an
        empty update leaves it alone — a turn that cited nothing should not
        erase the referent the next question may need.

        || Une las listas que acumulan y reemplaza lo que describe solo al
        último turno. Un update vacío de ``last_document_ids`` no lo borra: un
        turno que no citó nada no debería llevarse el referente que la
        pregunta siguiente quizá necesite.
        """
        return ConversationFacts(
            module_code=_union(self.module_code, update.module_code),
            window_type_name=_union(self.window_type_name, update.window_type_name),
            transaction_codes=_union(self.transaction_codes, update.transaction_codes),
            last_document_ids=update.last_document_ids or self.last_document_ids,
        )


def _union(current: list[str], incoming: list[str]) -> list[str]:
    """Case-insensitive union that preserves first-seen order.

    || Unión case-insensitive que conserva el orden de aparición.
    """
    merged = list(current)
    seen = {value.casefold() for value in merged}
    for value in incoming:
        if value.casefold() not in seen:
            merged.append(value)
            seen.add(value.casefold())
    return merged


class Turn(BaseModel):
    """One closed exchange. || Un intercambio cerrado.

    Both questions are kept: ``question`` is what the user typed and
    ``resolved_question`` is what was actually retrieved. When they differ,
    that difference is the most useful thing in the record — it is where a
    wrong answer to a well-formed question gets explained.
    """

    question: str
    resolved_question: str
    answer: str
    created_at: datetime = Field(default_factory=_utcnow)


class Anchor(BaseModel):
    """A scope constraint the user pinned explicitly.

    ``source_question`` is kept so the console can say WHY a filter is being
    applied. A filter with no visible origin is indistinguishable from a bug.

    || Una restricción de alcance que el usuario fijó explícitamente.
    ``source_question`` se conserva para que la consola pueda decir POR QUÉ se
    aplica un filtro: un filtro sin origen visible no se distingue de un bug.
    """

    kind: AnchorKind
    value: str
    source_question: str
    created_at: datetime = Field(default_factory=_utcnow)


class ConversationSession(BaseModel):
    """A conversation: its facts, its pinned constraints and its recent turns.

    || Una conversación: sus hechos, sus restricciones fijadas y sus turnos
    recientes.
    """

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    facts: ConversationFacts = Field(default_factory=ConversationFacts)
    anchors: list[Anchor] = Field(default_factory=list)
    turns: list[Turn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def append_turn(self, turn: Turn, *, max_turns: int) -> None:
        """Add a closed turn and trim the window to ``max_turns``.

        Trimming happens here and not in a separate policy: unlike the
        course, this window holds no anchors to promote and no summary to
        fold into — the pieces that earned a policy object there do not exist
        here, and one would be an indirection with a single caller.

        || Agrega un turno cerrado y recorta la ventana. El recorte vive acá y
        no en una política aparte: a diferencia del curso, esta ventana no
        tiene anchors que promover ni resumen al que plegar — las piezas que
        allá justificaban un objeto de política acá no existen, y sería una
        indirección con un solo llamador.
        """
        self.turns.append(turn)
        if len(self.turns) > max_turns:
            del self.turns[: len(self.turns) - max_turns]
        self.updated_at = _utcnow()

    def pin(self, anchors: list[Anchor]) -> list[Anchor]:
        """Add anchors that are not pinned yet, returning the ones added.

        || Agrega los anchors que todavía no están fijados y devuelve cuáles.
        """
        existing = {(anchor.kind, anchor.value.casefold()) for anchor in self.anchors}
        added: list[Anchor] = []
        for anchor in anchors:
            key = (anchor.kind, anchor.value.casefold())
            if key in existing:
                continue
            existing.add(key)
            self.anchors.append(anchor)
            added.append(anchor)
        if added:
            self.updated_at = _utcnow()
        return added

    def unpin(self, kind: AnchorKind, value: str) -> bool:
        """Remove one pinned constraint. || Quita una restricción fijada."""
        before = len(self.anchors)
        self.anchors = [
            anchor
            for anchor in self.anchors
            if not (anchor.kind == kind and anchor.value.casefold() == value.casefold())
        ]
        removed = len(self.anchors) != before
        if removed:
            self.updated_at = _utcnow()
        return removed

    def anchored_filters(self) -> dict[str, list[str]]:
        """The pinned constraints as retrieval filters.

        || Las restricciones fijadas, como filtros de recuperación.
        """
        filters: dict[str, list[str]] = {}
        for anchor in self.anchors:
            filters.setdefault(anchor.kind, []).append(anchor.value)
        return filters
