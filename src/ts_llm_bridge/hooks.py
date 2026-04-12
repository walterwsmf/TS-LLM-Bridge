"""
hooks.py — Hooks do ciclo de vida do Kedro.

Hooks são o mecanismo do Kedro para cross-cutting concerns:
logging, monitoramento, notificações, etc.

Hooks disponíveis:
  NodeTimingHook  → registra duração de cada node
  LLMCostHook     → acumula custo total da sessão (lê dos logs)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from kedro.framework.hooks import hook_impl
from kedro.pipeline.node import Node

logger = logging.getLogger(__name__)


class NodeTimingHook:
    """
    Registra o tempo de execução de cada node.

    Para ativar: adicionar à lista HOOKS em settings.py
        HOOKS = (NodeTimingHook(),)
    """

    def __init__(self):
        self._start_times: dict[str, float] = {}

    @hook_impl
    def before_node_run(
        self,
        node: Node,
        catalog,
        inputs: dict[str, Any],
        is_async: bool,
        session_id: str,
    ) -> None:
        self._start_times[node.name] = time.monotonic()
        logger.info(f"▶ Iniciando node: {node.name}")

    @hook_impl
    def after_node_run(
        self,
        node: Node,
        catalog,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        is_async: bool,
        session_id: str,
    ) -> None:
        start = self._start_times.pop(node.name, None)
        if start:
            elapsed = round((time.monotonic() - start) * 1000)
            logger.info(f"✓ Node concluído: {node.name} ({elapsed}ms)")

    @hook_impl
    def on_node_error(
        self,
        error: Exception,
        node: Node,
        catalog,
        inputs: dict[str, Any],
        is_async: bool,
        session_id: str,
    ) -> None:
        logger.error(f"✗ Erro no node {node.name}: {error}")


class LLMCostHook:
    """
    Exibe um resumo de custo LLM ao final de cada pipeline run.

    Para ativar: adicionar à lista HOOKS em settings.py
        HOOKS = (NodeTimingHook(), LLMCostHook())
    """

    @hook_impl
    def after_pipeline_run(
        self,
        run_params: dict[str, Any],
        pipeline,
        catalog,
    ) -> None:
        try:
            cost_report = catalog.load("cost_report")
            logger.info(
                "━" * 50 + "\n"
                f"  💰 Custo da sessão: ${cost_report.get('custo_total_usd', 0):.6f}\n"
                f"  🔤 Tokens:          {cost_report.get('tokens_total', 0):}\n"
                f"  📞 Chamadas LLM:    {cost_report.get('total_chamadas', 0)}\n"
                f"  ⏱  Latência média:  {cost_report.get('latencia_media_ms', 0):.0f}ms\n"
                + "━" * 50
            )
        except Exception:
            pass  # cost_report pode não existir se pipeline parou antes
