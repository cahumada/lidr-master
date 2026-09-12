"""The two hops from a transaction code to the tables it touches.

Hop 1 -- code to routines -- is the only one that uses names: the
``document_id`` appears inside the Oracle object's name (domain §5.3). Hop 2 --
routines to tables -- is Oracle's own compiled dependency graph, where names are
irrelevant: that is why ``CA014`` reaches ``COVER`` without the two resembling
each other.

Everything here is pure. The mirror reads live in the batch script; these
functions take lists and return edges, so the disambiguation and the role rules
are testable without a database.

|| Los dos saltos del código de transacción a sus tablas. El salto 1 es el
único que usa nombres; el salto 2 es el grafo que Oracle compiló. Todo acá es
puro: las lecturas del mirror viven en el batch.
"""

from __future__ import annotations

import collections
from collections.abc import Iterable, Mapping, Sequence

from pydantic import BaseModel, Field

from app.generation.rag.business_db.roles import (
    ROUTINE_PREFIXES,
    TableRole,
    classify_role,
)

# Codes shorter than this do not anchor. Domain §5.3: the length-4 pairs are
# pure false positives -- `LOGO -> INSCOPYCATALOGO`, `MENU -> REAWINDOWSMENUPKG`
# -- and there are only 7 of them across 2 documents.
# || Los códigos más cortos que esto no anclan. Los de largo 4 son falsos
# positivos puros.
MIN_ANCHOR_LENGTH = 4 + 1

# Today the only path that produces these edges. The field exists because the
# domain note describes other paths (§5.2, §5.3 identity) that would arrive as
# indicios and must stay distinguishable from this one.
# || Hoy el único camino que produce estas aristas.
DEPENDENCY_GRAPH = "dependency_graph"


class TableEdge(BaseModel):
    """One table a transaction touches, with everything that justifies it.

    || Una tabla que toca una transacción, con todo lo que la justifica.
    """

    transaction_code: str = Field(description="Transaction code. || Código de transacción.")
    table_name: str = Field(description="Table the routines depend on. || Tabla de la que dependen las rutinas.")
    role: TableRole = Field(description="Declared role, or unknown. || Rol declarado, o unknown.")
    role_reason: str = Field(description="Why that role. || Por qué ese rol.")
    via_routines: list[str] = Field(
        default_factory=list,
        description="Routines the dependency came from. || Rutinas de las que salió la dependencia.",
    )
    fan_in: int = Field(
        default=0,
        description="Routines in the whole run depending on this table. || Rutinas de toda la corrida que dependen de esta tabla.",
    )
    routine_hits: int = Field(
        default=0,
        description="Routines of THIS code reaching the table. || Rutinas DE ESTE código que llegan a la tabla.",
    )
    routine_total: int = Field(
        default=0, description="Routines this code has. || Rutinas que tiene este código."
    )
    origin: str = Field(
        default=DEPENDENCY_GRAPH, description="Which path produced it. || Qué camino la produjo."
    )

    @property
    def coverage(self) -> float:
        """Share of the transaction's routines that reach this table.

        Two declared counts divided, not a fitted score: it needs no threshold
        to mean something, which is why it is the ordering signal.

        || Dos conteos declarados divididos, no un puntaje calibrado.
        """
        if not self.routine_total:
            return 0.0
        return self.routine_hits / self.routine_total


def _is_well_placed(name: str, code: str, start: int) -> bool:
    """Whether the match sits where the naming convention puts a code.

    Routine names are ``<verb prefix><code><suffix>``, so a code is well placed
    when what precedes it is nothing, a non-alphanumeric, or a known verb
    prefix. Without this, longest-match picks spurious codes that the verb
    prefix glues together: ``INSCA001PKG`` contains ``SCA001`` because the
    ``S`` of ``INS`` runs into ``CA001``, and being longer it would beat the
    real code. Measured, that alone stole every routine of ``CA001``.

    || Si el match cae donde la convención pone un código. Sin esto, el munch
    máximo elige códigos espurios que el prefijo verbal pega: ``INSCA001PKG``
    contiene ``SCA001`` porque la ``S`` de ``INS`` se junta con ``CA001``.
    """
    if start == 0:
        return True
    before = name[:start]
    if not before[-1].isalnum():
        return True
    return any(before == prefix for prefix, _ in ROUTINE_PREFIXES)


