"""Validate the structure of openspec/ specs and changes.

Enforces exactly the format documented in ``openspec/AGENTS.md``, so the
source of truth stays machine-checkable instead of aspirational. Standard
library only and no network: any agent, any harness, and CI run it identically.

Exit code 0 when there are no errors (warnings alone do not fail), 1 otherwise.

Usage:
    uv run python scripts/validate_specs.py
    uv run python scripts/validate_specs.py --strict   # warnings also fail

|| Valida la estructura de las specs y los changes de openspec/. Impone
exactamente el formato documentado en ``openspec/AGENTS.md``, para que la
fuente de verdad quede verificable por máquina en vez de ser una aspiración.
Solo biblioteca estándar y sin red: cualquier agente, cualquier harness y CI
lo corren igual.

Código de salida 0 cuando no hay errores (las advertencias solas no fallan), 1 si no.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENSPEC_DIR = REPO_ROOT / "openspec"

SPEC_TITLE = re.compile(r"^#\s+\S.*\bSpecification\s*$", re.MULTILINE)
DELTA_TITLE = re.compile(r"^#\s+\S.*\bDelta Specification\s*$", re.MULTILINE)
REQUIREMENT_HEADER = re.compile(r"^###\s+Requirement:\s*(\S.*)$", re.MULTILINE)
SCENARIO_HEADER = re.compile(r"^####\s+Scenario:\s*(\S.*)$", re.MULTILINE)
OPERATION_HEADER = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements\s*$", re.MULTILINE)
ANY_H2 = re.compile(r"^##\s+(\S.*)$", re.MULTILINE)
# A bulleted line that looks like a scenario step but sits outside a
# "#### Scenario:" block — the most common formatting slip.
# || Una línea con bullet que parece un paso de escenario pero está fuera de un
# bloque "#### Scenario:" — el desliz de formato más común.
LOOSE_STEP = re.compile(r"^\s*[-*]\s*\**\s*(WHEN|THEN|AND|GIVEN)\b", re.MULTILINE | re.IGNORECASE)
STEP_BULLET = re.compile(r"^\s*-\s+\*\*(WHEN|THEN|AND|GIVEN)\*\*", re.MULTILINE)


class Report:
    """Collects errors and warnings with their file for a single pass.

    || Junta errores y advertencias con su archivo en una sola pasada.
    """

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, path: Path, message: str) -> None:
        self.errors.append(f"{self._rel(path)}: {message}")

    def warn(self, path: Path, message: str) -> None:
        self.warnings.append(f"{self._rel(path)}: {message}")

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)


def _requirement_blocks(text: str) -> list[tuple[str, str]]:
    """Split a spec body into (requirement name, requirement body) pairs.

    || Divide el cuerpo de una spec en pares (nombre del requirement, cuerpo).
    """
    matches = list(REQUIREMENT_HEADER.finditer(text))
    blocks: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        blocks.append((match.group(1).strip(), text[match.end() : end]))
    return blocks


def _check_requirements(path: Path, text: str, report: Report, *, require_scenarios: bool) -> None:
    """Shared requirement/scenario checks for both specs and delta specs.

    || Chequeos compartidos de requirement/escenario para specs y deltas.
    """
    blocks = _requirement_blocks(text)
    if not blocks:
        report.error(path, "no '### Requirement:' found")
        return

    for name, body in blocks:
        scenarios = list(SCENARIO_HEADER.finditer(body))
        prose = body[: scenarios[0].start()] if scenarios else body
        # Strip step bullets so a body made only of loose steps isn't counted as prose.
        # || Se quitan los bullets de paso para que un cuerpo hecho solo de pasos
        # sueltos no cuente como prosa.
        prose_lines = [
            line
            for line in prose.strip().split("\n")
            if line.strip() and not LOOSE_STEP.match(line)
        ]
        if not prose_lines:
            report.error(
                path,
                f"requirement '{name}' has no descriptive text before its first scenario "
                "(add 1-2 sentences stating the normative behavior)",
            )

        if not scenarios:
            if require_scenarios:
                report.error(path, f"requirement '{name}' has no '#### Scenario:' block")
            continue

        for s_idx, scenario in enumerate(scenarios):
            s_end = scenarios[s_idx + 1].start() if s_idx + 1 < len(scenarios) else len(body)
            s_body = body[scenario.end() : s_end]
            if not STEP_BULLET.search(s_body):
                report.error(
                    path,
                    f"scenario '{scenario.group(1).strip()}' (requirement '{name}') has no "
                    "'- **WHEN**' / '- **THEN**' step bullets",
                )

        # Loose steps that never made it into a scenario block.
        # || Pasos sueltos que nunca entraron en un bloque de escenario.
        if scenarios and LOOSE_STEP.search(prose):
            report.warn(
                path,
                f"requirement '{name}' has WHEN/THEN bullets outside a '#### Scenario:' header",
            )


def validate_spec(path: Path, report: Report) -> None:
    """Validate a current-truth spec: openspec/specs/<capability>/spec.md.

    || Valida una spec de verdad actual: openspec/specs/<capability>/spec.md.
    """
    text = path.read_text(encoding="utf-8")

    if not SPEC_TITLE.search(text):
        report.error(path, "missing '# <capability> Specification' title")
    if "## Purpose" not in text:
        report.error(path, "missing '## Purpose' section")
    if "## Requirements" not in text:
        report.error(path, "missing '## Requirements' section")

    if OPERATION_HEADER.search(text):
        report.error(
            path,
            "current-truth spec carries a delta operation header "
            "(ADDED/MODIFIED/REMOVED/RENAMED) — those belong in a change's spec delta",
        )

    _check_requirements(path, text, report, require_scenarios=True)


def validate_delta_spec(path: Path, report: Report) -> None:
    """Validate a change's spec delta: openspec/changes/<id>/specs/<capability>/spec.md.

    || Valida el delta de spec de un cambio.
    """
    text = path.read_text(encoding="utf-8")

    if not DELTA_TITLE.search(text):
        report.warn(path, "missing '# <capability> Delta Specification' title")

    operations = list(OPERATION_HEADER.finditer(text))
    if not operations:
        report.error(
            path,
            "no delta operation header found — expected '## ADDED Requirements', "
            "'## MODIFIED Requirements', '## REMOVED Requirements' or '## RENAMED Requirements'",
        )
        return

    # Nothing but the title may precede the first operation header.
    # || Nada más que el título puede preceder al primer header de operación.
    head = text[: operations[0].start()]
    head_without_title = DELTA_TITLE.sub("", head).strip()
    if head_without_title:
        report.error(
            path,
            "prose before the first operation header — a delta file must start with the "
            "title followed by an operation header",
        )

    for h2 in ANY_H2.finditer(text):
        label = h2.group(1).strip()
        if not OPERATION_HEADER.match(h2.group(0)):
            report.error(path, f"unexpected '## {label}' in a delta file (only operation headers allowed)")

    # REMOVED sections describe a withdrawal and need no scenarios.
    # || Las secciones REMOVED describen un retiro y no necesitan escenarios.
    removed_only = all(op.group(1) == "REMOVED" for op in operations)
    _check_requirements(path, text, report, require_scenarios=not removed_only)


def validate_change(change_dir: Path, report: Report, *, archived: bool) -> None:
    """Validate one change folder (in flight or archived).

    || Valida una carpeta de cambio (en curso o archivada).
    """
    proposal = change_dir / "proposal.md"
    tasks = change_dir / "tasks.md"

    if not proposal.is_file():
        report.error(change_dir, "missing proposal.md")
    else:
        text = proposal.read_text(encoding="utf-8")
        for required in ("## Why", "## What Changes"):
            if required not in text:
                report.error(proposal, f"missing '{required}' section")

    if not tasks.is_file():
        report.error(change_dir, "missing tasks.md")
    else:
        text = tasks.read_text(encoding="utf-8")
        if not re.search(r"^\s*-\s*\[[ xX]\]", text, re.MULTILINE):
            report.error(tasks, "no task checklist items ('- [ ]' / '- [x]') found")

    delta_files = sorted((change_dir / "specs").rglob("spec.md")) if (change_dir / "specs").is_dir() else []
    for delta in delta_files:
        validate_delta_spec(delta, report)

    # An in-flight change should declare which capabilities it moves. An
    # archived one has already folded its deltas into openspec/specs/.
    # || Un cambio en curso debería declarar qué capabilities mueve. Uno
    # archivado ya integró sus deltas en openspec/specs/.
    if not delta_files and not archived:
        report.warn(change_dir, "no spec deltas under specs/ — an in-flight change should declare them")


EVIDENCE_TAG = re.compile(r"\[(VALIDADO-BD|TÁCITO|TACITO|HIPÓTESIS|HIPOTESIS|VERIFICADO-CORPUS)\]")


def validate_domain_doc(path: Path, report: Report) -> None:
    """Validate a domain reference doc: openspec/domain/<subject>.md.

    Domain docs describe the SOURCE system, not ours, so they are free-form —
    but they must not masquerade as normative specs, and every one must carry
    evidence status, since a hypothesis read as a fact is how the source of
    truth starts lying.

    || Los docs de dominio describen el sistema FUENTE, no el nuestro, así que
    son de forma libre — pero no deben disfrazarse de specs normativas, y todos
    deben llevar estado de evidencia, porque una hipótesis leída como hecho es
    la forma en que la fuente de verdad empieza a mentir.
    """
    text = path.read_text(encoding="utf-8")

    if REQUIREMENT_HEADER.search(text):
        report.error(
            path,
            "domain doc carries '### Requirement:' — domain docs describe the SOURCE system "
            "and are not normative on our code; move it to openspec/specs/ or a change proposal",
        )
    if OPERATION_HEADER.search(text):
        report.error(
            path,
            "domain doc carries a delta operation header — those belong in a change's spec delta",
        )
    if not EVIDENCE_TAG.search(text):
        report.warn(
            path,
            "no evidence status tag found ([VALIDADO-BD] / [TÁCITO] / [HIPÓTESIS] / "
            "[VERIFICADO-CORPUS]) — every claim needs its status",
        )


def _archive_dir_name_is_dated(name: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}-\S+", name))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args()

    report = Report()

    if not OPENSPEC_DIR.is_dir():
        print(f"ERROR: {OPENSPEC_DIR} not found", file=sys.stderr)
        return 1

    for required in (OPENSPEC_DIR / "project.md", OPENSPEC_DIR / "AGENTS.md"):
        if not required.is_file():
            report.error(required, "required file is missing")

    specs_dir = OPENSPEC_DIR / "specs"
    spec_count = 0
    if specs_dir.is_dir():
        for capability_dir in sorted(p for p in specs_dir.iterdir() if p.is_dir()):
            spec_file = capability_dir / "spec.md"
            if not spec_file.is_file():
                report.error(capability_dir, "capability directory has no spec.md")
                continue
            validate_spec(spec_file, report)
            spec_count += 1

    domain_dir = OPENSPEC_DIR / "domain"
    domain_count = 0
    if domain_dir.is_dir():
        for doc in sorted(domain_dir.glob("*.md")):
            validate_domain_doc(doc, report)
            domain_count += 1

    changes_dir = OPENSPEC_DIR / "changes"
    archive_dir = changes_dir / "archive"
    change_count = 0
    if changes_dir.is_dir():
        for entry in sorted(p for p in changes_dir.iterdir() if p.is_dir() and p != archive_dir):
            validate_change(entry, report, archived=False)
            change_count += 1

    archived_count = 0
    if archive_dir.is_dir():
        for entry in sorted(p for p in archive_dir.iterdir() if p.is_dir()):
            if not _archive_dir_name_is_dated(entry.name):
                report.error(entry, "archived change must be named '<YYYY-MM-DD>-<change-id>'")
            validate_change(entry, report, archived=True)
            archived_count += 1

    for warning in report.warnings:
        print(f"WARN  {warning}")
    for error in report.errors:
        print(f"ERROR {error}")

    print()
    print(
        f"{spec_count} spec(s), {domain_count} domain doc(s), {change_count} change(s) in flight, "
        f"{archived_count} archived — {len(report.errors)} error(s), {len(report.warnings)} warning(s)"
    )

    if report.errors:
        return 1
    if args.strict and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
