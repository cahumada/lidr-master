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

from app.generation.rag.business_db.roles import TableRole

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
    "edges_not_built",
    "no_dependency_routine",
    "routine_without_tables",
    "code_too_short_to_anchor",
    "dependency_tables_capped",
    "role_unknown",
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
    "edges_not_built",
    "no_dependency_routine",
    "routine_without_tables",
    "code_too_short_to_anchor",
    "dependency_tables_capped",
    "role_unknown",
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
        # The dependency graph declared there is nothing to bring.
        # || El grafo declaró que no hay nada que traer.
        "no_dependency_routine",
        "routine_without_tables",
        "code_too_short_to_anchor",
        # A role the rules could not derive is a declared "I do not know", not
        # a catalog that arrived short. It is visible, and it is not a loss.
        # || Un rol que las reglas no derivaron es un «no sé» declarado.
        "role_unknown",
        # A DECLARED truncation, and that is what separates it from the causes
        # below. The section says, in words, "Tablas que toca: 17, se muestran
        # 12", and the twelve are the highest-coverage ones: nothing is hidden,
        # the amount is exact and the order is known. `table_not_loaded` and
        # `edges_not_built` are mute absences -- you cannot tell what you lost.
        #
        # Measured, the cap bit 26% of the codes that have tables, and a turn
        # anchors about ten of them, so treating it as incompleteness raised
        # the alarm on nearly every answer. An alarm that always fires teaches
        # the operator to ignore it, and then `edges_not_built` goes unread on
        # the day it matters.
        # || Un recorte DECLARADO: el bloque dice «toca 17, se muestran 12» y
        # las 12 son las de mayor cobertura. Medido, mordía el 26% de los
        # códigos y el aviso saltaba en casi toda respuesta.
        "dependency_tables_capped",
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
        # The batch never ran for the active run: there WAS something and it did
        # not arrive. This is the one an administrator has to see -- activating a
        # run whose edges were never built cannot degrade an answer in silence.
        # || El batch nunca corrió para la corrida activa: había algo y no llegó.
        "edges_not_built",
    }
)

# Truncations the block states inline, with the real count. They are NOT
# incompleteness -- see `DECLARED_ABSENT` -- but the closing section still
# names them, so a reader scanning "what could not be brought" does not have to
# re-read every table list to notice a cap.
# || Recortes que el bloque declara inline con su conteo real. NO son
# incompletitud, pero la sección de cierre igual los nombra.
DECLARED_TRUNCATION: frozenset[ResolutionOutcome] = frozenset(
    {"dependency_tables_capped"}
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


class DependencyTable(BaseModel):
    """One table a transaction touches, as Oracle's dependency graph declares it.

    ``via_routines`` is the provenance and never gets trimmed: a table asserted
    without saying why it entered is the same defect as a chunk without its
    document. ``role`` comes from ordered rules over declared signals and is
    ``unknown`` -- with its reason -- whenever none applies.

    || Una tabla que toca la transacción, como la declara el grafo de
    dependencias. ``via_routines`` es la procedencia y no se recorta.
    """

    table_name: str = Field(description="Table name. || Nombre de la tabla.")
    role: TableRole = Field(description="Declared role, or unknown. || Rol declarado, o unknown.")
    role_reason: str = Field(description="Why that role. || Por qué ese rol.")
    description: str | None = Field(
        default=None,
        description="Business prose from the dictionary. || Prosa de negocio del diccionario.",
    )
    via_routines: list[str] = Field(
        default_factory=list,
        description="Routines the dependency came from. || Rutinas de las que salió la dependencia.",
    )
    routine_hits: int = Field(
        default=0,
        description="Routines of this code reaching the table. || Rutinas de este código que llegan.",
    )
    routine_total: int = Field(
        default=0, description="Routines this code has. || Rutinas que tiene el código."
    )
    fan_in: int = Field(
        default=0,
        description="Routines in the whole run depending on it. || Rutinas de toda la corrida que dependen.",
    )


class DictionaryColumn(BaseModel):
    """One column as the run declares it, with its key marks.

    || Una columna como la declara la corrida, con sus marcas de clave.
    """

    name: str = Field(description="Physical column name. || Nombre físico.")
    description: str | None = Field(
        default=None, description="Business prose. || Prosa de negocio."
    )
    data_type: str | None = Field(default=None, description="Oracle type. || Tipo Oracle.")
    nullable: bool | None = Field(
        default=None, description="Whether it admits nulls. || Si admite nulos."
    )
    is_primary_key: bool = Field(default=False, description="In the PK. || Está en la PK.")
    is_foreign_key: bool = Field(default=False, description="In an FK. || Está en una FK.")


class DictionaryForeignKey(BaseModel):
    """One declared foreign key and where it points.

    || Una clave foránea declarada y a dónde apunta.
    """

    name: str
    columns: list[str] = Field(default_factory=list)
    references_table: str | None = None


class DictionaryIndex(BaseModel):
    """One index, its columns in order. || Un índice y sus columnas en orden."""

    name: str
    unique: bool = False
    columns: list[str] = Field(default_factory=list)


class TableDictionaryDetail(BaseModel):
    """Everything the run declares about one table.

    Served on its own and NOT in the prompt: measured, 12 tables in this shape
    are 15,969 tokens against a 16,384-token context ceiling that already
    spends ~7,000 on evidence.

    || Todo lo que la corrida declara de una tabla. Se sirve aparte y NO va al
    prompt: 12 tablas así son 15.969 tokens.
    """

    table_name: str
    description_es: str | None = None
    description_en: str | None = None
    # None = the run did not extract them; [] = the table has none. Not the
    # same fact, and §12 of the domain note says so.
    # || None = no se extrajeron; [] = la tabla no tiene. No es lo mismo.
    columns: list[DictionaryColumn] | None = None
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[DictionaryForeignKey] = Field(default_factory=list)
    indexes: list[DictionaryIndex] = Field(default_factory=list)
    run_id: str
    env: str


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
    # Ordered by coverage descending: how many of this code's routines reach
    # each table. Two declared counts, so the order needs no threshold.
    # || Ordenadas por cobertura descendente. Dos conteos declarados.
    dependency_tables: list[DependencyTable] = Field(default_factory=list)
    dependency_tables_total: int = 0
    dependency_routines: list[str] = Field(default_factory=list)

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
