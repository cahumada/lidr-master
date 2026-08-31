# changes/

Trabajo en curso, una carpeta por cambio; los completados se mueven a
`archive/<YYYY-MM-DD>-<change-id>/`.

El ciclo (proponer → implementar → verificar → archivar) está en
[`../../AGENTS.md`](../../AGENTS.md); el formato y las plantillas, en
[`../AGENTS.md`](../AGENTS.md).

|| Work in flight, one folder per change; completed ones move to
`archive/<YYYY-MM-DD>-<change-id>/`. The loop is in `../../AGENTS.md`; the
format and templates are in `../AGENTS.md`.

Validar antes de cerrar || Validate before closing:

```bash
uv run python scripts/validate_specs.py
```
