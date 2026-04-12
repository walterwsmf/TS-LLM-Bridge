"""
pipelines/feature_extraction/pipeline.py

Pipeline de extração de features TS.

Grafo de dependências:
  params:synthetic_data
        │
        ▼
  generate_synthetic_series → synthetic_series
        │
        ▼ (ou raw_time_series para dados reais)
  validate_and_clean_series → clean_series
        │
        ▼
  extract_ts_context → ts_context
        │
        ▼
  build_prompt_inputs → prompt_inputs
"""

from kedro.pipeline import Pipeline, node, pipeline

from .nodes import (
    build_prompt_inputs,
    extract_ts_context,
    generate_synthetic_series,
    validate_and_clean_series,
)


def _build_prompt_inputs_wrapper(ts_context, llm_params, model_rec_params):
    """Combina múltiplos params antes de chamar build_prompt_inputs."""
    combined = {"llm": llm_params, "model_recommendation": model_rec_params}
    return build_prompt_inputs(ts_context, combined)


def create_pipeline(**kwargs) -> Pipeline:
    return pipeline([

        node(
            func=generate_synthetic_series,
            inputs="params:synthetic_data",
            outputs="synthetic_series",
            name="generate_synthetic_series",
            tags=["demo", "feature_extraction"],
        ),

        # Para dados reais: troque 'synthetic_series' → 'raw_time_series'
        node(
            func=validate_and_clean_series,
            inputs=["synthetic_series", "params:feature_extraction"],
            outputs="clean_series",
            name="validate_and_clean_series",
            tags=["feature_extraction"],
        ),

        node(
            func=extract_ts_context,
            inputs=["clean_series", "params:feature_extraction"],
            outputs="ts_context",
            name="extract_ts_context",
            tags=["feature_extraction"],
        ),

        node(
            func=_build_prompt_inputs_wrapper,
            inputs=["ts_context", "params:llm", "params:model_recommendation"],
            outputs="prompt_inputs",
            name="build_prompt_inputs",
            tags=["feature_extraction"],
        ),
    ])
