"""
pipelines/feature_extraction/nodes.py

Nodes da pipeline de extração de features.

Filosofia Kedro: cada node é uma função pura sem side-effects.
Entrada e saída são dados do catálogo — nunca I/O direto.

Nodes:
  generate_synthetic_series  → cria série para demos
  validate_and_clean_series  → valida e limpa a série bruta
  extract_ts_context         → extrai ContextoTS como dict
  build_prompt_inputs        → prepara inputs para o prompt builder
"""

from __future__ import annotations

import json
import logging
import warnings
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Dataclasses tipadas
# ----------------------------------------------------------------

@dataclass
class Anomalia:
    data: str
    valor: float
    desvios_padrao: float
    tipo: str  # spike_positivo | spike_negativo | outlier_sazonal


@dataclass
class ContextoTS:
    """Contexto estruturado de uma série temporal para o LLM."""
    nome: str
    n_pontos: int
    frequencia: str
    periodo_inicio: str
    periodo_fim: str
    media: float
    desvio_padrao: float
    minimo: float
    maximo: float
    tendencia: str
    inclinacao_por_periodo: float
    forca_sazonalidade: float
    periodo_sazonal: Optional[int]
    estacionaria: bool
    n_anomalias: int
    anomalias: list[dict]   # dicts serializáveis para o catálogo
    coef_variacao: float
    ultima_media_3p: float
    tokens_estimados: int


# ----------------------------------------------------------------
# Node 1 — Geração de série sintética
# ----------------------------------------------------------------

def generate_synthetic_series(parameters: dict) -> pd.DataFrame:
    """
    Gera uma série temporal sintética para demos e testes.

    Kedro input:  params:synthetic_data
    Kedro output: synthetic_series

    Args:
        parameters: subdict 'synthetic_data' do parameters.yml

    Returns:
        DataFrame com DatetimeIndex e coluna 'valor'.
    """
    p = parameters
    n = p["n_periodos"]
    np.random.seed(p["seed"])
    t = np.arange(n)

    valores = (
        p["nivel_base"]
        + p["tendencia"] * t
        + p["amplitude_sazonal"] * np.sin(2 * np.pi * t / p["periodo_sazonal"])
        + np.random.normal(0, p["ruido_std"], n)
    )

    # Injeta anomalia
    idx_anomalia = int(n * p["anomalia_posicao"])
    valores[idx_anomalia] += p["anomalia_magnitude"]

    idx = pd.date_range(p["data_inicio"], periods=n, freq=p["frequencia"])
    df = pd.DataFrame({"valor": valores}, index=idx)
    df.index.name = "data"

    logger.info(f"Série sintética gerada: {n} pontos, anomalia em {idx[idx_anomalia].date()}")
    return df


# ----------------------------------------------------------------
# Node 2 — Validação e limpeza da série bruta
# ----------------------------------------------------------------

def validate_and_clean_series(
    raw_df: pd.DataFrame,
    parameters: dict,
) -> pd.DataFrame:
    """
    Valida e limpa a série temporal bruta.

    Kedro input:  raw_time_series (ou synthetic_series), params:feature_extraction
    Kedro output: clean_series

    Checagens:
    - DatetimeIndex presente
    - Coluna de valor existe
    - Sem duplicatas no índice
    - Sem séries muito curtas (<12 pontos)

    Args:
        raw_df: DataFrame bruto do catálogo.
        parameters: subdict 'feature_extraction' do parameters.yml.

    Returns:
        DataFrame limpo com DatetimeIndex e coluna de valor.

    Raises:
        ValueError: se a série não passar nas validações críticas.
    """
    coluna = parameters["coluna_valor"]

    # Garante DatetimeIndex
    if not isinstance(raw_df.index, pd.DatetimeIndex):
        try:
            raw_df.index = pd.to_datetime(raw_df.index)
            logger.info("Índice convertido para DatetimeIndex.")
        except Exception as e:
            raise ValueError(f"Não foi possível converter o índice para data: {e}") from e

    # Verifica coluna
    if coluna not in raw_df.columns:
        available = raw_df.columns.tolist()
        raise ValueError(
            f"Coluna '{coluna}' não encontrada. "
            f"Disponíveis: {available}. "
            f"Ajuste 'feature_extraction.coluna_valor' no parameters.yml."
        )

    # Extrai série e ordena
    series = raw_df[coluna].sort_index()

    # Remove duplicatas de índice (mantém último)
    n_dup = series.index.duplicated().sum()
    if n_dup > 0:
        logger.warning(f"{n_dup} duplicatas de índice removidas (mantido último valor).")
        series = series[~series.index.duplicated(keep="last")]

    # Remove NaN
    n_nan = series.isna().sum()
    if n_nan > 0:
        logger.warning(f"{n_nan} valores nulos removidos.")
        series = series.dropna()

    # Validação mínima de tamanho
    if len(series) < 12:
        raise ValueError(
            f"Série muito curta: {len(series)} pontos. "
            "Mínimo recomendado: 12 pontos para análise LLM."
        )

    logger.info(
        f"Série validada: {len(series)} pontos, "
        f"{series.index[0].date()} → {series.index[-1].date()}"
    )

    return series.to_frame(name=coluna)


