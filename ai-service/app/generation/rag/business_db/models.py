"""Types that travel: dictionary, rows, one resolution, and the accounting.

The outcome vocabulary is CLOSED and has no catch-all. A new cause has to be
added here; that is how `complete = false` never arrives without a name.

|| Tipos que viajan: diccionario, filas, una resolución y la contabilidad.
El vocabulario de resultados es CERRADO y no tiene cajón de sastre. Una causa
nueva se agrega acá; así `complete = false` nunca llega sin nombre.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

ResolutionOutcome = Literal[
    "resolved",
    "not_in_run",
    "no_maintained_table",
    "ng_identi_ignored_by_type",
    "table_not_in_dictionary",
    "table_not_loaded",
    "columns_unknown",
    "no_validity_mechanism",
    "validity_discrepancy",
    "rows_capped",
    "date_unparsed",
    "dropped_by_budget",
]

RESOLUTION_OUTCOMES: tuple[ResolutionOutcome, ...] = (
    "resolved",
    "not_in_run",
    "no_maintained_table",
    "ng_identi_ignored_by_type",
    "table_not_in_dictionary",
    "table_not_loaded",
    "columns_unknown",
    "no_validity_mechanism",
    "validity_discrepancy",
    "rows_capped",
    "date_unparsed",
    "dropped_by_budget",
)

# The base declared there was nothing to bring: not incompleteness.
# || La base declaró que no había nada que traer: no es incompletitud.
DECLARED_ABSENT: frozenset[ResolutionOutcome] = frozenset(
    {
        "resolved",
        "not_in_run",
        "no_maintained_table",
        "ng_identi_ignored_by_type",
        "no_validity_mechanism",
        "validity_discrepancy",
    }
)

# There was something and it did not arrive.
# || Había algo y no llegó.
INCOMPLETE_OUTCOMES: frozenset[ResolutionOutcome] = frozenset(
    {
        "table_not_in_dictionary",
        "table_not_loaded",
        "rows_capped",
        "columns_unknown",
        "date_unparsed",
        "dropped_by_budget",
    }
)

ValidityMechanism = Literal["status", "period", "both", "none"]

AbsentReason = Literal["no_active_run", "disabled"]


class ColumnDictionary(BaseModel):
    """One column as `business_tables` describes it. || Una columna como la describe `business_tables`."""

    name: str
    description: str | None = None


class TableDictionary(BaseModel):
    """The business description of one table. || La descripción de negocio de una tabla."""

    table_name: str
    description_es: str | None = None
    description_en: str | None = None
    # None = columns were not extracted; [] = the table has none. §12.
    # || None = no se extrajeron columnas; [] = la tabla no tiene. §12.
    columns: list[ColumnDictionary] | None = None


class CatalogRow(BaseModel):
    """One `business_data` row, already pulled out of jsonb.

    || Una fila de `business_data`, ya sacada del jsonb.
    """

    values: dict[str, str | None] = Field(default_factory=dict)


class CodeResolution(BaseModel):
    """What the mirror said about one anchored transaction code.

    ``outcome`` is the primary result; ``causes`` is the closed set of every
    cause that applied (including the primary). A resolution can be `resolved`
    and still carry `rows_capped`.

    || Lo que dijo el mirror de un código anclado. ``outcome`` es el resultado
    principal; ``causes`` es el conjunto cerrado de cada causa que aplicó.
    """

    code: str
    outcome: ResolutionOutcome
    causes: list[ResolutionOutcome] = Field(default_factory=list)
    table_name: str | None = None
    window_type: str | None = None
    window_type_name: str | None = None
    window_status: str | None = None
    window_description: str | None = None
    ng_identi: int | None = None
    dictionary: TableDictionary | None = None
    rows: list[CatalogRow] = Field(default_factory=list)
    rows_valid: int = 0
    rows_shown: int = 0
    rows_fetched: int = 0
    mechanism: ValidityMechanism | None = None
    status_normalized_from_4: int = 0
    date_unparsed_count: int = 0
    validity_discrepancy_count: int = 0
    dropped_column_descriptions: bool = False
    dropped_table_description: bool = False

    def model_post_init(self, context: object, /) -> None:
        if not self.causes:
            self.causes = [self.outcome]


class BusinessDbContext(BaseModel):
    """The run, the resolutions, and whether everything that existed arrived.

    || La corrida, las resoluciones, y si llegó todo lo que existía.
    """

    run_id: str | None = None
    env: str | None = None
    as_of: date | None = None
    resolutions: list[CodeResolution] = Field(default_factory=list)
    complete: bool = True
    absent_reason: AbsentReason | None = None
    absent_detail: str | None = None
    dropped_codes: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    block_emitted: bool = False

    @classmethod
    def absent(
        cls,
        reason: AbsentReason,
        *,
        env: str | None = None,
        detail: str | None = None,
    ) -> BusinessDbContext:
        """No block: there is no run, or the eval turned the block off.

        || Sin bloque: no hay corrida, o el eval apagó el bloque.
        """
        return cls(
            env=env,
            complete=True,
            absent_reason=reason,
            absent_detail=detail,
            block_emitted=False,
        )

    def with_completeness(self) -> BusinessDbContext:
        """Recompute ``complete`` from the closed vocabulary.

        || Recalcula ``complete`` desde el vocabulario cerrado.
        """
        incomplete = any(
            cause in INCOMPLETE_OUTCOMES
            for resolution in self.resolutions
            for cause in resolution.causes
        ) or bool(self.dropped_codes)
        return self.model_copy(update={"complete": not incomplete})


def parse_as_of(value: str | datetime | date | None) -> date | None:
    """A calendar date, or ``None`` when nothing was configured.

    || Una fecha de calendario, o ``None`` cuando no se configuró nada.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = value.strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])
