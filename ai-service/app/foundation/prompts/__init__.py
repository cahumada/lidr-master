"""Versioned Jinja2 prompts, loaded from this package.

One loader and one ``Environment``. ``StrictUndefined`` so a missing variable
fails instead of rendering as empty — a silent hole in a prompt is the same
class of defect as a chunk that produces zero text: it has to scream.

No autoescape: these templates produce model text, not HTML.

|| Prompts Jinja2 versionados, cargados desde este paquete. Un loader y un
``Environment``. ``StrictUndefined`` para que una variable que falta falle en
vez de renderizarse vacía — un hueco silencioso en un prompt es la misma
clase de defecto que un chunk que produce cero texto: tiene que gritar. Sin
autoescape: estas plantillas producen texto para el modelo, no HTML.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_DIR = Path(__file__).resolve().parent

_ENV = Environment(
    loader=FileSystemLoader(_DIR),
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
)


def render_prompt(name: str, version: str, role: str, **values: object) -> str:
    """Render ``<name>/<version>/<role>.j2``.

    || Renderiza ``<name>/<version>/<role>.j2``.
    """
    return _ENV.get_template(f"{name}/{version}/{role}.j2").render(**values)
