"""The VisualTIME navigation tree, loaded from an export of the `WINDOWS` table.

`WINDOWS` holds the whole menu tree, self-referencing: `SCODISPL` is a node's
code, `SCODMEN` its parent's, `SDESCRIPT` its description. From it come two
things the code patterns cannot give:

* **Node vs leaf, DECLARED.** `NWINDOWTY` type 8 is "Menu". That replaces the
  has-children heuristic, which got 189 of 194 right and missed 19 -- and which
  was fooled outright by `MA6835`, a row that is its own parent. The domain note
  recorded that self-loop as "a folder indistinguishable by pattern"; it is
  neither a folder nor indistinguishable, it is a data defect.
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

* **Nodo vs. hoja, DECLARADO.** El tipo 8 de `NWINDOWTY` es "Menú". Eso
  reemplaza a la heurística de hijos, que acertaba 189 de 194 y fallaba en 19 —y
  a la que `MA6835` engañaba de lleno, siendo una fila que es su propio padre. La
  nota de dominio registró ese self-loop como "una carpeta indistinguible por
  patrón"; no es carpeta ni indistinguible, es un defecto de datos.
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

# The window types, from `MA0088` in the corpus itself. The name travels
# resolved and not the code: `6` tells nobody anything, `Masivo con encabezado`
# does, and the chunk gets embedded for a model to read.
# || Los tipos de ventana, de `MA0088` en el propio corpus. El nombre viaja
# resuelto y no el código: `6` no le dice nada a nadie, `Masivo con encabezado`
# sí, y el chunk se embebe para que lo lea un modelo.
WINDOW_TYPES = {
    "1": "Puntual con encabezado",
    "2": "Secuencia con encabezado",
    "3": "Masiva sin encabezado",
    "4": "Secuencia sin encabezado",
    "5": "Puntual sin encabezado",
    "6": "Masivo con encabezado",
    "7": "Carpeta especifica",
    "8": "Menu",
    "9": "Carpeta masiva",
    "10": "Tabla general",
    "11": "Ventana emergente",
}

# The type that DECLARES a code to be a menu folder. Authoritative, unlike the
# has-children heuristic it replaces: that one gets 189 of 194 right and misses
# 21, including 16 empty menus it called executable transactions.
# || El tipo que DECLARA que un código es una carpeta de menú. Autoritativo, a
# diferencia de la heurística de hijos que reemplaza: esa acierta 189 de 194 y
# falla en 21, incluidos 16 menús vacíos que llamaba transacciones ejecutables.
MENU_WINDOW_TYPE = "8"


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
    window_type_name: str | None = Field(
        default=None,
        description="How the transaction is operated: puntual, secuencia or masiva, with or "
        "without a header. Absent when the export does not declare it. "
        "|| Cómo se opera la transacción: puntual, secuencia o masiva, con o sin encabezado. "
        "Ausente cuando el export no lo declara.",
    )


UNRESOLVED = NavigationLocation()


class NavigationTree:
    """The menu tree: parents, descriptions, and which codes have children."""

    def __init__(self, rows: list[tuple]) -> None:
        self._parent: dict[str, str | None] = {}
        self._description: dict[str, str] = {}
        self._window_type: dict[str, str] = {}
        for row in rows:
            # Rows are (code, parent, description) or, from a newer export,
            # (code, parent, description, window_type, short_description). The
            # short form still loads: an older CSV keeps working and simply
            # leaves the type unresolved.
            # || Las filas son (código, padre, descripción) o, de un export más
            # nuevo, con tipo de ventana y descripción corta. La forma corta
            # sigue cargando: un CSV viejo funciona y deja el tipo sin resolver.
            code, parent_code, description = row[0], row[1], row[2]
            self._parent[code] = parent_code or None
            self._description[code] = description
            if len(row) > 3 and row[3]:
                self._window_type[code] = str(row[3]).strip()
        # A code that is its OWN parent does not have children in any useful
        # sense. `MA6835` is exactly that -- a self-loop in the export, and one
        # of the two cycles the process map detects -- and counting it as a
        # parent made the has-children heuristic call it a menu folder. The
        # domain note then recorded that artifact as a domain fact.
        # || Un código que es su PROPIO padre no tiene hijos en ningún sentido
        # útil. `MA6835` es exactamente eso —un self-loop en el export, y uno de
        # los dos ciclos que detecta el mapa de procesos— y contarlo como padre
        # hacía que la heurística de hijos lo llamara carpeta de menú. La nota de
        # dominio después registró ese artefacto como un hecho del dominio.
        self._with_children = {
            parent for code, parent in self._parent.items() if parent and parent != code
        }

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
        """Whether anything hangs off ``code``.

        || Si algo cuelga de ``code``.
        """
        return code in self._with_children

    def window_type(self, code: str) -> str | None:
        """The declared window type code, or ``None``.

        || El código del tipo de ventana declarado, o ``None``.
        """
        return self._window_type.get(code)

    def window_type_name(self, code: str) -> str | None:
        """The declared window type, by name.

        || El tipo de ventana declarado, por nombre.
        """
        declared = self._window_type.get(code)
        return WINDOW_TYPES.get(declared) if declared else None

    def is_menu_node(self, code: str) -> bool:
        """Whether ``code`` is a menu folder rather than an executable transaction.

        From the DECLARED window type when the export has it, and only from the
        has-children heuristic when it does not. The heuristic gets 189 of 194
        right and misses 21 -- 16 empty menus it called executable, and 5
        transactions with children it called folders -- and
        ``classify_transaction_type`` reads this, so those 21 propagated.

        || Si ``code`` es una carpeta de menú y no una transacción ejecutable.
        Del tipo de ventana DECLARADO cuando el export lo trae, y de la
        heurística de hijos solo cuando no. La heurística acierta 189 de 194 y
        falla en 21 —16 menús vacíos que llamaba ejecutables y 5 transacciones
        con hijos que llamaba carpetas— y ``classify_transaction_type`` lee esto,
        así que esos 21 se propagaban.
        """
        declared = self._window_type.get(code)
        if declared:
            return declared == MENU_WINDOW_TYPE
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

        is_menu_node = self.is_menu_node(code)
        if chain[0] != ROOT_CODE:
            return NavigationLocation(
                is_menu_node=is_menu_node, window_type_name=self.window_type_name(code)
            )

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
            window_type_name=self.window_type_name(code),
        )


def load_navigation_tree(path: Path) -> NavigationTree | None:
    """Load the tree from a CSV export, or None when it is not available.

    || Carga el árbol desde un export CSV, o None cuando no está disponible.
    """
    if not path.is_file():
        log.warning("navigation_tree_missing", path=str(path))
        return None

    rows: list[tuple] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            code = (record.get("code") or "").strip()
            if not code:
                continue
            # `window_type` is absent from a CSV produced by the older
            # three-column import. Reading it as empty keeps that CSV working
            # and simply leaves the type unresolved, instead of making a stale
            # export a hard failure.
            # || `window_type` no está en un CSV producido por el import viejo de
            # tres columnas. Leerlo como vacío mantiene ese CSV funcionando y
            # deja el tipo sin resolver, en vez de volver un export viejo un
            # error fatal.
            rows.append(
                (
                    code,
                    (record.get("parent_code") or "").strip() or None,
                    (record.get("description") or "").strip(),
                    (record.get("window_type") or "").strip(),
                    (record.get("short_description") or "").strip(),
                )
            )

    tree = NavigationTree(rows)
    log.info(
        "navigation_tree_loaded",
        path=str(path),
        codes=len(tree),
        with_window_type=sum(1 for code in tree.codes() if tree.window_type(code)),
    )
    return tree


@lru_cache
def get_navigation_tree(path: Path) -> NavigationTree | None:
    """Cached loader, so the batch run parses the export once.

    || Loader cacheado, para que la corrida batch parsee el export una sola vez.
    """
    return load_navigation_tree(path)
