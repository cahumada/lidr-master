"""Convert an export of the `WINDOWS` table into the CSV the pipeline reads.

The export arrives as a legacy `.xls` (OLE2/BIFF) with the full table — 23
columns — of which the tree needs five: `SCODISPL` (code), `SCODMEN` (parent),
`SDESCRIPT` (description), `NWINDOWTY` (window type) and `SSHORT_DES`. Values
come CHAR-padded, so they are trimmed.

`xlrd` is NOT a project dependency: it is needed once per export, not at
runtime. Run it transiently instead of adding it to `pyproject.toml`:

    uv run --with xlrd python scripts/import_windows_tree.py "C:\\path\\Windows.xls"

Add `--system-certs` if a corporate TLS proxy blocks the download.

|| Convierte un export de la tabla `WINDOWS` al CSV que lee el pipeline.

El export llega como un `.xls` legacy (OLE2/BIFF) con la tabla completa — 23
columnas — de las cuales el árbol necesita cinco: `SCODISPL` (código),
`SCODMEN` (padre), `SDESCRIPT` (descripción), `NWINDOWTY` (tipo de ventana) y
`SSHORT_DES`. Los valores vienen con relleno CHAR, así que se recortan.

`xlrd` NO es dependencia del proyecto: se necesita una vez por export, no en
runtime. Correrlo de forma transitoria en vez de agregarlo a `pyproject.toml`.
Agregar `--system-certs` si un proxy TLS corporativo bloquea la descarga.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REQUIRED_COLUMNS = ("SCODISPL", "SCODMEN", "SDESCRIPT")

# `NWINDOWTY` is the window type, and type 8 IS "Menu" -- an authoritative
# answer to the node-vs-leaf question that was being derived from "does anything
# hang off this code". The heuristic gets 189 of 194 right and misses 21,
# including 16 empty menus it called executable transactions.
# `SSHORT_DES` is a short description, useful where the long one is empty.
# || `NWINDOWTY` es el tipo de ventana, y el tipo 8 ES "Menu" — una respuesta
# autoritativa a la pregunta nodo-vs-hoja que se venia derivando de "cuelga algo
# de este codigo". La heuristica acierta 189 de 194 y falla en 21, incluidos 16
# menus vacios que llamaba transacciones ejecutables.
OPTIONAL_COLUMNS = ("NWINDOWTY", "SSHORT_DES")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xls", help="Path to the WINDOWS export (.xls)")
    parser.add_argument(
        "--out", default="data/windows_tree.csv", help="Output CSV (default: data/windows_tree.csv)"
    )
    args = parser.parse_args()

    try:
        import xlrd
    except ModuleNotFoundError:
        print(
            "xlrd is not installed. It is deliberately not a project dependency — run:\n"
            '  uv run --with xlrd python scripts/import_windows_tree.py "<file.xls>"',
            file=sys.stderr,
        )
        return 1

    book = xlrd.open_workbook(args.xls)
    sheet = book.sheet_by_index(0)
    header = [str(sheet.cell_value(0, col)).strip() for col in range(sheet.ncols)]

    missing = [name for name in REQUIRED_COLUMNS if name not in header]
    if missing:
        print(f"export is missing required column(s): {', '.join(missing)}", file=sys.stderr)
        print(f"columns found: {', '.join(header)}", file=sys.stderr)
        return 1
    available = [name for name in OPTIONAL_COLUMNS if name in header]
    index = {name: header.index(name) for name in (*REQUIRED_COLUMNS, *available)}
    if len(available) < len(OPTIONAL_COLUMNS):
        print(
            "note: this export lacks "
            f"{', '.join(n for n in OPTIONAL_COLUMNS if n not in available)}; "
            "those columns are written empty and the window type stays unresolved.",
            file=sys.stderr,
        )

    def value(row: int, name: str) -> str:
        cell = sheet.cell_value(row, index[name])
        # Numeric-looking cells come back as floats; keep them as integers so a
        # code never turns into "205.0".
        # || Las celdas que parecen numéricas vuelven como float; se guardan como
        # enteros para que un código nunca se vuelva "205.0".
        if isinstance(cell, float):
            return str(int(cell))
        return str(cell).strip()

    rows: list[tuple[str, str, str, str, str]] = []
    for row in range(1, sheet.nrows):
        code = value(row, "SCODISPL")
        if not code:
            continue
        rows.append(
            (
                code,
                value(row, "SCODMEN"),
                value(row, "SDESCRIPT"),
                value(row, "NWINDOWTY") if "NWINDOWTY" in index else "",
                value(row, "SSHORT_DES") if "SSHORT_DES" in index else "",
            )
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["code", "parent_code", "description", "window_type", "short_description"]
        )
        writer.writerows(rows)

    parents = {row[1] for row in rows if row[1]}
    codes = {row[0] for row in rows}
    import collections

    types = collections.Counter(row[3] for row in rows if row[3])
    print(f"{out_path}: {len(rows)} rows")
    print(f"  nodes with children: {len(parents & codes)}")
    print(f"  leaves             : {len(codes - parents)}")
    print(f"  dangling parents   : {len(parents - codes)}")
    print(f"  with window type   : {sum(types.values())}")
    if types:
        print(f"  declared as menu (type 8): {types.get('8', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
