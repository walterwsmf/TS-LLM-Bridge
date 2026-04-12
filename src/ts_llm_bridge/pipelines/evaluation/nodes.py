"""
pipelines/evaluation/nodes.py

Nodes de avaliação e relatório final.

Nodes:
  evaluate_llm_output    → score de qualidade + checks
  generate_final_report  → relatório consolidado (JSON)
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Checks individuais (funções puras)
# ----------------------------------------------------------------

def _check_campos(output: dict, campos: list[str]) -> tuple[bool, list[str]]:
    faltando = [c for c in campos if c not in output or output[c] is None]
    return len(faltando) == 0, [f"Campo ausente: '{c}'" for c in faltando]


def _check_tendencia(output: dict, ctx: dict) -> tuple[bool, list[str]]:
    if "tendencia" not in output:
        return False, ["Campo 'tendencia' ausente"]
    decl, calc = output["tendencia"], ctx.get("tendencia", "")
    if decl == calc:
        return True, []
    inc_norm = abs(ctx.get("inclinacao_por_periodo", 0)) / (abs(ctx.get("media", 1)) + 1e-9)
    if inc_norm < 0.01 and decl in ("estavel", calc):
        return True, []
    return False, [
        f"Tendência '{decl}' diverge da calculada '{calc}' "
        f"(inclinação normalizada={inc_norm:.3f})"
    ]


def _check_anomalias(output: dict, ctx: dict) -> tuple[bool, list[str]]:
    avisos = []
    resumo = output.get("resumo_anomalias", "")
    n_det = ctx.get("n_anomalias", 0)
    if n_det == 0 and "anomalia" in resumo.lower():
        avisos.append(
            "LLM menciona anomalias, mas nenhuma foi detectada numericamente. "
            "Possível hallucination — verifique threshold."
        )
    if n_det > 0 and "nenhuma" in resumo.lower():
        avisos.append(
            f"LLM diz 'nenhuma anomalia', mas {n_det} foram detectadas. "
            "Verifique se o contexto chegou corretamente ao prompt."
        )
    return len(avisos) == 0, avisos


def _check_confianca(output: dict, ctx: dict) -> tuple[bool, list[str]]:
    c = output.get("confianca_analise", 0.5)
    avisos = []
    if c > 0.95 and ctx.get("n_pontos", 0) < 24:
        avisos.append(
            f"Confiança {c:.2f} para série com {ctx['n_pontos']} pontos "
            "é provavelmente superestimada."
        )
    if c < 0.3:
        avisos.append(
            f"Confiança muito baixa ({c:.2f}) — contexto pode ser insuficiente."
        )
    return True, avisos


def _check_modelo(output: dict, ctx: dict) -> tuple[bool, list[str]]:
    modelo = output.get("modelo_recomendado", "")
    avisos = []
    if modelo == "LSTM" and ctx.get("n_pontos", 0) < 100:
        avisos.append(f"LSTM recomendado para {ctx['n_pontos']} pontos — requer >200.")
    if modelo == "SARIMA" and not ctx.get("periodo_sazonal"):
        avisos.append("SARIMA recomendado sem período sazonal detectado.")
    if modelo == "Naive" and ctx.get("forca_sazonalidade", 0) > 0.5:
        avisos.append(f"Naive para sazonalidade forte (F={ctx['forca_sazonalidade']:.2f}).")
    return True, avisos


# ----------------------------------------------------------------
# Node 1 — Avaliação do output LLM
# ----------------------------------------------------------------

CAMPOS_OBRIGATORIOS = [
    "narrativa_executiva", "tendencia", "modelo_recomendado",
    "justificativa_modelo", "confianca_analise",
]


def evaluate_llm_output(
    llm_analysis_output: dict,
    ts_context: dict,
    eval_params: dict,
) -> dict:
    """
    Avalia a qualidade da análise gerada pelo LLM.

    Kedro inputs:  llm_analysis_output, ts_context, params:evaluation
    Kedro output:  evaluation_result

    Args:
        llm_analysis_output: dict gerado por run_llm_analysis.
        ts_context: contexto TS original (ground truth).
        eval_params: subdict 'evaluation' do parameters.yml.

    Returns:
        Dict com score, checks, avisos, erros e status.
    """
    checks: dict[str, bool] = {}
    erros: list[str] = []
    avisos: list[str] = []

    runners = [
        ("campos_obrigatorios",   lambda: _check_campos(llm_analysis_output, CAMPOS_OBRIGATORIOS)),
        ("tendencia_consistente", lambda: _check_tendencia(llm_analysis_output, ts_context)),
        ("anomalias_coerentes",   lambda: _check_anomalias(llm_analysis_output, ts_context)),
        ("confianca_razoavel",    lambda: _check_confianca(llm_analysis_output, ts_context)),
        ("modelo_coerente",       lambda: _check_modelo(llm_analysis_output, ts_context)),
    ]

    for nome, fn in runners:
        ok, msgs = fn()
        checks[nome] = ok
        if nome in ("campos_obrigatorios", "tendencia_consistente") and not ok:
            erros.extend(msgs)
        else:
            avisos.extend(msgs)

    n = len(checks)
    score_base = sum(checks.values()) / n if n > 0 else 0.0
    max_pen_av = eval_params["max_penalidade_avisos"]
    pen_av = min(max_pen_av, len(avisos) * eval_params["penalidade_por_aviso"])
    pen_er = len(erros) * eval_params["penalidade_por_erro"]
    score = max(0.0, round(score_base - pen_av - pen_er, 3))
    passou = score >= eval_params["score_minimo"]

    status = "APROVADO" if passou else "REPROVADO"
    logger.info(
        f"Avaliação: {status} (score={score:.2f}) | "
        f"{sum(checks.values())}/{n} checks | "
        f"{len(erros)} erros | {len(avisos)} avisos"
    )

    return {
        "score_geral": score,
        "passou": passou,
        "status": status,
        "checks": checks,
        "erros": erros,
        "avisos": avisos,
        "avaliado_em": datetime.now().isoformat(),
    }


# ----------------------------------------------------------------
# Node 2 — Relatório final consolidado
# ----------------------------------------------------------------

def generate_final_report(
    ts_context: dict,
    llm_analysis_output: dict,
    anomaly_investigation: list[dict],
    model_recommendation: dict,
    evaluation_result: dict,
    cost_report: dict,
) -> dict:
    """
    Gera relatório final consolidando todas as saídas do pipeline.

    Kedro inputs:  todos os outputs anteriores
    Kedro output:  final_report

    Returns:
        Dict completo com todas as análises, avaliação e custo.
    """
    # Resumo executivo
    narrativa = llm_analysis_output.get("narrativa_executiva", "Análise não disponível.")
    modelo_rec = (
        model_recommendation
        .get("recomendacao_principal", {})
        .get("modelo", llm_analysis_output.get("modelo_recomendado", "—"))
    )

    report = {
        "serie": {
            "nome": ts_context.get("nome"),
            "periodo": f"{ts_context.get('periodo_inicio')} → {ts_context.get('periodo_fim')}",
            "n_pontos": ts_context.get("n_pontos"),
            "frequencia": ts_context.get("frequencia"),
        },
        "resumo_executivo": {
            "narrativa": narrativa,
            "tendencia": llm_analysis_output.get("tendencia"),
            "sazonalidade": llm_analysis_output.get("forca_sazonalidade"),
            "n_anomalias": ts_context.get("n_anomalias", 0),
            "modelo_recomendado": modelo_rec,
            "confianca": llm_analysis_output.get("confianca_analise"),
        },
        "analise_completa": llm_analysis_output,
        "anomalias_investigadas": anomaly_investigation,
        "recomendacao_modelo": model_recommendation,
        "qualidade": {
            "score": evaluation_result.get("score_geral"),
            "status": evaluation_result.get("status"),
            "n_erros": len(evaluation_result.get("erros", [])),
            "n_avisos": len(evaluation_result.get("avisos", [])),
        },
        "custo": {
            "total_usd": cost_report.get("custo_total_usd"),
            "tokens_total": cost_report.get("tokens_total"),
            "chamadas": cost_report.get("total_chamadas"),
            "latencia_media_ms": cost_report.get("latencia_media_ms"),
        },
        "gerado_em": datetime.now().isoformat(),
        "versao_pipeline": "0.1.0",
    }

    logger.info(
        f"Relatório final gerado: "
        f"score={evaluation_result.get('score_geral'):.2f}, "
        f"modelo={modelo_rec}, "
        f"custo=${cost_report.get('custo_total_usd', 0):.6f}"
    )
    return report
