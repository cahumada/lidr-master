"""Minimum privilege over tools for answer-orchestration agents.

|| Privilegio mínimo sobre herramientas para los agentes de orquestación.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any

import structlog

from app.config import get_settings

log = structlog.get_logger()

SEARCH_CORPUS_TOOL = "search_corpus"

AGENT_PRIVILEGES: dict[str, frozenset[str]] = {
    "orchestrator": frozenset(),
    "query_planner": frozenset(),
    "evidence_retriever": frozenset({SEARCH_CORPUS_TOOL}),
    "answer_synthesizer": frozenset(),
    "citation_validator": frozenset(),
    "answer_review_gate": frozenset(),
}


class PrivilegeViolation(RuntimeError):
    """An agent attempted a tool outside its declared allowlist.

    || Un agente intentó una herramienta fuera de su allowlist declarada.
    """

    def __init__(self, agent: str, tool: str, allowed: frozenset[str]) -> None:
        self.agent = agent
        self.tool = tool
        self.allowed = allowed
        super().__init__(
            f"agent {agent!r} attempted tool {tool!r}; its declared privilege is "
            f"{sorted(allowed) or 'NO tools'}"
        )


def allowed_tools(agent: str) -> frozenset[str]:
    """The tools ``agent`` may call.

    || Las herramientas que ``agent`` puede llamar.
    """
    return AGENT_PRIVILEGES.get(agent, frozenset())


def assert_allowed(agent: str, tool: str) -> None:
    """Raise ``PrivilegeViolation`` unless ``tool`` is allowed.

    || Lanza ``PrivilegeViolation`` si ``tool`` no está permitida.
    """
    allowed = allowed_tools(agent)
    if tool not in allowed:
        raise PrivilegeViolation(agent, tool, allowed)


def _digest(args: dict[str, Any]) -> str:
    canonical = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _preview(args: dict[str, Any]) -> str:
    limit = get_settings().ANSWER_ORCHESTRATOR_AUDIT_ARGS_PREVIEW_CHARS
    return json.dumps(args, sort_keys=True, default=str)[:limit]


def record_model_action(
    agent: str,
    action: str,
    *,
    step: int,
    summary: str,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    """Audit a model-only action and return its contribution row.

    || Audita una acción solo-modelo y devuelve su fila de contribución.
    """
    log.info(
        "agent_action",
        step=step,
        agent=agent,
        tool=None,
        action=action,
        outcome="ok",
        allowed=sorted(allowed_tools(agent)),
        result_summary=summary[:200],
        duration_ms=duration_ms,
    )
    return {
        "step": step,
        "agent": agent,
        "action": action,
        "tool": None,
        "outcome": "ok",
        "summary": summary[:200],
        "args_digest": None,
        "duration_ms": duration_ms,
    }


async def guarded_dispatch(
    agent: str,
    tool: str,
    args: dict[str, Any],
    *,
    step: int,
    executor: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Check privilege, execute, audit. Returns ``(result_envelope, contribution)``.

    || Chequea privilegio, ejecuta, audita. Devuelve ``(result_envelope, contribution)``.
    """
    settings = get_settings()
    started = perf_counter()
    digest = _digest(args)
    allowed = allowed_tools(agent)

    if tool not in allowed:
        violation = PrivilegeViolation(agent, tool, allowed)
        log.error(
            "agent_privilege_denied",
            step=step,
            agent=agent,
            tool=tool,
            allowed=sorted(allowed),
            args_digest=digest,
            args_preview=_preview(args),
        )
        contribution = {
            "step": step,
            "agent": agent,
            "action": f"tool:{tool}",
            "tool": tool,
            "outcome": "denied",
            "summary": str(violation),
            "args_digest": digest,
            "duration_ms": int((perf_counter() - started) * 1000),
        }
        if settings.ANSWER_ORCHESTRATOR_PRIVILEGE_STRICT:
            raise violation
        return (
            {"ok": False, "error": "privilege_denied", "summary": str(violation)},
            contribution,
        )

    try:
        result = await executor(args)
        outcome = "ok" if result.get("ok", True) else "error"
    except Exception as exc:  # noqa: BLE001 — a bad tool call must not kill the graph.
        result = {
            "ok": False,
            "error": type(exc).__name__,
            "summary": str(exc)[:200],
        }
        outcome = "error"

    duration_ms = int((perf_counter() - started) * 1000)
    summary = str(result.get("summary", ""))[:200]
    log.info(
        "agent_action",
        step=step,
        agent=agent,
        tool=tool,
        action=f"tool:{tool}",
        outcome=outcome,
        allowed=sorted(allowed),
        args_digest=digest,
        args_preview=_preview(args),
        result_summary=summary,
        duration_ms=duration_ms,
    )
    return result, {
        "step": step,
        "agent": agent,
        "action": f"tool:{tool}",
        "tool": tool,
        "outcome": outcome,
        "summary": summary,
        "args_digest": digest,
        "duration_ms": duration_ms,
    }
