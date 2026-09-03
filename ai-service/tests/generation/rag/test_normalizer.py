"""Unit tests for app.generation.rag.chunking.normalizer, against 3 real
broken-table fixtures taken verbatim from the corpus (CA014, CA001)."""

from __future__ import annotations

from app.generation.rag.chunking.normalizer import (
    repair_broken_tables,
    repair_broken_tables_with_trace,
)

# --- Fixture 1: CA014 "Ramos generales" — simple shape, 2 headers + 4 data rows ---
CA014_RAMOS_GENERALES = """**Ramos generales**

#### Información cambiada

#### Recálculorealizado

Capital |  Prima anual, en base a la tasa mostrada por el sistema
Tasa |  Prima anual, en base a la tasa incluida por el usuario y el capital mostrado por el sistema
Capital y Tasa |  Prima anual, en base al capital y tasa incluidos por el usuario
Prima anual |  -

**Vida**
"""

# --- Fixture 2: CA001 "Tipo de registro / Transacción" — two consecutive
# simple-shape tables, separated by ordinary bullet prose ---
CA001_TIPO_REGISTRO = """  * Sí la operación en dicha ventana es Consulta:

    * Mostrar en el campo "Transacción" el valor correspondiente al tipo de registro recibido como parámetro y no permitir que sea modificado por el usuario:

#### Tipo de registro

#### Transacción

Propuesta |  Consulta de propuesta
Cotización |  Consulta de cotización
Cotización de modificación |  Consulta de cotización
Cotización de renovación |  Consulta de cotización
Propuesta de modificación |  Consulta de propuesta
Propuesta de renovación |  Consulta de propuesta

    * Mostrar los valores del resto de los campos, de acuerdo a los ingresados como parámetros en la CA099 y no permitir que sean modificados por el usuario.

  * Sí la operación en dicha ventana es Actualizar:

    * Mostrar en el campo "Transacción" el valor correspondiente al tipo de registro recibido como parámetro y no permitir que sea modificado por el usuario:

#### Tipo de registro

#### Transacción

Propuesta |  Propuesta de póliza/certificado
Cotización |  Cotización de póliza certificado
Cotización de modificación |  Cotización de modificación
Cotización de renovación |  Cotización de renovación
Propuesta de modificación |  Propuesta de modificación
Propuesta de renovación |  Propuesta de renovación

    * Mostrar los valores del resto de los campos, de acuerdo a los ingresados como parámetros en la CA099 y no permitir que sean modificados por el usuario.
"""

# --- Fixture 3: CA001 "Tipo de inicio de vigencia / Fecha a mostrar" — paired
# shape, 2 headers + 5 rows each split as its own "####" label + "|value" line ---
CA001_TIPO_INICIO_VIGENCIA = """      * Según el tipo de endoso seleccionado y el valor del campo "Tipo de inicio de vigencia" \\(Type\\_amend.nTypeIssue\\), el sistema muestra o sugiere la "Fecha vigencia":

#### Tipo de inicio de vigencia

#### Fecha a mostrar / sugerir

#### _1 - Primer día mes siguiente_

|  Primer día del mes siguiente según la fecha del computador

#### _2 - Próxima facturación_

|  Fecha de próxima facturación asociada a la póliza - certificado indicada.

#### _3 - Fecha de inspección_

|  Fecha de realizada la inspección \\(según el número de inspección indicado\\).

#### _4 - Fecha del día_

|  Fecha del computador

#### _5 - Libre_

|  El usuario indica la fecha de vigencia del movimiento

      * La información de este campo se actualiza en la tabla de historia de la póliza \\(policy\\_his\\) según el movimiento que se genere.
"""


def test_repairs_ca014_ramos_generales_simple_shape():
    fixed, traces = repair_broken_tables_with_trace(CA014_RAMOS_GENERALES)

    assert len(traces) == 1
    table = traces[0]
    assert table.headers == ["Información cambiada", "Recálculorealizado"]
    assert table.warnings == []
    assert len(table.repaired_markdown.split("\n")) == 6  # header + separator + 4 rows

    assert "| Información cambiada | Recálculorealizado |" in fixed
    assert "| --- | --- |" in fixed
    assert "| Capital | Prima anual, en base a la tasa mostrada por el sistema |" in fixed
    assert "| Prima anual | - |" in fixed
    # Untouched content around the block survives.
    assert "**Ramos generales**" in fixed
    assert "**Vida**" in fixed


def test_repairs_both_ca001_tipo_registro_tables_independently():
    fixed, traces = repair_broken_tables_with_trace(CA001_TIPO_REGISTRO)

    assert len(traces) == 2
    for table in traces:
        assert table.headers == ["Tipo de registro", "Transacción"]
        assert len(table.repaired_markdown.split("\n")) == 8  # header + separator + 6 rows
        assert table.warnings == []

    assert "| Propuesta | Consulta de propuesta |" in fixed
    assert "| Propuesta | Propuesta de póliza/certificado |" in fixed
    # The bullet prose between (and around) the two tables must survive intact.
    assert 'no permitir que sea modificado por el usuario' in fixed
    assert "Sí la operación en dicha ventana es Actualizar" in fixed