# ----------------------------------------------------------------
# Helpers internos para extração de features
# ----------------------------------------------------------------

def _detectar_frequencia(index: pd.DatetimeIndex) -> tuple[str, Optional[int]]:
    if len(index) < 2:
        return "desconhecida", None
    delta = (index[1] - index[0]).days
    if delta <= 1:    return "diária", 7
    elif delta <= 8:  return "semanal", 52
    elif delta <= 32: return "mensal", 12
    elif delta <= 95: return "trimestral", 4
    else:             return "anual", None


def _calcular_stl(series: pd.Series, period: int) -> tuple[float, pd.Series]:
    try:
        from statsmodels.tsa.seasonal import STL
    except ImportError:
        return 0.0, series - series.mean()

    if len(series) < 2 * period + 1:
        return 0.0, series - series.mean()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stl = STL(series, period=period, robust=True).fit()

    var_r = stl.resid.var()
    var_sr = (stl.seasonal + stl.resid).var()
    forca = 0.0 if var_sr == 0 else max(0.0, 1 - var_r / var_sr)
    return round(forca, 3), stl.resid


def _detectar_anomalias(
    series: pd.Series,
    residuos: pd.Series,
    limiar: float,
    max_anomalias: int,
) -> list[dict]:
    std = residuos.std()
    if std == 0:
        return []

    z = (residuos - residuos.mean()) / std
    anomalos = z[np.abs(z) > limiar]
    resultado = []

    for data, z_val in anomalos.items():
        idx = series.index.get_loc(data)
        tipo = "spike_positivo" if z_val > 0 else "spike_negativo"

        if hasattr(data, "month") and len(series) > 24:
            mesmo = series[series.index.month == data.month]
            if len(mesmo) > 1 and abs(series.iloc[idx] - mesmo.mean()) > 2 * series.std():
                tipo = "outlier_sazonal"

        resultado.append({
            "data": str(data)[:10],
            "valor": round(float(series.iloc[idx]), 2),
            "desvios_padrao": round(float(z_val), 2),
            "tipo": tipo,
        })

    return sorted(resultado, key=lambda a: abs(a["desvios_padrao"]), reverse=True)[:max_anomalias]


# ----------------------------------------------------------------
# Node 3 — Extração de contexto TS
# ----------------------------------------------------------------

