"""The VisualTIME navigation tree, loaded from an export of the `WINDOWS` table.

`WINDOWS` holds the whole menu tree, self-referencing: `SCODISPL` is a node's
code, `SCODMEN` its parent's, `SDESCRIPT` its description. From it come two
things the code patterns cannot give:

* **Node vs leaf, structurally.** A code that is some other row's parent is a
  menu folder; a leaf is an executable transaction. The domain note prefers
  this to guessing from the code's shape, and rightly: `MA6835` looks exactly
  like the 941 maintenance leaves and is in fact a folder.
* **The breadcrumb** Módulo → Submódulo → Transacción, at whatever depth.

Kept separate from :mod:`app.generation.rag.taxonomy` on purpose: that module
is a pure string rule, testable with no file present. This one loads data.

The tree is OPTIONAL. Without the export the pipeline runs unchanged and simply
resolves no breadcrumb — the export is a partial snapshot of one installation,
not a precondition for chunking.

|| El árbol de navegación de VisualTIME, cargado de un export de la tabla
`WINDOWS`. Esa tabla tiene el árbol de menú completo, auto-referenciado:
`SCODISPL` es el código de un nodo, `SCODMEN` el de su padre, `SDESCRIPT` su
descripción. De ahí salen dos cosas que los patrones de código no pueden dar:

* **Nodo vs. hoja, estructuralmente.** Un código que es padre de otra fila es
  carpeta de menú; una hoja es transacción ejecutable. La nota de dominio
  prefiere esto a adivinar por la forma del código, y con razón: `MA6835` se ve
  igual que las 941 hojas de mantenimiento y en realidad es una carpeta.
* **El breadcrumb** Módulo → Submódulo → Transacción, con la profundidad que sea.

Se mantiene separado de :mod:`app.generation.rag.taxonomy` a propósito: ese
módulo es una regla de strings pura, testeable sin ningún archivo presente.
Este carga datos.

El árbol es OPCIONAL. Sin el export el pipeline corre igual y simplemente no
resuelve breadcrumb — el export es una foto parcial de una instalación, no una
precondición para trocear.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger()

ROOT_CODE = "MENU"


class NavigationLocation(BaseModel):
    """Where a code sits in the menu tree.

    Every field is optional because the export resolves a path for only part of
    the corpus: an unresolved breadcrumb must read as unresolved, never as a
    guess.

    || Dónde se ubica un código en el árbol de menú. Todos los campos son
    opcionales porque el export resuelve camino solo para parte del corpus: un
    breadcrumb sin resolver tiene que leerse como sin resolver, nunca como una
    suposición.
    """

    module_code: str | None = None
    module_name: str | None = None
    submodule_code: str | None = None
    submodule_name: str | None = None
    navigation_path: str | None = Field(
        default=None,
        description="Full path from the root, for traceability at any depth. "
        "|| Camino completo desde la raíz, para trazabilidad a cualquier profundidad.",
    )
    is_menu_node: bool | None = Field(
        default=None,
        description="True = folder, False = executable leaf, None = absent from the tree. "
        "|| True = carpeta, False = hoja ejecutable, None = ausente del árbol.",
    )


UNRESOLVED = NavigationLocation()


class NavigationTree:
    """The menu tree: parents, descriptions, and which codes have children."""

    def __init__(self, rows: list[tuple[str, str | None, str]]) -> None:
        self._parent: dict[str, str | None] = {}
        self._description: dict[str, str] = {}
        for code, parent_code, description in rows:
            self._parent[code] = parent_code or None
            self._description[code] = description
        self._with_children = {p for p in self._parent.values() if p}

    def __len__(self) -> int:
        return len(self._parent)

    def path(self, code: str) -> list[str]:
        """Path from the root down to ``code``, empty when absent from the tree.

        Guards against cycles: the export contains 2, so a naive walk would
        hang the whole batch run.

        || Camino desde la raíz hasta ``code``, vacío si no está en el árbol.
        Protege contra ciclos: el export tiene 2, así que un recorrido ingenuo
        colgaría toda la corrida batch.
        """
        if code not in self._parent:
            return []
        seen: set[str] = set()
        chain: list[str] = []
        current: str | None = code
        while current and current not in seen:
            seen.add(current)
            chain.append(current)
            current = self._parent.get(current)
        return list(reversed(chain))

    # --- Read-only views, for consumers that walk the whole tree ----------
    # || Vistas de solo lectura, para consumidores que recorren todo el árbol.

    def codes(self) -> list[str]:
        """Every code in the tree, in export order.

        || Cada código del árbol, en el orden del export.
        """
        return list(self._parent)

    def parent_of(self, code: str) -> str | None:
        """The declared parent, or ``None`` when the export carries none.

        717 codes have no parent and 63 point at one the export does not carry,
        so ``None`` is a real answer and not an error.

        || El padre declarado, o ``None`` si el export no trae ninguno. 717
        códigos no tienen padre y 63 apuntan a uno que el export no trae, así
        que ``None`` es una respuesta real y no un error.
        """
        return self._parent.get(code)

    def description_of(self, code: str) -> str | None:
        """The window's description, or ``None`` when the code is unknown.

        || La descripción de la ventana, o ``None`` si el código no se conoce.
        """
        return self._description.get(code)

    def has_children(self, code: str) -> bool:
        """Whether anything hangs off ``code`` -- a menu node rather than a leaf.

        || Si algo cuelga de ``code`` — un nodo de menú y no una hoja.
        """
        return code in self._with_children

    def locate(self, code: str) -> NavigationLocation:
        """Resolve ``code``'s breadcrumb, or leave it unresolved.

        The breadcrumb is only claimed for a path that actually reaches the
        root: 324 codes sit in the tree under a parent that leads nowhere, and
        calling their first ancestor a "module" would invent a taxonomy.

        || Resuelve el breadcrumb de ``code``, o lo deja sin resolver. El
        breadcrumb solo se afirma para un camino que realmente llega a la raíz:
        324 códigos están en el árbol bajo un padre que no lleva a ninguna
        parte, y llamar "módulo" a su primer ancestro inventaría una taxonomía.
        """
        chain = self.path(code)
        if not chain:
            return UNRESOLVED

        is_menu_node = code in self._with_children
        if chain[0] != ROOT_CODE:
            return NavigationLocation(is_menu_node=is_menu_node)

        # chain = [MENU, module, ...intermediates..., code]. Depth runs 1..6 in
        # the real export, so the submodule is the first level between the
        # module and the code — and simply absent when there is none.
        # || chain = [MENU, módulo, ...intermedios..., código]. La profundidad
        # va de 1 a 6 en el export real, así que el submódulo es el primer
        # nivel entre el módulo y el código — y está ausente cuando no hay.
        module = chain[1] if len(chain) >= 2 else None
        submodule = chain[2] if len(chain) >= 4 else None
        return NavigationLocation(
            module_code=module,
            module_name=self._description.get(module) if module else None,
            submodule_code=submodule,
            submodule_name=self._description.get(submodule) if submodule else None,
            navigation_path=" > ".join(chain),
            is_menu_node=is_menu_node,
        )


def load_navigation_tree(path: Path) -> NavigationTree | None:
    """Load the tree from a CSV export, or None when it is not available.

    || Carga el árbol desde un export CSV, o None cuando no está disponible.
    """
    if not path.is_file():
        log.warning("navigation_tree_missing", path=str(path))
        return None

    rows: list[tuple[str, str | None, str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            code = (record.get("code") or "").strip()
            if not code:
                continue
            rows.append(
                (code, (record.get("parent_code") or "").strip() or None, (record.get("description") or "").strip())
            )

    tree = NavigationTree(rows)
    log.info("navigation_tree_loaded", path=str(path), codes=len(tree))
    return tree


@lru_cache
def get_navigation_tree(path: Path) -> NavigationTree | None:
    """Cached loader, so the batch run parses the export once.

    || Loader cacheado, para que la corrida batch parsee el export una sola vez.
    """
    return load_navigation_tree(path)
