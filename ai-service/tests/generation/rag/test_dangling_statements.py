"""Tests for the grammar rule that keeps a split statement together.

A unit whose text ends in a comma or a colon has not closed its statement; the
chunker joins it with what follows instead of emitting half a business rule.
The fixtures are verbatim excerpts of the real corpus.

|| Tests de la regla gramatical que mantiene junto un enunciado partido. Una
unidad cuyo texto termina en coma o dos puntos no cerró su enunciado; el
chunker la une con lo que sigue en vez de emitir media regla de negocio. Los
fixtures son extractos textuales del corpus real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.generation.rag.chunking.functional_spec import (
    FunctionalSpecChunker,
    _join_open_statements,
    _leaves_statement_open,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# A cap small enough that these short fixtures still go through the
# segment-and-descend path. At the production cap of 500 each fixture section
# would fit whole in one chunk and the join would never be exercised.
# || Un techo lo bastante chico como para que estos fixtures cortos igual pasen
# por el camino de segmentar y descender. Con el techo de producción de 500,
# cada sección de fixture entraría entera en un chunk y la unión nunca se
# ejercitaría.
SMALL_CAP = 150


def chunk_fixture(filename: str, cap: int = SMALL_CAP) -> list:
    content = (FIXTURES / filename).read_text(encoding="utf-8")
    documents = FunctionalSpecChunker(narrative_token_cap=cap).chunk(filename, content)
    assert len(documents) == 1
    return documents[0].chunks


# --- The discriminator itself || El discriminador mismo -------------------


@pytest.mark.parametrize(
    "text",
    [
        "De lo contrario,",
        "Dónde,",
        "En el detalle:",
        "### · _De la tabla de Situación impositiva del Cliente se obtiene:_",
        "·Período:",
        "Se obtiene:",
    ],
)
def test_these_leave_the_statement_open(text: str) -> None:
    assert _leaves_statement_open(text)


@pytest.mark.parametrize(
    "text",
    [
        # The 291 short real answers the length filter would have deleted.
        # || Las 291 respuestas reales cortas que el filtro por largo habría borrado.
        "No aplica.",
        "A petición del usuario.",
        "Volver a ejecutar.",
        "No",
        "·Se calcula el importe de Comisión Neta.",
        "Formato: Página",
        "",
    ],
)
def test_these_close_their_statement(text: str) -> None:
    assert not _leaves_statement_open(text)


def test_a_trailing_italic_marker_does_not_hide_the_colon() -> None:
    # The export wraps the line in italics, so the colon is not the last
    # character — the marker has to be stripped before the test.
    # || El export envuelve la línea en itálicas, así que los dos puntos no son
    # el último carácter — hay que sacar el marcador antes de la prueba.
    assert _leaves_statement_open("### o _La información se obtiene de:_")


# --- The join || La unión --------------------------------------------------


def test_join_absorbs_the_continuation() -> None:
    assert _join_open_statements(["Se obtiene:", "El importe neto."]) == [
        "Se obtiene:\n\nEl importe neto."
    ]


def test_join_keeps_absorbing_until_the_statement_closes() -> None:
    joined = _join_open_statements(["§Si A,", "·entonces B,", "·y C."])
    assert joined == ["§Si A,\n\n·entonces B,\n\n·y C."]


def test_join_leaves_closed_statements_untouched() -> None:
    segments = ["Primera regla.", "Segunda regla.", "Tercera regla."]
    assert _join_open_statements(segments) == segments


def test_a_statement_left_open_at_the_end_is_emitted_as_it_stands() -> None:
    # There is nothing ahead to join it to; dropping it would delete content.
    # || No hay nada adelante a lo cual unirlo; descartarlo borraría contenido.
    assert _join_open_statements(["Regla.", "Dónde,"]) == ["Regla.", "Dónde,"]


def test_join_never_reorders() -> None:
    segments = ["A:", "B.", "C,", "D."]
    assert "".join(_join_open_statements(segments)).replace("\n", "") == "A:B.C,D."


# --- End to end on the real corpus || Punta a punta sobre el corpus real ---


def test_the_agl009_connector_travels_with_the_branch_it_introduces() -> None:
    """`De lo contrario,` was emitted as a chunk of its own, 72 times.

    Worse than useless: the `else` branch left on its own reads as the `then`
    branch and inverts the business rule. Joined with its connector, the branch
    says out loud that it is the contrary case.

    What this rule does NOT do is reattach the `§Si <condición>` above, which
    closes its own sentence with a period. Doing that needs the glyph hierarchy
    the corpus does not reliably carry (see the change's design.md).

    || `De lo contrario,` se emitía como chunk propio, 72 veces. Peor que
    inútil: la rama `else` sola se lee como la rama `then` e invierte la regla
    de negocio. Unida a su conector, la rama dice en voz alta que es el caso
    contrario. Lo que esta regla NO hace es volver a pegar el `§Si <condición>`
    de arriba, que cierra su oración con punto.
    """
    chunks = chunk_fixture("agl009_conditional.md")
    narrative = [c for c in chunks if c.metadata.chunk_type == "narrative"]

    assert not any(
        c.text.rstrip().endswith("De lo contrario,") for c in narrative
    ), "the connector was emitted as a chunk of its own"

    holders = [c for c in narrative if "De lo contrario," in c.text]
    assert len(holders) == 1, "the connector lives in exactly one chunk"
    whole = holders[0].text
    assert "el importe de ajuste por mínimo de retención servicios sociales" in whole, (
        "the else branch travels with the connector that marks it as contrary"
    )


def test_the_cpl502_lead_in_travels_with_what_closes_it() -> None:
    """A lead-in ending in `:` is joined with the unit that closes the statement.

    The join restores the STATEMENT, not the whole list: a second sibling item
    already closes its own sentence and stays its own chunk.

    || Un lead-in que termina en `:` se une con la unidad que cierra el
    enunciado. La unión reconstruye el ENUNCIADO, no la lista entera: un
    segundo ítem hermano ya cierra su propia oración y queda como chunk propio.
    """
    chunks = chunk_fixture("cpl502_lead_in.md")
    holders = [
        c for c in chunks
        if "Situación impositiva del Cliente" in c.text and "se obtiene:" in c.text
    ]
    assert len(holders) == 1
    whole = holders[0].text
    assert "La condición ante el IVA" in whole, "the lead-in is no longer a chunk on its own"

    assert not any(
        c.text.rstrip().endswith("se obtiene:_") for c in chunks
    ), "no chunk ends on the open lead-in"


def test_short_real_answers_still_become_their_own_chunks() -> None:
    """The rule discriminates by content, never by length.

    || La regla discrimina por contenido, nunca por largo.
    """
    chunks = chunk_fixture("cpl500_short_answers.md")
    bodies = {c.text.split("\n", 2)[2].strip() for c in chunks}
    assert {"A petición del usuario.", "Volver a ejecutar.", "No aplica."} <= bodies


def test_a_complete_statement_declares_no_continuation() -> None:
    for chunk in chunk_fixture("cpl500_short_answers.md"):
        assert chunk.metadata.continued_from is None
        assert chunk.metadata.continues_into is None


# --- The residue the cap forces apart || El residuo que el techo separa -----

OVER_CAP = 200


def test_a_statement_over_the_cap_is_marked_not_forced() -> None:
    """Joining is bounded by the token cap, and what does not fit gets linked.

    Forcing the join would break the guarantee the embedding layer verifies
    before its first API call; dropping either side would delete a rule. So the
    pieces are emitted separately and each names its neighbour.

    || La unión está acotada por el techo de tokens, y lo que no entra queda
    enlazado. Unir a la fuerza rompería la garantía que la capa de embeddings
    verifica antes de su primera llamada a la API; descartar cualquiera de los
    dos lados borraría una regla. Así que las piezas se emiten separadas y cada
    una nombra a su vecina.
    """
    chunks = chunk_fixture("over_cap_statement.md", cap=OVER_CAP)
    assert len(chunks) > 1, "the fixture is meant to exceed the cap"

    for chunk in chunks:
        assert chunk.token_count <= OVER_CAP, f"{chunk.chunk_id} broke the cap"

    linked = [c for c in chunks if c.metadata.continues_into]
    assert linked, "an over-cap statement must declare where it continues"


def test_the_links_form_a_chain_in_both_directions() -> None:
    chunks = chunk_fixture("over_cap_statement.md", cap=OVER_CAP)
    by_id = {c.chunk_id: c for c in chunks}
    for chunk in chunks:
        target = chunk.metadata.continues_into
        if target is None:
            continue
        assert target in by_id, "a link must point at a chunk that was emitted"
        assert by_id[target].metadata.continued_from == chunk.chunk_id, "the link points back"
        assert by_id[target].metadata.section == chunk.metadata.section, "never across sections"
        assert by_id[target].metadata.document_id == chunk.metadata.document_id


def test_no_chunk_links_to_itself() -> None:
    for chunk in chunk_fixture("over_cap_statement.md", cap=OVER_CAP):
        assert chunk.metadata.continues_into != chunk.chunk_id
        assert chunk.metadata.continued_from != chunk.chunk_id
