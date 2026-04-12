"""
pipelines/llm_analysis/nodes.py

Nodes da pipeline de análise LLM.

Cada node é stateless — o estado (logs, custo) é retornado como
dataset para o catálogo, nunca armazenado na instância.

Nodes:
  run_llm_analysis           → análise completa da série
  run_anomaly_investigation  → investigação de cada anomalia
  run_model_recommendation   → seleção de modelo de forecast
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Helpers de custo e retry
# ----------------------------------------------------------------

_PRECOS_POR_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":                (0.15,  0.60),
    "gpt-4o":                     (2.50, 10.00),
    "claude-3-haiku-20240307":    (0.25,  1.25),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "gemini-2.0-flash":           (0.10,  0.40),
    "gemini-1.5-flash":           (0.075, 0.30),
    "gemini-1.5-pro":             (1.25,  5.00),
}


def _calcular_custo(modelo: str, tokens_in: int, tokens_out: int) -> float:
    pi, po = _PRECOS_POR_1M.get(modelo, (0.15, 0.60))
    return round((tokens_in * pi + tokens_out * po) / 1_000_000, 8)


def _extrair_tokens(response) -> tuple[int, int]:
    """Extrai tokens de uso da resposta do LLM (OpenAI e Anthropic)."""
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        meta = response.usage_metadata
        return (
            meta.get("input_tokens", 0),
            meta.get("output_tokens", 0),
        )
    if hasattr(response, "response_metadata"):
        meta = response.response_metadata.get("token_usage", {})
        return (
            meta.get("prompt_tokens", 0),
            meta.get("completion_tokens", 0),
        )
    return 0, 0


def _criar_llm(modelo: str, temperatura: float, provider: str):
    """
    Instancia o LLM LangChain.

    As API keys são lidas automaticamente das variáveis de ambiente
    populadas pelo CredentialsToEnvHook (OPENAI_API_KEY, etc.).
    """
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=modelo, temperature=temperatura)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=modelo, temperature=temperatura)
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=modelo, temperature=temperatura)
    else:
        raise ValueError(f"Provider desconhecido: {provider}. Use: openai | anthropic | google")


def _parsear_json_resposta(content: str) -> dict:
    """Parseia JSON mesmo com lixo ao redor (ex: ```json ... ```)."""
    import re
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Resposta não é JSON válido: {content[:300]}")


def _chamar_com_retry(
    llm,
    messages,
    modelo: str,
    tipo_analise: str,
    max_tentativas: int,
    timeout: int,
) -> tuple[dict, dict]:
    """
    Executa a chamada ao LLM com retry e retorna (resultado, log_entry).
    """
    ultimo_erro = None

    for tentativa in range(1, max_tentativas + 1):
        t0 = time.monotonic()
        try:
            response = llm.invoke(messages)
            latencia_ms = round((time.monotonic() - t0) * 1000, 1)
            tokens_in, tokens_out = _extrair_tokens(response)
            resultado = _parsear_json_resposta(response.content)

            log = {
                "timestamp": datetime.now().isoformat(),
                "tipo_analise": tipo_analise,
                "modelo_llm": modelo,
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
                "tokens_total": tokens_in + tokens_out,
                "custo_usd": _calcular_custo(modelo, tokens_in, tokens_out),
                "latencia_ms": latencia_ms,
                "tentativa": tentativa,
                "sucesso": True,
                "erro": None,
            }
            logger.info(
                f"✓ [{tipo_analise}] {tokens_in + tokens_out} tokens | "
                f"${log['custo_usd']:.6f} | {latencia_ms:.0f}ms"
            )
            return resultado, log

        except Exception as e:
            ultimo_erro = e
            latencia_ms = round((time.monotonic() - t0) * 1000, 1)
            logger.warning(
                f"Tentativa {tentativa}/{max_tentativas} falhou: {e}"
            )
            if tentativa < max_tentativas:
                wait = 2 ** tentativa
                logger.info(f"Aguardando {wait}s antes de retry...")
                time.sleep(wait)

    log = {
        "timestamp": datetime.now().isoformat(),
        "tipo_analise": tipo_analise,
        "modelo_llm": modelo,
        "tokens_input": 0,
        "tokens_output": 0,
        "tokens_total": 0,
        "custo_usd": 0.0,
        "latencia_ms": 0.0,
        "tentativa": max_tentativas,
        "sucesso": False,
        "erro": str(ultimo_erro),
    }
    logger.error(f"✗ [{tipo_analise}] falhou após {max_tentativas} tentativas: {ultimo_erro}")
    return {}, log


# ----------------------------------------------------------------
# Templates de prompt (inline para manter o node stateless)
# ----------------------------------------------------------------

_BASE_SYSTEM = """Você é um analista sênior especializado em séries temporais com 15 anos de experiência.
Regras inegociáveis:
1. Nunca invente números, datas ou valores fora do contexto fornecido.
2. Se uma informação não estiver disponível, diga "dado insuficiente".
3. Responda APENAS com JSON válido — sem markdown, sem texto fora do JSON.
4. Use português do Brasil."""

_SYSTEM_ANALISE = _BASE_SYSTEM
_SYSTEM_ANOMALIA = _BASE_SYSTEM + "\nEspecialização: classificação e investigação causal de anomalias."
_SYSTEM_MODELO   = _BASE_SYSTEM + "\nEspecialização: seleção de modelos de forecasting com justificativa técnica."


# ----------------------------------------------------------------
# Node 1 — Análise completa da série
# ----------------------------------------------------------------

def run_llm_analysis(
    prompt_inputs: dict,
    llm_params: dict,
) -> tuple[dict, dict]:
    """
    Executa análise completa da série temporal com LLM.

    Kedro inputs:  prompt_inputs, params:llm
    Kedro outputs: llm_analysis_output, analysis_log

    API keys lidas das variáveis de ambiente via CredentialsToEnvHook.

    Args:
        prompt_inputs: dict gerado por build_prompt_inputs.
        llm_params: subdict 'llm' do parameters.yml.

    Returns:
        Tuple (analysis_dict, log_entry_dict).
    """
    llm = _criar_llm(
        llm_params["modelo"],
        llm_params["temperatura"],
        llm_params["provider"],
    )

    analise_inputs = prompt_inputs["analise_completa"]
    user_msg = (
        f"Contexto da série temporal:\n{analise_inputs['contexto']}\n\n"
        f"Pergunta: {analise_inputs['pergunta']}\n\n"
        f'Responda com este JSON:\n{{'
        f'"narrativa_executiva": "<3 frases para CFO>",'
        f'"tendencia": "<crescente|decrescente|estavel>",'
        f'"intensidade_tendencia": "<fraca|moderada|forte>",'
        f'"forca_sazonalidade": "<nenhuma|fraca|moderada|forte>",'
        f'"resumo_anomalias": "<padrão geral ou nenhuma detectada>",'
        f'"modelo_recomendado": "<SARIMA|Prophet|XGBoost|LSTM|ETS|Naive>",'
        f'"justificativa_modelo": "<2 frases técnicas>",'
        f'"proximo_passo_analise": "<ação concreta>",'
        f'"confianca_analise": 0.0,'
        f'"alertas": []}}'
    )

    from langchain_core.messages import HumanMessage, SystemMessage
    messages = [SystemMessage(content=_SYSTEM_ANALISE), HumanMessage(content=user_msg)]

    resultado, log = _chamar_com_retry(
        llm, messages,
        modelo=llm_params["modelo"],
        tipo_analise="analise_completa",
        max_tentativas=llm_params["max_tentativas"],
        timeout=llm_params["timeout_segundos"],
    )
    return resultado, log


# ----------------------------------------------------------------
# Node 2 — Investigação de anomalias
# ----------------------------------------------------------------

def run_anomaly_investigation(
    prompt_inputs: dict,
    ts_context: dict,
    llm_params: dict,
    anomaly_params: dict,
) -> tuple[list[dict], list[dict]]:
    """
    Investiga cada anomalia detectada individualmente.

    Kedro inputs:  prompt_inputs, ts_context, params:llm, params:anomaly_analysis
    Kedro outputs: anomaly_investigation, anomaly_logs

    Args:
        prompt_inputs: dict gerado por build_prompt_inputs.
        ts_context: contexto TS (para referência na investigação).
        llm_params: configuração do LLM.
        anomaly_params: subdict 'anomaly_analysis'.

    Returns:
        Tuple (lista de resultados, lista de logs).
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = _criar_llm(
        llm_params["modelo"],
        llm_params["temperatura"],
        llm_params["provider"],
    )

    anomalias = prompt_inputs.get("anomalias", [])
    max_inv = anomaly_params.get("max_anomalias_investigar", 3)

    if not anomaly_params.get("investigar_todas", False):
        anomalias = anomalias[:max_inv]

    resultados = []
    logs = []

    for i, anom_inputs in enumerate(anomalias):
        logger.info(
            f"Investigando anomalia {i+1}/{len(anomalias)}: "
            f"{anom_inputs['data_anomalia']}"
        )

        user_msg = (
            f"Série: {anom_inputs['nome_serie']}\n"
            f"Contexto: {anom_inputs['contexto']}\n\n"
            f"Anomalia:\n"
            f"- Data: {anom_inputs['data_anomalia']}\n"
            f"- Valor: {anom_inputs['valor_anomalia']}\n"
            f"- Desvios: {anom_inputs['desvios']} σ\n\n"
            f'Responda com:\n{{'
            f'"classificacao": "<spike_positivo|spike_negativo|outlier_sazonal|mudanca_nivel|dado_suspeito>",'
            f'"confianca_classificacao": 0.0,'
            f'"hipoteses": [{{"hipotese": "", "probabilidade": "<alta|media|baixa>", "dado_para_validar": ""}}],'
            f'"impacto_no_forecast": "",'
            f'"tratamento_recomendado": "<imputar|manter|investigar|remover>",'
            f'"justificativa_tratamento": ""}}'
        )

        messages = [SystemMessage(content=_SYSTEM_ANOMALIA), HumanMessage(content=user_msg)]
        resultado, log = _chamar_com_retry(
            llm, messages,
            modelo=llm_params["modelo"],
            tipo_analise=f"anomalia_{anom_inputs['data_anomalia']}",
            max_tentativas=llm_params["max_tentativas"],
            timeout=llm_params["timeout_segundos"],
        )

        if resultado:
            resultado["data"] = anom_inputs["data_anomalia"]
            resultado["valor"] = anom_inputs["valor_anomalia"]
            resultados.append(resultado)
        logs.append(log)

    logger.info(f"Investigação concluída: {len(resultados)}/{len(anomalias)} anomalias analisadas")
    return resultados, logs


