"""Tests for heading parsing and for the human name of a heading.

The contextual header is embedded and `metadata.section` is a filterable
field, so neither may carry the Word export's markup. Every raw heading used
here is a real one from the corpus.

|| Tests del parseo de headings y del nombre humano de un heading. El header
contextual se embebe y `metadata.section` es campo filtrable, así que ninguno
puede llevar el marcado del export de Word. Cada heading crudo usado acá es uno
real del corpus.
"""

from __future__ import annotations

import pytest

from app.generation.rag.chunking.functional_spec import (
    FunctionalSpecChunker,
    heading_text,
    parse_sections,
)

# --- A heading pattern must not cross a line break ---------------------------


def test_an_empty_h2_does_not_swallow_the_next_heading():
    """`re.MULTILINE` moves the anchors; it does not stop `\\s+` from eating a
    newline. The export emits a bare `##`, and with `\\s+` the heading below it
    became the empty one's NAME."""
    text = "# Previsión de incobrables\n\n## Efecto\n\nCuerpo.\n\n##\n\n## Notas al programador\n\nTodos los valores.\n"

    names = [name for name, _ in parse_sections(text)]

    assert "Notas al programador" in names
    assert "## Notas al programador" not in names


def test_an_empty_h2_followed_by_prose_invents_no_section():
    """68 phantom sections in the corpus were a body paragraph promoted to a
    section name."""
    text = "# Doc\n\n## Efecto\n\nPrimer párrafo.\n\n##\n\nTodos los valores son expresados en moneda original.\n"

    names = [name for name, _ in parse_sections(text)]

    assert names == ["Efecto"]
    assert "Todos los valores son expresados en moneda original." not in names


def test_the_body_of_a_swallowed_heading_stays_with_it():
    """Reattributing content to a section that does not exist under that name
    is the part that is not cosmetic."""
    text = "# Doc\n\n##\n\n## Notas al programador\n\nTodos los valores son expresados en moneda original.\n"

    sections = dict(parse_sections(text))

    assert "Todos los valores" in sections["Notas al programador"]


def test_an_empty_h1_does_not_swallow_the_title():
    from app.generation.rag.chunking.functional_spec import extract_document_title

    assert extract_document_title("#\n\n# Asientos automáticos de primas\n\n## Efecto\n\nx\n") == (
        "Asientos automáticos de primas"
    )


def test_a_tab_still_separates_a_heading_from_its_text():
    assert [name for name, _ in parse_sections("# D\n\n##\tCampos\n\nCuerpo.\n")] == ["Campos"]


# --- heading_text: the human name --------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Emphasis split between two adjacent Word bold runs: the space between
        # them did not survive the export.
        ("**Función****General**", "Función General"),
        ("**Información********Técnica**", "Información Técnica"),
        ("**Información******Técnica**", "Información Técnica"),
        ("**Proceso****Batch**", "Proceso Batch"),
        ("**Proceso********Batch**", "Proceso Batch"),
        ("**Frecuencia****de****Ejecución**", "Frecuencia de Ejecución"),
        # Emphasis that closed away from the edges.
        ("**Proceso** Batch", "Proceso Batch"),
        # A heading that is a link: the label is the name, the URL is not.
        ("[Campos](../../seguridad/valschemaoffice.html)", "Campos"),
        ("[Validaciones](../ma5578.html)", "Validaciones"),
        ("[Observaciones](../reportes/CAL013_incidencias.jpg)", "Observaciones"),
        # A Word bullet glyph opening the heading, plus the export's escapes.
        ("o _Ramo \\(parámetro\\)._", "Ramo (parámetro)."),
        ("o _Producto \\(parámetro\\)_", "Producto (parámetro)"),
        ("· _Código del ramo comercial \\(nBranch\\)", "Código del ramo comercial (nBranch)"),
        ("§ _Se obtiene la sumatoria_", "Se obtiene la sumatoria"),
        # A bullet_path element that arrives carrying its own `#` marker.
        ("### **Modo de generación: Detallado", "Modo de generación: Detallado"),
        ("#### Páginas asociadas", "Páginas asociadas"),
        # Already clean: untouched.
        ("Notas al programador", "Notas al programador"),
        ("Proceso batch", "Proceso batch"),
    ],
)
def test_heading_text_on_real_corpus_headings(raw, expected):
    assert heading_text(raw) == expected


# --- The underscore trap ------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "Conteo de unidades por unit_type",
        "Detección del tipo de unidad (unit_type)",
        "`(CAC1014_K)`",
        "`(CAC1024_k)`",
    ],
)
def test_an_underscore_inside_a_word_is_not_emphasis(raw):
    """CommonMark: `foo_bar_baz` carries no emphasis, `a*b*c` does. Without
    that distinction, cleaning emphasis breaks the domain's identifiers —
    `unit_type` would become `unit type`."""
    assert heading_text(raw) == raw


def test_an_asterisk_between_two_word_characters_becomes_a_space():
    """The counterpart of the rule above: `*` inside a word IS emphasis, so the
    run marks a boundary Word lost."""
    assert heading_text("Función****General") == "Función General"


