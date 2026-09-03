"""Privilege table and guarded dispatch.

|| Tabla de privilegios y guarded_dispatch.
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.graph.privilege import (
    PrivilegeViolation,
    assert_allowed,
    guarded_dispatch,
)


def test_evidence_retriever_has_one_tool():
    assert_allowed("evidence_retriever", "search_corpus")


def test_synthesizer_has_no_tools():
    with pytest.raises(PrivilegeViolation):
        assert_allowed("answer_synthesizer", "search_corpus")


def test_denied_tool_is_audited_without_execution():
    async def _should_not_run(_args):
        raise AssertionError("tool executed")

    result, contribution = asyncio.run(
        guarded_dispatch(
            "answer_synthesizer",
            "search_corpus",
            {"query": "x"},
            step=2,
            executor=_should_not_run,
        )
    )
    assert result["ok"] is False
    assert contribution["outcome"] == "denied"
