"""
pipelines/llm_analysis/pipeline.py

Pipeline de análise LLM.

Grafo:
  prompt_inputs ──────────┐
  params:llm ─────────────┤
                           ▼
          run_llm_analysis → llm_analysis_output
          run_anomaly_investigation → anomaly_investigation
          run_model_recommendation → model_recommendation
                  │
                  ▼
          consolidate_llm_logs → cost_report

API keys injetadas via CredentialsToEnvHook (settings.py) antes do run.
"""

from kedro.pipeline import Pipeline, node, pipeline

from .nodes import (
    consolidate_llm_logs,
    run_anomaly_investigation,
    run_llm_analysis,
    run_model_recommendation,
)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline([

        # ── Node 1: Análise completa da série ────────────────────────
        node(
            func=run_llm_analysis,
            inputs=["prompt_inputs", "params:llm"],
            outputs=["llm_analysis_output", "analysis_log"],
            name="run_llm_analysis",
            tags=["llm_analysis"],
        ),

        # ── Node 2: Investigação de anomalias ────────────────────────
        node(
            func=run_anomaly_investigation,
            inputs=[
                "prompt_inputs",
                "ts_context",
                "params:llm",
                "params:anomaly_analysis",
            ],
            outputs=["anomaly_investigation", "anomaly_logs"],
            name="run_anomaly_investigation",
            tags=["llm_analysis"],
        ),

        # ── Node 3: Recomendação de modelo ───────────────────────────
        node(
            func=run_model_recommendation,
            inputs=["prompt_inputs", "params:llm"],
            outputs=["model_recommendation", "rec_log"],
            name="run_model_recommendation",
            tags=["llm_analysis"],
        ),

        # ── Node 4: Consolida logs de custo ──────────────────────────
        node(
            func=consolidate_llm_logs,
            inputs=["analysis_log", "anomaly_logs", "rec_log"],
            outputs="cost_report",
            name="consolidate_llm_logs",
            tags=["llm_analysis", "reporting"],
        ),
    ])