def routines_for_codes(
    codes: Iterable[str], routine_names: Iterable[str]
) -> dict[str, list[str]]:
    """Hop 1, with the collision resolved by longest match.

    184 codes of length >= 5 are substrings of another code (``CA013`` inside
    ``CA013A``, ``AG001`` inside both ``AG001_K`` and ``MAG001``), which without
    disambiguation hands the short code 55 routines that are not its own.
    Each routine goes to the LONGEST code that matches it, and only to that one:
    ``INSPOSTCA013A`` names ``CA013A`` unambiguously, and ``CA013`` being a
    prefix of it is an accident of the naming convention.

A match is only taken where the naming convention puts a code (see
    :func:`_is_well_placed`), and there is no fallback: a routine whose name does
    not follow the convention anchors nowhere.

    A code left with nothing is a fact -- it has no routine of its own -- not a
    reason to inherit the long code's tables.

    || Salto 1, con la colisión resuelta por munch máximo. Cada rutina va al
    código más largo que la matchea, y solo a ese.
    """
    anchorable = sorted(
        {code.strip().upper() for code in codes if len(code.strip()) >= MIN_ANCHOR_LENGTH}
    )
    assigned: dict[str, list[str]] = {code: [] for code in anchorable}
    for name in routine_names:
        upper = name.upper()
        # Only well-placed matches, with no fallback: a routine whose name does
        # not follow the convention anchors NOWHERE rather than being handed to
        # whichever code happens to appear inside it. Measured, the fallback
        # gave `SCA001` all 30 routines of `CA001` -- a code with no functional
        # spec at all -- which is the "indicio presented as hecho" that domain
        # §5.4 forbids. Not anchoring is a fact; anchoring wrong is a lie.
        # || Solo matches bien ubicados, sin fallback: una rutina cuyo nombre no
        # sigue la convención no ancla en ningún lado. No anclar es un hecho;
        # anclar mal es una mentira.
        candidates = [
            code
            for code in anchorable
            if (start := upper.find(code)) >= 0 and _is_well_placed(upper, code, start)
        ]
        if candidates:
            assigned[max(candidates, key=len)].append(name)
    return {code: sorted(names) for code, names in assigned.items()}


def fan_in_by_table(edges: Iterable[tuple[str, str]]) -> dict[str, int]:
    """How many distinct routines in the whole run depend on each table.

    Stored on every edge so the role decision can be revisited without
    rebuilding. It is NOT used to demote a table: measured against the annotated
    set it runs backwards -- the central entities are the ones with the highest
    fan-in. See ``roles.py``.

    || Cuántas rutinas distintas de toda la corrida dependen de cada tabla. NO
    se usa para degradar una tabla: medido, corre al revés.
    """
    counter: collections.Counter[str] = collections.Counter()
    seen: set[tuple[str, str]] = set()
    for routine, table in edges:
        pair = (routine, table)
        if pair in seen:
            continue
        seen.add(pair)
        counter[table] += 1
    return dict(counter)


def build_edges(
    *,
    code_routines: Mapping[str, Sequence[str]],
    routine_tables: Mapping[str, Sequence[str]],
    descriptions: Mapping[str, str | None],
    fan_in: Mapping[str, int],
) -> dict[str, list[TableEdge]]:
    """Hop 2 plus the role, ordered by coverage descending then name.

    ``descriptions`` is the business prose from ``business_tables``; a table
    missing from it still produces an edge -- the dependency is declared either
    way -- with the role rules falling back to the name.

    || Salto 2 más el rol, ordenado por cobertura descendente y después por
    nombre. Una tabla sin ficha igual produce arista: la dependencia está
    declarada de todos modos.
    """
    built: dict[str, list[TableEdge]] = {}
    for code, routines in code_routines.items():
        if not routines:
            built[code] = []
            continue
        via: dict[str, list[str]] = collections.defaultdict(list)
        for routine in routines:
            for table in routine_tables.get(routine, ()):
                via[table].append(routine)
        total = len(routines)
        edges: list[TableEdge] = []
        for table, names in via.items():
            unique = sorted(set(names))
            role, reason = classify_role(
                table_name=table,
                description=descriptions.get(table),
                via_routines=unique,
            )
            edges.append(
                TableEdge(
                    transaction_code=code,
                    table_name=table,
                    role=role,
                    role_reason=reason,
                    via_routines=unique,
                    fan_in=fan_in.get(table, 0),
                    routine_hits=len(unique),
                    routine_total=total,
                )
            )
        edges.sort(key=lambda edge: (-edge.routine_hits, edge.table_name))
        built[code] = edges
    return built