# --- The `o` glyph is also a Spanish word -------------------------------------


def test_a_leading_o_is_only_a_glyph_when_a_name_follows_it():
    """`o` is both Word's second-level bullet and the Spanish for "or". It is
    taken as a glyph only before a capital, a quote or an emphasis marker —
    the shape of all 267 such headings in the corpus."""
    assert heading_text("o _Ramo \\(parámetro\\)._") == "Ramo (parámetro)."
    assert heading_text("oDescripción de la compañía") == "Descripción de la compañía"
    assert heading_text("o «Total»") == "«Total»"
    # Used as a word, it survives.
    assert heading_text("o dos opciones") == "o dos opciones"
    assert heading_text("uno o varios procesos") == "uno o varios procesos"


# --- Edge cases ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("**.******", "."),  # the junk heading the export emits
        ("**", ""),
    ],
)
def test_heading_text_degenerate_input(raw, expected):
    assert heading_text(raw) == expected


def test_heading_text_collapses_runs_of_spaces():
    assert heading_text("##   Campos    asociados") == "Campos asociados"


# --- It reaches the chunk -------------------------------------------------------


def test_the_section_metadata_carries_the_clean_name():
    text = (
        "# Preparación de cuentas corrientes\n\n(AGL001)\n\n"
        "## **Proceso****Batch**\n\nSe procesan los movimientos del período.\n"
    )
    documents = FunctionalSpecChunker().chunk("agl001.md", text)

    sections = {c.metadata.section for d in documents for c in d.chunks}
    assert sections == {"Proceso Batch"}


def test_the_contextual_header_carries_the_clean_name():
    text = (
        "# Carga de pólizas\n\n(CAL013)\n\n"
        "## [Campos](../../seguridad/valschemaoffice.html)\n\n"
        "| Campo | Descripción |\n|---|---|\n| Póliza | Número de póliza |\n"
    )
    documents = FunctionalSpecChunker().chunk("cal013.md", text)
    chunk = documents[0].chunks[0]

    assert "[Sección: Campos]" in chunk.text
    assert "valschemaoffice.html" not in chunk.text


def test_a_chunk_id_slug_is_unaffected_by_emphasis():
    """`_slugify` already collapses non-alphanumerics, so the emphasis cases
    keep their id — only the sections that were a link change theirs."""
    text = "# Doc\n\n(AGL001)\n\n## **Proceso****Batch**\n\nCuerpo del proceso.\n"
    documents = FunctionalSpecChunker().chunk("agl001.md", text)

    assert documents[0].chunks[0].chunk_id.startswith("AGL001::proceso_batch::")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("> ### Proceso", "Proceso"),
        ("> > #### Campo", "Campo"),
        ("># Título", "Título"),
    ],
)
def test_a_blockquote_marker_does_not_shield_the_heading_marker(raw, expected):
    """The export nests them (`> ### Proceso`). Stripping only one left the
    other in 211 contextual headers."""
    assert heading_text(raw) == expected


@pytest.mark.parametrize("raw", ["`<DF009>`", "Se inserta en la tabla (`IBNR`)."])
def test_backticks_are_kept(raw):
    """A backtick marks an identifier, not formatting: `<DF009>` is the
    per-client customization marker the design keeps on purpose, and `IBNR` is
    a table name. Stripping them would erase meaning, not noise."""
    assert heading_text(raw) == raw


def test_an_escaped_hash_is_content_not_a_marker():
    r"""The corpus writes a literal hash in report layouts. Unescaping happens
    after the leading-marker strip, so `\#` never becomes a live marker."""
    assert heading_text(r"Página: \#Número de página") == "Página: #Número de página"
    assert heading_text("# Título real") == "Título real"


# --- A heading must never take its body with it -------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("[](../mantenimiento/ma0085.html)", "MA0085"),
        ("[.](../seguridad/valschemaoffice.html)", "VALSCHEMAOFFICE"),
        ("[.](../maintenance/ma6023.html)", "MA6023"),
    ],
)
def test_a_link_heading_with_no_usable_label_falls_back_to_its_target(raw, expected):
    """Regression: cleaning these down to nothing made them junk headings, and
    a junk heading is dropped WITH its body. MS010 lost its seven validation
    rules and their error codes (10208, 10209, 12039, 10885) that way. The link
    target is the only name left, so it becomes the name."""
    assert heading_text(raw) == expected


def test_the_body_of_a_label_less_link_heading_survives():
    text = (
        "# Tipos de secuencia\n\n(MS010)\n\n"
        "## [](../mantenimiento/ma0085.html)\n\n"
        "| Campo | Validacion | Error |\n|---|---|---|\n"
        "| Codigo | Debe estar lleno | 10208 |\n"
    )
    documents = FunctionalSpecChunker().chunk("ms010.md", text)

    todo = " ".join(c.text for d in documents for c in d.chunks)
    assert "10208" in todo, "the error code must not disappear with its heading"
    assert "MA0085" in todo
