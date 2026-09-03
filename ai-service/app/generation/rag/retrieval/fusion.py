"""Reciprocal Rank Fusion: combine ranked lists by position, not by score.

Cosine distance lives in [0, 2]; ``ts_rank_cd`` has no ceiling and depends on the
length of the text and the density of the terms. They are not comparable, and
normalizing them needs minimums and maximums that change with every query -- a
result's score would end up depending on who else came back with it.

RRF sidesteps that entirely: each result contributes ``1 / (k + rank)`` for every
ranking it appears in. Nothing to calibrate, and a result that does well in two
branches beats one that does very well in a single branch, which is exactly what
a fusion is for.

``k = 60`` is the constant from Cormack et al., and the same one the course uses.
A larger k flattens the curve and forces a result to rank well across several
branches; a smaller one lets a single first place dominate.

**No per-branch weights.** The course deliberately has none, and it is right: the
point of RRF is that positional consensus decides, and a weight puts back the
manual calibration RRF avoids -- with the twist that a badly chosen weight is
invisible, because the resulting order still looks reasonable.

|| Reciprocal Rank Fusion: combina rankings por posición, no por puntaje.

La distancia coseno vive en [0, 2]; ``ts_rank_cd`` no tiene tope y depende del
largo del texto y de la densidad de los términos. No son comparables, y
normalizarlos necesita mínimos y máximos que cambian con cada consulta — el
puntaje de un resultado terminaría dependiendo de con quiénes volvió.

RRF esquiva todo eso: cada resultado aporta ``1 / (k + posición)`` por cada
ranking donde aparece. Nada que calibrar, y un resultado que va bien en dos ramas
le gana a uno que va muy bien en una sola, que es para lo que sirve una fusión.

``k = 60`` es el constante de Cormack et al., el mismo que usa el curso. Un k
grande achata la curva y obliga a rankear bien en varias ramas; uno chico deja
que un solo primer puesto domine.

**Sin pesos por rama.** El curso deliberadamente no los tiene, y tiene razón: el
punto de RRF es que el consenso posicional decida, y un peso reintroduce la
calibración manual que RRF evita — con el agravante de que un peso mal elegido es
invisible, porque el orden resultante sigue pareciendo razonable.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

# From Cormack et al., and the course's `DEFAULT_RRF_K`.
# || De Cormack et al., y el `DEFAULT_RRF_K` del curso.
DEFAULT_RRF_K = 60

T = TypeVar("T")


@dataclass
class Fused:
    """One result of the fusion, with where it came from.

    || Un resultado de la fusión, con de dónde vino.
    """

    key: str
    score: float
    # Which branches found it, in the order they were fused. A result found by
    # two branches is a different kind of answer than one found by one, and the
    # caller (and the person reading the answer) should be able to tell.
    # || Qué ramas lo encontraron, en el orden en que se fusionaron. Un
    # resultado que encontraron dos ramas es otra clase de respuesta que uno que
    # encontró una sola, y quien llama —y quien lee la respuesta— debería poder
    # distinguirlos.
    branches: list[str] = field(default_factory=list)
    # Its position in each branch, 1-based, for auditing an order that looks odd.
    # || Su posición en cada rama, desde 1, para auditar un orden que parezca raro.
    ranks: dict[str, int] = field(default_factory=dict)


def reciprocal_rank_fusion(
    rankings: dict[str, Sequence[T]],
    *,
    key: Callable[[T], str],
    k: int = DEFAULT_RRF_K,
    limit: int | None = None,
) -> list[Fused]:
    """Fuse named rankings into one, by position.

    Ties break by key so the order is deterministic: two results with the same
    score would otherwise come back in whatever order the dict happened to have,
    and a metric that moves between runs is useless.

    || Fusiona rankings con nombre en uno solo, por posición. Los empates se
    rompen por clave para que el orden sea determinístico: si no, dos resultados
    con el mismo puntaje volverían en el orden que el dict tuviera, y una métrica
    que se mueve entre corridas no sirve.
    """
    scores: dict[str, float] = {}
    branches: dict[str, list[str]] = {}
    ranks: dict[str, dict[str, int]] = {}

    for branch, results in rankings.items():
        for position, result in enumerate(results, start=1):
            identity = key(result)
            scores[identity] = scores.get(identity, 0.0) + 1.0 / (k + position)
            branches.setdefault(identity, []).append(branch)
            # First position wins if a branch somehow returns a duplicate.
            # || Si una rama devuelve un duplicado, gana la primera posición.
            ranks.setdefault(identity, {}).setdefault(branch, position)

    fused = [
        Fused(key=identity, score=score, branches=branches[identity], ranks=ranks[identity])
        for identity, score in scores.items()
    ]
    fused.sort(key=lambda item: (-item.score, item.key))
    return fused[:limit] if limit is not None else fused


def cap_per_group(
    fused: Sequence[Fused], group_of: Callable[[str], str], *, cap: int | None, limit: int
) -> list[Fused]:
    """Keep at most ``cap`` results per group, filling the freed places downward.

    Measured on 8 real questions: the dominant document takes 4.5 of 10 hits on
    average. On a general question that is a defect -- 7 of 10 from ``CA001k``,
    which is the key request and not the main transaction. On a specific one it
    is the right answer: the 10 chunks of ``AGL009`` for a question about
    ``AGL009``'s logic.

    Forcing diversity would fix the first case by breaking the second, so this
    is a parameter and ``cap=None`` (the default) does not trim.

    || Deja a lo sumo ``cap`` resultados por grupo, y llena los lugares liberados
    con los que siguen. Medido sobre 8 preguntas reales: el documento dominante
    se lleva 4,5 de 10 hits en promedio. En una pregunta general eso es un
    defecto; en una específica es la respuesta correcta. Forzar diversidad
    arreglaría el primer caso rompiendo el segundo, así que esto es un parámetro
    y ``cap=None`` (el default) no recorta.
    """
    if cap is None:
        return list(fused[:limit])

    seen: dict[str, int] = {}
    kept: list[Fused] = []
    for item in fused:
        group = group_of(item.key)
        if seen.get(group, 0) >= cap:
            continue
        seen[group] = seen.get(group, 0) + 1
        kept.append(item)
        if len(kept) == limit:
            break
    return kept
