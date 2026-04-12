"""
pipelines/evaluation/pipeline.py

Pipeline de avaliação e relatório final.

Grafo:
  llm_analysis_output ─┐
  ts_context ──────────┼─► evaluate_llm_output → evaluation_result
  params:evaluation ───┘
          │
          ▼
  [todos os outputs] ──► generate_final_report → final_report
"""

from kedro.pipeline import Pipeline, node, pipeline

from .nodes import evaluate_llm_output, generate_final_report


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline([

        # ── Node 1: Avalia qualidade do output LLM ───────────────────
        node(
            func=evaluate_llm_output,
            inputs=[
                "llm_analysis_output",
                "ts_context",
                "params:evaluation",
            ],
            outputs="evaluation_result",
            name="evaluate_llm_output",
            tags=["evaluation"],
        ),

        # ── Node 2: Gera relatório final consolidado ─────────────────
        node(
            func=generate_final_report,
            inputs=[
                "ts_context",
                "llm_analysis_output",
                "anomaly_investigation",
                "model_recommendation",
                "evaluation_result",
                "cost_report",
            ],
            outputs="final_report",
            name="generate_final_report",
            tags=["evaluation", "reporting"],
        ),
    ])