def test_repairs_ca001_tipo_inicio_vigencia_paired_shape():
    fixed, traces = repair_broken_tables_with_trace(CA001_TIPO_INICIO_VIGENCIA)

    assert len(traces) == 1
    table = traces[0]
    assert table.headers == ["Tipo de inicio de vigencia", "Fecha a mostrar / sugerir"]
    assert table.warnings == []
    assert len(table.repaired_markdown.split("\n")) == 7  # header + separator + 5 rows

    assert "| 1 - Primer día mes siguiente | Primer día del mes siguiente según la fecha del computador |" in fixed
    assert "| 5 - Libre | El usuario indica la fecha de vigencia del movimiento |" in fixed
    # Surrounding prose survives untouched.
    assert "según el movimiento que se genere" in fixed


# --- Fixture 4: cash_and_banks/opl835.md — split-row shape, 5 columns, rows
# spanning one or three lines. These are search conditions
# (table/field/operator/value), and before this shape was handled the five
# column headers became five useless chunks while the rules were mangled. ---
OPL835_CONDICION_BUSQUEDA = """**Condición de búsqueda para la tabla de órdenes de pago \\(Cheques\\)**

####  Información

####  Campo

####  Operador

####  Valor

####  Observación

Número de solicitud
|  nRequest\\_nu
| > | 0 | Se deben tomar en cuenta todas las solicitudes de cheque
Número de cheque |  sCheque
| >= | ' ' | Se deben tomar en cuenta todos los cheques
Número consecutivo de la solicitud | nConsec | >= | 0 |

**Condición de búsqueda para la tabla de clientes \\(Client\\)**
"""

# --- Fixture 5: accounting/cp001.md — a validation rule and its error code,
# split across two lines. ---
CP001_VALIDACION = """####  Validación

####  Código

Debe incluir el ejercicio
| 736024
Debe estar lleno
| 60829
"""


def test_repairs_the_split_row_shape_keeping_cells_in_their_column():
    fixed, traces = repair_broken_tables_with_trace(OPL835_CONDICION_BUSQUEDA)

    assert len(traces) == 1
    table = traces[0]
    assert table.headers == ["Información", "Campo", "Operador", "Valor", "Observación"]

    # A row split across three lines lands in the right five cells.
    assert (
        "| Número de solicitud | nRequest\\_nu | > | 0 | "
        "Se deben tomar en cuenta todas las solicitudes de cheque |"
    ) in fixed
    # A row split across two lines, and one that was already on a single line.
    assert "| Número de cheque | sCheque | >= | ' ' | Se deben tomar en cuenta todos los cheques |" in fixed
    assert "| Número consecutivo de la solicitud | nConsec | >= | 0 |  |" in fixed
    # Surrounding prose survives.
    assert "tabla de clientes" in fixed


def test_a_five_column_split_table_is_not_read_as_a_paired_two_column_one():
    """Regression: the paired shape matched on the first two headers and turned
    'Operador', 'Valor' and 'Observación' into rows. The paired shape is
    recognised by its alternation, not by its first two lines."""
    _fixed, traces = repair_broken_tables_with_trace(OPL835_CONDICION_BUSQUEDA)

    assert len(traces[0].headers) == 5
    assert "Operador" in traces[0].headers


def test_recovers_a_validation_rule_with_its_error_code():
    """This is the content the naive 'filter short chunks' fix would have
    deleted: an insurance validation rule and the error code it raises."""
    fixed, traces = repair_broken_tables_with_trace(CP001_VALIDACION)

    assert len(traces) == 1
    assert traces[0].headers == ["Validación", "Código"]
    assert "| Debe incluir el ejercicio | 736024 |" in fixed
    assert "| Debe estar lleno | 60829 |" in fixed


def test_does_not_trigger_on_a_real_heading_followed_by_prose():
    text = (
        "#### Some real heading\n\n"
        "This is a regular paragraph of prose, not a table at all.\n\n"
        "#### Another real heading\n\n"
        "More ordinary prose follows here.\n"
    )
    fixed, traces = repair_broken_tables_with_trace(text)

    assert traces == []
    assert fixed == text


def test_pads_missing_cells_and_warns_instead_of_failing_silently():
    text = (
        "#### Campo\n\n"
        "#### Regla\n\n"
        "#### Código de error\n\n"
        "A |  regla A |  E01\n"
        "B |  regla B\n"  # missing the third column
        "C |  regla C |  E03\n"
    )
    fixed, traces = repair_broken_tables_with_trace(text)

    assert len(traces) == 1
    table = traces[0]
    assert len(table.warnings) == 1
    assert "regla B" in table.warnings[0]
    assert "| B | regla B |  |" in fixed


def test_repair_broken_tables_returns_only_text():
    fixed = repair_broken_tables(CA014_RAMOS_GENERALES)
    assert isinstance(fixed, str)
    assert "| Capital | Prima anual, en base a la tasa mostrada por el sistema |" in fixed