def extract_ts_context(
    clean_df: pd.DataFrame,
    parameters: dict,
) -> dict:
    """
    Extrai contexto interpretável da série para alimentar os prompts.

    Kedro input:  clean_series, params:feature_extraction
    Kedro output: ts_context

    O resultado é um dict JSON-serializável compatível com o
    catálogo kedro_datasets.json.JSONDataset.

    Args:
        clean_df: DataFrame limpo com DatetimeIndex.
        parameters: subdict 'feature_extraction'.

    Returns:
        Dict com todas as features da série (ContextoTS serializado).
    """
    p = parameters
    coluna = p["coluna_valor"]
    series = clean_df[coluna].sort_index()
    n = len(series)

    freq_str, periodo_sazonal = _detectar_frequencia(series.index)

    # Tendência por regressão linear
    x = np.arange(n)
    slope, _ = np.polyfit(x, series.values, 1)
    inclinacao = round(float(slope), 4)
    norm = abs(slope) / (abs(series.mean()) + 1e-9)
    if norm < 0.01:    tendencia = "estavel"
    elif slope > 0:    tendencia = "crescente"
    else:              tendencia = "decrescente"

    # STL e anomalias
    if periodo_sazonal and n > 2 * periodo_sazonal:
        forca_saz, residuos = _calcular_stl(series, periodo_sazonal)
    else:
        forca_saz, residuos = 0.0, series - series.mean()

    anomalias = _detectar_anomalias(
        series, residuos,
        p["limiar_anomalia"],
        p["max_anomalias"],
    )

    # Teste ADF
    estacionaria = False
    if n >= 20:
        try:
            from statsmodels.tsa.stattools import adfuller
            estacionaria = bool(adfuller(series.values, autolag="AIC")[1] < 0.05)
        except Exception:
            pass

    ctx = {
        "nome": p["serie_nome"],
        "n_pontos": n,
        "frequencia": freq_str,
        "periodo_inicio": str(series.index[0])[:10],
        "periodo_fim": str(series.index[-1])[:10],
        "media": round(float(series.mean()), 2),
        "desvio_padrao": round(float(series.std()), 2),
        "minimo": round(float(series.min()), 2),
        "maximo": round(float(series.max()), 2),
        "tendencia": tendencia,
        "inclinacao_por_periodo": inclinacao,
        "forca_sazonalidade": forca_saz,
        "periodo_sazonal": periodo_sazonal,
        "estacionaria": estacionaria,
        "n_anomalias": len(anomalias),
        "anomalias": anomalias,
        "coef_variacao": round(float(series.std() / series.mean()), 3) if series.mean() != 0 else 0.0,
        "ultima_media_3p": round(float(series.iloc[-3:].mean()), 2),
        "tokens_estimados": int(len(str({"dummy": "x" * 200})) * n * 0.05),
    }
    # Estimativa real de tokens
    ctx["tokens_estimados"] = int(len(json.dumps(ctx)) * 1.3)

    logger.info(
        f"Contexto extraído: tendência={tendencia}, "
        f"sazonalidade={forca_saz:.2f}, "
        f"anomalias={len(anomalias)}, "
        f"~{ctx['tokens_estimados']} tokens"
    )
    return ctx


# ----------------------------------------------------------------
# Node 4 — Construção dos inputs de prompt
# ----------------------------------------------------------------

def build_prompt_inputs(
    ts_context: dict,
    parameters: dict,
) -> dict:
    """
    Monta o dict de inputs para cada template de prompt.

    Kedro input:  ts_context, params:llm, params:model_recommendation
    Kedro output: prompt_inputs

    Args:
        ts_context: contexto TS extraído pelo node anterior.
        parameters: dict com llm, model_recommendation fundidos.

    Returns:
        Dict com inputs para cada prompt template.
    """
    llm_p = parameters["llm"]
    mr_p = parameters["model_recommendation"]

    ctx_json = json.dumps(ts_context, ensure_ascii=False, indent=2)
    anomalias_json = json.dumps(
        [{"data": a["data"], "tipo": a["tipo"]} for a in ts_context.get("anomalias", [])],
        ensure_ascii=False,
    )

    inputs = {
        "analise_completa": {
            "contexto": ctx_json,
            "pergunta": llm_p["pergunta_padrao"],
        },
        "selecao_modelo": {
            "nome_serie": ts_context["nome"],
            "contexto": ctx_json,
            "horizonte": mr_p["horizonte_forecast"],
            "prioridade": mr_p["prioridade"],
        },
        "codigo_preprocessing": {
            "contexto": ctx_json,
            "modelo_alvo": "Prophet",
            "anomalias": anomalias_json,
        },
        "anomalias": [
            {
                "nome_serie": ts_context["nome"],
                "contexto": ctx_json,
                "data_anomalia": a["data"],
                "valor_anomalia": a["valor"],
                "desvios": a["desvios_padrao"],
            }
            for a in ts_context.get("anomalias", [])
        ],
    }

    logger.info(
        f"Prompt inputs construídos: "
        f"{len(inputs['anomalias'])} anomalias para investigar"
    )
    return inputs
