"""Validity predicate, derived from the columns a table DECLARES.

Never a hardcoded list of tables. `business_tables.columns` already says
which columns exist; deriving the mechanism from that is reading the data
instead of remembering a measurement of one run.

The assumption that `SSTATREGT = '1'` means Active is MEASURED, not implied
by the comparison. §4.1 measured that every `TABLE<n>` uses `SSTATREGT` and
nothing else. That `1` is Active on every one of them is still [HIPÓTESIS]:
the catalog is per-table (§4.2), `CONFIGECONGROUP` declares its own
`1 ACTIVO - 0 DESACTIVO`, and a `TABLE<n>` with another catalog would drop
valid rows while completeness accounting saw a successful filter. So we
only apply the status filter when the column description remits to table 26;
any other catalog, or none, is `no_validity_mechanism`.

|| Predicado de vigencia, derivado de las columnas que la tabla DECLARA.
Nunca una lista hardcodeada. El supuesto de que `SSTATREGT = '1'` es Activo
se mide: solo se filtra por estado cuando la descripción de la columna
remite a la tabla 26.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Literal

from app.generation.rag.business_db.models import (
    CatalogRow,
    ColumnDictionary,
    ValidityMechanism,
)

STATUS_COLUMN = "SSTATREGT"
EFFECTIVE_COLUMN = "DEFFECDATE"
NULL_COLUMN = "DNULLDATE"
ACTIVE_STATUS = "1"

# The assumption, written next to the comparison it would otherwise hide.
# Evidence: domain §4.1 / §4.2. Status: [HIPÓTESIS] until a TABLE<n> catalog
# is confirmed per table.
# || El supuesto, escrito al lado de la comparación que si no lo escondería.
STATUS_ACTIVE_EQUALS_ONE = (
    "SSTATREGT='1' is treated as Active ONLY when the column description "
    "remits to TABLE26 (domain §4.1 measured every TABLE<n> uses SSTATREGT; "
    "that 1 means Active on every catalog is [HIPÓTESIS], §4.2 / §13.7). "
    "|| SSTATREGT='1' se trata como Activo SOLO cuando la descripción de la "
    "columna remite a TABLE26."
)

_TABLE26_RE = re.compile(r"tabla\s*26\b|table\s*26\b|table26\b", re.IGNORECASE)
_CATALOG_TABLE_RE = re.compile(
    r"(?:tabla|table)\s*(?:TABLE)?(\d+)|TABLE(\d+)",
    re.IGNORECASE,
)
_INLINE_FOREIGN_RE = re.compile(r"1\s*ACTIVO\b.*\b0\s*DESACTIV|\b0\s*DESACTIV", re.IGNORECASE)

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d/%m/%Y %H:%M:%S",
    "%Y%m%d",
)


def declared_mechanism(
    columns: list[ColumnDictionary] | None,
) -> ValidityMechanism | Literal["unknown"]:
    """Which validity mechanism the declared columns support.

    ``None`` is "columns were not extracted" — unknown, not none. ``[]`` is
    "the table has no columns", which is none.

    || Qué mecanismo de vigencia soportan las columnas declaradas. ``None``
    es «no se extrajeron columnas» — unknown, no none.
    """
    if columns is None:
        return "unknown"
    names = {column.name.upper() for column in columns}
    has_status = STATUS_COLUMN in names
    has_effective = EFFECTIVE_COLUMN in names
    has_null = NULL_COLUMN in names
    has_period = has_effective and has_null
    half_period = (has_effective and not has_null) or (has_null and not has_effective)
    if half_period:
        # Presence is not the mechanism: POLICY / CHEQUES / BANK_MOV. §4.1.
        # || La presencia no es el mecanismo. §4.1.
        return "none"
    if has_status and has_period:
        return "both"
    if has_status:
        return "status"
    if has_period:
        return "period"
    return "none"


def status_catalog_is_table26(description: str | None) -> bool:
    """Whether the column description remits to TABLE26.

    || Si la descripción de la columna remite a TABLE26.
    """
    if not description:
        return False
    return bool(_TABLE26_RE.search(description))


def status_catalog_is_foreign(description: str | None) -> bool:
    """Whether the column declares a catalog that is NOT TABLE26.

    A generic "Estado del registro." does not: §4.1 measured every TABLE<n>
    uses SSTATREGT the same way, and that description is the common one.
    A remit to table 1520 / 535 / 1541, or an inline 1-ACTIVO-0-DESACTIVO,
    is a different catalog — those must not be filtered by `1`.

    || Si la columna declara un catálogo que NO es TABLE26. Un «Estado del
    registro.» genérico no cuenta: §4.1 midió que todas las TABLE<n> usan
    SSTATREGT igual. Una remisión a otra tabla sí.
    """
    if not description:
        return False
    if _TABLE26_RE.search(description):
        return False
    if _INLINE_FOREIGN_RE.search(description):
        return True
    for match in _CATALOG_TABLE_RE.finditer(description):
        number = match.group(1) or match.group(2)
        if number and number != "26":
            return True
    return False


def apply_status_filter(description: str | None) -> bool:
    """Whether `SSTATREGT='1'` is safe to apply.

    || Si es seguro aplicar `SSTATREGT='1'`.
    """
    return not status_catalog_is_foreign(description)


def column_description(
    columns: list[ColumnDictionary] | None, name: str
) -> str | None:
    """The declared description of ``name``, if any. || La descripción declarada de ``name``."""
    if not columns:
        return None
    target = name.upper()
    for column in columns:
        if column.name.upper() == target:
            return column.description
    return None


def parse_row_date(value: str | None) -> date | None:
    """A calendar date, or ``None`` when the text cannot be read.

    The predicate is evaluated in Python because the dates live in jsonb as
    undeclared text; a SQL cast would turn one odd value into a failed query.

    || Una fecha de calendario, o ``None`` cuando el texto no se puede leer.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"NULL", "NONE"}:
        return None
    text = text.replace("Z", "")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.date()
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC).date()
        except ValueError:
            continue
    return None


