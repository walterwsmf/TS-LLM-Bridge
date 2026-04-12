"""
pipelines/llm_analysis/pipeline.py

Pipeline de análise LLM.

Grafo:
  prompt_inputs ──────────────────────────────────┐
  params:llm ─────────────────────────────────────┤
  credentials:openai/anthropic ───────────────────┤
                                                   ▼
                              run_llm_analysis → llm_analysis_output
                              run_anomaly_investigation → anomaly_investigation
                              run_model_recommendation → model_recommendation
                                      │
                                      ▼
                              consolidate_llm_logs → cost_report
"""

from kedro.pipeline import Pipeline, node, pipeline

from .nodes import (
    consolidate_llm_logs,
    run_anomaly_investigation,
    run_llm_analysis,
    run_model_recommendation,
)


def _get_credentials(llm_params, openai_creds, anthropic_creds, google_creds):
    """Seleciona credenciais com base no provider configurado."""
    provider = llm_params.get("provider", "openai")
    return {"openai": openai_creds, "anthropic": anthropic_creds, "google": google_creds}.get(
        provider, openai_creds
    )


# Wrappers para injeção correta de credenciais via catálogo
def _run_llm_analysis(prompt_inputs, llm_params, openai_creds, anthropic_creds, google_creds):
    creds = _get_credentials(llm_params, openai_creds, anthropic_creds, google_creds)
    result, log = run_llm_analysis(prompt_inputs, llm_params, creds)
    return result, log

def _run_anomaly_investigation(prompt_inputs, ts_context, llm_params, anomaly_params, openai_creds, anthropic_creds, google_creds):
    creds = _get_credentials(llm_params, openai_creds, anthropic_creds, google_creds)
    results, logs = run_anomaly_investigation(prompt_inputs, ts_context, llm_params, anomaly_params, creds)
    return results, logs

def _run_model_recommendation(prompt_inputs, llm_params, openai_creds, anthropic_creds, google_creds):
    creds = _get_credentials(llm_params, openai_creds, anthropic_creds, google_creds)
    result, log = run_model_recommendation(prompt_inputs, llm_params, creds)
    return result, log


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline([

        # ── Node 1: Análise completa da série ────────────────────────
        node(
            func=_run_llm_analysis,
            inputs=[
                "prompt_inputs",
                "params:llm",
                "credentials:openai",
                "credentials:anthropic",
                "credentials:google",
            ],
            outputs=["llm_analysis_output", "analysis_log"],
            name="run_llm_analysis",
            tags=["llm_analysis"],
        ),

        # ── Node 2: Investigação de anomalias ────────────────────────
        node(
            func=_run_anomaly_investigation,
            inputs=[
                "prompt_inputs",
                "ts_context",
                "params:llm",
                "params:anomaly_analysis",
                "credentials:openai",
                "credentials:anthropic",
                "credentials:google",
            ],
            outputs=["anomaly_investigation", "anomaly_logs"],
            name="run_anomaly_investigation",
            tags=["llm_analysis"],
        ),

        # ── Node 3: Recomendação de modelo ───────────────────────────
        node(
            func=_run_model_recommendation,
            inputs=[
                "prompt_inputs",
                "params:llm",
                "credentials:openai",
                "credentials:anthropic",
                "credentials:google",
            ],
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
