"""The chunker must not be pinned to whichever run booted the process.

``get_functional_spec_chunker`` used to be an ``@lru_cache`` with NO arguments
and the navigation tree lives inside the chunker. That pinned it to whatever
run happened to be resolved at import time, and the resulting bug is one of the
worst available: two replicas of the service serving different navigation trees
depending on when each one started, with nothing to see in either.

So the test is about identity, not behaviour: two different runs must produce
two different chunkers, and the same run must produce the same one — the cache
still has to be a cache.

|| El chunker no puede quedar pegado a la corrida que arrancó el proceso. Antes
era un `@lru_cache` SIN argumentos y el árbol vive adentro del chunker: eso lo
pegaba a la corrida que se hubiera resuelto al importar, y el bug resultante es
de los peores — dos réplicas del servicio sirviendo árboles distintos según
cuándo arrancó cada una, sin nada que ver en ninguna. El test es de identidad y
no de comportamiento: dos corridas distintas tienen que dar dos chunkers
distintos, y la misma corrida el mismo — el caché tiene que seguir siendo caché.
"""

from __future__ import annotations

import pytest

from app.dependencies import build_functional_spec_chunker, resolve_navigation_tree
from app.generation.rag.navigation import NavigationTree


@pytest.fixture(autouse=True)
def fake_trees(monkeypatch):
    """One distinct tree per run, without touching a database.

    || Un árbol distinto por corrida, sin tocar la base.
    """
    build_functional_spec_chunker.cache_clear()

    made: dict[tuple[str, str], NavigationTree] = {}

    def _tree_for(database_url, tenant, env, run_id):
        key = (env, run_id)
        if key not in made:
            # A one-row tree whose single code encodes the run, so two runs are
            # distinguishable by what the tree resolves and not just by identity.
            # || Un árbol de una fila cuyo código codifica la corrida, así dos
            # corridas se distinguen por lo que el árbol resuelve.
            made[key] = NavigationTree(
                [(f"CA{run_id[-3:]}", "", f"Ventana de {run_id}", "1", "", "1")]
            )
        return made[key]

    monkeypatch.setattr("app.dependencies.get_navigation_tree_for_run", _tree_for)
    yield made
    build_functional_spec_chunker.cache_clear()


def test_two_runs_give_two_chunkers_with_two_trees():
    first = build_functional_spec_chunker("PROD", "20260909_214921")
    second = build_functional_spec_chunker("PROD", "20260908_225731")

    assert first is not second
    # El atributo es privado y el test lo lee igual: lo que este test protege es
    # justamente que el árbol de ADENTRO cambie, y desde afuera no hay otra
    # forma de verlo sin trocear un corpus entero por corrida.
    # || The attribute is private and the test reads it anyway: what this test
    # protects is that the tree INSIDE changes, and there is no other way to see
    # that from outside without chunking a whole corpus per run.
    assert first._navigation_tree is not second._navigation_tree
    assert first._navigation_tree.codes() != second._navigation_tree.codes()


def test_the_same_run_gives_the_same_chunker():
    """Sigue siendo un caché: no se rearma el árbol en cada request."""
    first = build_functional_spec_chunker("PROD", "20260909_214921")
    again = build_functional_spec_chunker("PROD", "20260909_214921")

    assert first is again


def test_the_same_run_id_in_two_environments_is_two_runs():
    """El mirror identifica una corrida por (tenant, env, run_id)."""
    prod = build_functional_spec_chunker("PROD", "20260909_214921")
    dev = build_functional_spec_chunker("DEV", "20260909_214921")

    assert prod is not dev


def test_no_run_falls_back_to_the_csv_tree(monkeypatch):
    """Sin corrida se usa el export, donde el estado queda sin resolver.

    El CSV no trae `SSTATREGT`, así que esta rama no puede advertir nada — y eso
    es correcto: no hay corrida activa respecto de la cual la columna esté vieja.
    """
    called: list[object] = []

    def _csv(path):
        # `None` implícito: el loader del CSV devuelve `None` cuando no hay
        # export, y esa es la rama que este test recorre.
        called.append(path)

    monkeypatch.setattr("app.dependencies.get_navigation_tree", _csv)

    assert resolve_navigation_tree(None, None) is None
    assert resolve_navigation_tree("PROD", "") is None
    assert len(called) == 2


def test_resolve_navigation_tree_takes_the_run_as_arguments():
    """No lee la corrida de settings, que es lo que la pegaba al arranque.

    Si volviera a leer `BUSINESS_DB_RUN_ID`, pedirle el árbol de otra corrida
    devolvería el de la configurada y la selección no haría nada.
    """
    tree = resolve_navigation_tree("PROD", "20260909_214921")
    other = resolve_navigation_tree("PROD", "20260908_225731")

    assert tree is not None and other is not None
    assert tree.codes() != other.codes()