def normalize_status(value: str | None) -> tuple[str | None, bool]:
    """Strip padding and treat `4` as `3`, saying so.

    || Recorta padding y trata el `4` como `3`, diciéndolo.
    """
    if value is None:
        return None, False
    code = str(value).strip()
    if not code:
        return None, False
    if code == "4":
        return "3", True
    return code, False


def _cell(row: CatalogRow, name: str) -> str | None:
    for key, value in row.values.items():
        if key.upper() == name.upper():
            return None if value is None else str(value)
    return None


def row_status_active(row: CatalogRow) -> tuple[bool, bool]:
    """Whether the row is status-active, and whether `4` was normalized.

    || Si la fila está activa por estado, y si se normalizó un `4`.
    """
    raw = _cell(row, STATUS_COLUMN)
    code, from_four = normalize_status(raw)
    return code == ACTIVE_STATUS, from_four


def row_period_active(
    row: CatalogRow, as_of: date
) -> tuple[bool | None, bool]:
    """Whether the row is in force at ``as_of``.

    ``None`` means a date did not parse — the row is out, counted separately.
    A missing `DEFFECDATE` after we already required the pair is the same:
    unparsed, out.

    || Si la fila está vigente en ``as_of``. ``None`` es una fecha que no
    parseó: la fila queda afuera y se cuenta aparte.
    """
    raw_effective = _cell(row, EFFECTIVE_COLUMN)
    raw_null = _cell(row, NULL_COLUMN)
    if raw_effective is None or not str(raw_effective).strip():
        return None, True
    effective = parse_row_date(raw_effective)
    if effective is None:
        return None, True
    if effective > as_of:
        return False, False
    if raw_null is None or not str(raw_null).strip():
        return True, False
    null_date = parse_row_date(raw_null)
    if null_date is None:
        return None, True
    return null_date > as_of, False


class ValidityCounts:
    """What the filter counted. || Lo que contó el filtro."""

    def __init__(self) -> None:
        self.kept: list[CatalogRow] = []
        self.status_normalized_from_4 = 0
        self.date_unparsed = 0
        self.validity_discrepancy = 0


def apply_validity(
    rows: list[CatalogRow],
    *,
    mechanism: ValidityMechanism | Literal["unknown"],
    as_of: date,
    apply_status: bool,
) -> ValidityCounts:
    """Keep the rows in force, counting every discard.

    ``apply_status`` is the measured gate: False when the SSTATREGT catalog
    is not TABLE26, even if the mechanism includes status.

    When both mechanisms apply, a row that one accepts and the other rejects
    is a discrepancy. Both predicates still run; neither wins.

    || Conserva las filas vigentes, contando cada descarte. Con ambos
    mecanismos, una fila que uno acepta y el otro rechaza es una discrepancia.
    Los dos predicados corren; ninguno gana.
    """
    counts = ValidityCounts()
    if mechanism in ("none", "unknown"):
        counts.kept = list(rows)
        return counts

    use_status = apply_status and mechanism in ("status", "both")
    use_period = mechanism in ("period", "both")

    for row in rows:
        status_ok: bool | None = None
        period_ok: bool | None = None
        if use_status:
            status_ok, from_four = row_status_active(row)
            if from_four:
                counts.status_normalized_from_4 += 1
        if use_period:
            period_ok, unparsed = row_period_active(row, as_of)
            if unparsed:
                counts.date_unparsed += 1
                continue
        if use_status and use_period:
            if status_ok is not None and period_ok is not None and status_ok != period_ok:
                counts.validity_discrepancy += 1
            if status_ok and period_ok:
                counts.kept.append(row)
            continue
        if use_status and status_ok:
            counts.kept.append(row)
            continue
        if use_period and period_ok:
            counts.kept.append(row)
    return counts