# ----------------------------------------------------------------
# Node 3 — Recomendação de modelo de forecast
# ----------------------------------------------------------------

def run_model_recommendation(
    prompt_inputs: dict,
    llm_params: dict,
) -> tuple[dict, dict]:
    """
    Recomenda modelo de forecast com justificativa técnica.

    Kedro inputs:  prompt_inputs, params:llm
    Kedro outputs: model_recommendation, rec_log
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = _criar_llm(
        llm_params["modelo"],
        llm_params["temperatura"],
        llm_params["provider"],
    )

    rec_inputs = prompt_inputs["selecao_modelo"]
    user_msg = (
        f'Propriedades da série "{rec_inputs["nome_serie"]}":\n'
        f"{rec_inputs['contexto']}\n\n"
        f"Horizonte: {rec_inputs['horizonte']} períodos\n"
        f"Prioridade: {rec_inputs['prioridade']}\n\n"
        f'Responda com:\n{{'
        f'"recomendacao_principal": {{"modelo": "", "justificativa": "", '
        f'"pre_requisitos": [], "hiperparametros_sugeridos": {{}}}},'
        f'"alternativas": [{{"modelo": "", "vantagem": "", "desvantagem": ""}}],'
        f'"pre_processamento_necessario": [],'
        f'"metrica_avaliacao_recomendada": "",'
        f'"justificativa_metrica": ""}}'
    )

    messages = [SystemMessage(content=_SYSTEM_MODELO), HumanMessage(content=user_msg)]
    resultado, log = _chamar_com_retry(
        llm, messages,
        modelo=llm_params["modelo"],
        tipo_analise="selecao_modelo",
        max_tentativas=llm_params["max_tentativas"],
        timeout=llm_params["timeout_segundos"],
    )
    return resultado, log


# ----------------------------------------------------------------
# Node 4 — Consolida logs de custo da pipeline LLM
# ----------------------------------------------------------------

def consolidate_llm_logs(
    analysis_log: dict,
    anomaly_logs: list[dict],
    recommendation_log: dict,
) -> dict:
    """
    Consolida todos os logs de chamada LLM em um relatório de custo.

    Kedro inputs:  outputs dos nodes anteriores (logs parciais)
    Kedro output:  cost_report
    """

    todos_logs = [analysis_log] + anomaly_logs + [recommendation_log]
    sucedidos = [l for l in todos_logs if l.get("sucesso")]

    custo_total = sum(l["custo_usd"] for l in sucedidos)
    tokens_total = sum(l["tokens_total"] for l in sucedidos)
    lat_media = (
        sum(l["latencia_ms"] for l in sucedidos) / len(sucedidos)
        if sucedidos else 0
    )

    report = {
        "total_chamadas": len(todos_logs),
        "chamadas_sucedidas": len(sucedidos),
        "custo_total_usd": round(custo_total, 8),
        "tokens_total": tokens_total,
        "latencia_media_ms": round(lat_media, 1),
        "por_tipo": {
            l["tipo_analise"]: {
                "custo_usd": round(l["custo_usd"], 8),
                "tokens": l["tokens_total"],
                "latencia_ms": l["latencia_ms"],
            }
            for l in sucedidos
        },
        "gerado_em": datetime.now().isoformat(),
    }

    logger.info(
        f"Custo total da sessão: ${custo_total:.6f} | "
        f"{tokens_total} tokens | {len(todos_logs)} chamadas"
    )
    return report
