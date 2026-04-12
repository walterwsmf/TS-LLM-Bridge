"""
pipeline_registry.py — Registro central de pipelines.

Kedro usa este arquivo para descobrir e compor pipelines.
Cada chave do dict retornado por register_pipelines() pode ser
executada com: kedro run --pipeline=<chave>

Pipelines disponíveis:
  __default__        → pipeline completo (feature + llm + eval)
  feature_extraction → só extração de features (sem LLM)
  llm_analysis       → análise LLM (requer feature_extraction antes)
  evaluation         → avaliação e relatório (requer llm_analysis)
  demo               → pipeline completo com série sintética
"""

from kedro.pipeline import Pipeline

from ts_llm_bridge.pipelines.feature_extraction import pipeline as fe
from ts_llm_bridge.pipelines.llm_analysis import pipeline as llm
from ts_llm_bridge.pipelines.evaluation import pipeline as ev


def register_pipelines() -> dict[str, Pipeline]:
    """
    Registra todos os pipelines do projeto.

    Returns:
        Dict mapeando nome → Pipeline.
    """
    feature_pipeline = fe.create_pipeline()
    llm_pipeline = llm.create_pipeline()
    eval_pipeline = ev.create_pipeline()

    # Pipeline completo: todas as etapas em sequência
    full_pipeline = feature_pipeline + llm_pipeline + eval_pipeline

    return {
        # Pipeline padrão (kedro run sem --pipeline)
        "__default__": full_pipeline,

        # Sub-pipelines individuais
        "feature_extraction": feature_pipeline,
        "llm_analysis": llm_pipeline,
        "evaluation": eval_pipeline,

        # Pipeline de demo (igual ao full, tags explicitadas)
        "demo": full_pipeline.only_nodes_with_tags("demo", "feature_extraction")
                + llm_pipeline
                + eval_pipeline,

        # Só features, sem chamar LLM (útil para inspecionar o contexto)
        "features_only": feature_pipeline,

        # Full sem geração sintética (para dados reais)
        "real_data": (
            feature_pipeline.filter(
                node_names=[
                    "validate_and_clean_series",
                    "extract_ts_context",
                    "build_prompt_inputs",
                ]
            )
            + llm_pipeline
            + eval_pipeline
        ),
    }
