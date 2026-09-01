"""Tests for the fourth broken-table shape: headers and labels with no pipes.

`cp001.md` exports its `Campos` catalogue as `#### Título` / `#### Descripción`
followed by `#### _Field_` + prose. No pipe is involved, so the three piped
shapes miss it and every cell becomes a loose narrative chunk — with the field
NAME severed from its description.

|| Tests de la cuarta forma de tabla rota: headers y etiquetas sin pipes.
`cp001.md` exporta su catálogo de `Campos` como `#### Título` /
`#### Descripción` seguido de `#### _Campo_` + prosa. No hay ningún pipe, así
que las tres formas con pipes no la ven y cada celda termina como un chunk
narrativo suelto — con el NOMBRE del campo separado de su descripción.
"""

from __future__ import annotations

import pytest

from app.generation.rag.chunking.functional_spec import (
    FunctionalSpecChunker,
    _split_row,
    parse_markdown_table,
)
from app.generation.rag.chunking.normalizer import repair_broken_tables

CP001_SHAPE = """##  Campos

####  Título

####  Descripción

####  _Moneda_

Código de la moneda en la que se lleva la contabilidad de esta compañía.

####  _Ejercicio_

Número de ejercicios o cierres anuales que tiene la compañía contable.
"""


def test_the_field_name_travels_with_its_description() -> None:
    headers, rows = parse_markdown_table(repair_broken_tables(CP001_SHAPE).split("##  Campos")[1])
    assert headers == ["Título", "Descripción"]
    assert rows[0][0] == "Moneda"
    assert "Código de la moneda" in rows[0][1]
    assert rows[1][0] == "Ejercicio"


def test_the_repaired_catalogue_becomes_one_chunk_per_field() -> None:
    document = f"# **Instalación contable**\n\n`**(CP001)**`\n\n{CP001_SHAPE}"
    chunks = FunctionalSpecChunker().chunk("cp001.md", document)[0].chunks
    campos = [c for c in chunks if c.metadata.section.strip() == "Campos"]
    assert [c.metadata.chunk_type for c in campos] == ["table", "table"]
    assert {c.metadata.field for c in campos} == {"Moneda", "Ejercicio"}
    moneda = next(c for c in campos if c.metadata.field == "Moneda")
    assert "Título: Moneda" in moneda.text, "the name is in the embedded text, not only in metadata"


def test_an_italic_run_member_is_a_row_label_not_a_column() -> None:
    """`Título` / `Descripción` / `_Parte repetitiva_` is 2 columns, not 3.

    || `Título` / `Descripción` / `_Parte repetitiva_` son 2 columnas, no 3.
    """
    source = """##  Campos

####  Título

####  Descripción

####  _Parte repetitiva_

####  _Sel_

Permite seleccionar los elementos que deben ser depositados.

####  _Banco_

Banco asociado al cheque pendiente por depositar.
"""
    headers, rows = parse_markdown_table(repair_broken_tables(source).split("##  Campos")[1])
    assert headers == ["Título", "Descripción"]
    labels = [row[0] for row in rows]
    assert labels == ["Parte repetitiva", "Sel", "Banco"]
    assert rows[0][1] == "", "a group divider is kept as a label-only row, not dropped"


def test_a_run_whose_rows_do_not_line_up_is_not_repaired() -> None:
    """Padding a short row at the end would put a value in the wrong column.

    In `mer001.md` the `Temporal` flag would land under `Tipo de Raíz del
    Error`, asserting a business fact the document never states.

    || Rellenar una fila corta al final pondría un valor en la columna
    equivocada: en `mer001.md` la bandera `Temporal` caería bajo `Tipo de Raíz
    del Error`, afirmando un hecho que el documento nunca dice.
    """
    source = """##  Valores definidos

####  Tipo de Error

####  Explicación

####  Tipo de Raíz

####  Temporal

####  _1. Especificaciones_

El error se debe a especificaciones incorrectas.

No

####  _1.1 Especificaciones incorrectas_

Las especificaciones indican que la transacción está mal ejecutada.

1. Especificaciones

No
"""
    assert repair_broken_tables(source) == source, "an asymmetric block is left alone"


def test_a_real_heading_followed_by_prose_is_untouched() -> None:
    source = """##  Función

####  Paso uno

Se valida el acceso del usuario a la sucursal.

####  Paso dos

Se registra el movimiento contable.
"""
    assert repair_broken_tables(source) == source


# --- The render/parse round trip || El viaje de ida y vuelta ---------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("| Ramo | Debe estar lleno | 01022 |", ["Ramo", "Debe estar lleno", "01022"]),
        # An escaped pipe belongs to the cell's text, not to the table.
        # || Un pipe escapado es parte del texto de la celda, no de la tabla.
        (r"| Fecha | posterior a la fecha \|de emisión | 07071 |",
         ["Fecha", "posterior a la fecha |de emisión", "07071"]),
    ],
)
def test_a_row_splits_only_on_unescaped_pipes(line: str, expected: list[str]) -> None:
    assert _split_row(line) == expected
