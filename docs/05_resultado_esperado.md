# Resultado Esperado por Etapa

> *O que o pipeline produz de concreto em cada fase — com exemplos reais de output.*

---

## Após `kedro run --pipeline=features_only`

### Dataset gerado: `ts_context.json`

```json
{
  "nome": "serie_principal",
  "n_pontos": 48,
  "frequencia": "mensal",
  "periodo_inicio": "2020-01-31",
  "periodo_fim": "2023-12-31",
  "media": 123.45,
  "desvio_padrao": 22.18,
  "minimo": 85.20,
  "maximo": 231.60,
  "tendencia": "crescente",
  "inclinacao_por_periodo": 0.8421,
  "forca_sazonalidade": 0.847,
  "periodo_sazonal": 12,
  "estacionaria": false,
  "n_anomalias": 1,
  "anomalias": [
    {
      "data": "2022-10-31",
      "valor": 231.60,
      "desvios_padrao": 4.87,
      "tipo": "spike_positivo"
    }
  ],
  "coef_variacao": 0.180,
  "ultima_media_3p": 157.32
}
```

**O que você aprende aqui:** O contexto é sua "radiografia" da série — sem chamar o LLM, você já sabe que ela tem sazonalidade forte (0.847), tendência crescente e uma anomalia em outubro/2022. Esse JSON é tudo que o LLM vai ver.

---

## Após `kedro run --pipeline=llm_analysis`

### Dataset gerado: `llm_analysis_output.json`

```json
{
  "narrativa_executiva": "A série apresenta crescimento consistente de 0.84 unidades/mês ao longo de 4 anos, com sazonalidade anual bem definida (força 0.85), sugerindo padrão cíclico estável. Em outubro de 2022, um spike positivo de 4.9 desvios-padrão interrompeu o padrão histórico, demandando investigação causal antes de qualquer modelagem. O comportamento recente (média últimos 3 períodos: 157,3) está acima da média histórica (123,5), sinalizando aceleração de tendência.",
  "tendencia": "crescente",
  "intensidade_tendencia": "moderada",
  "forca_sazonalidade": "forte",
  "resumo_anomalias": "Uma anomalia positiva detectada em outubro/2022 (+4.87σ), possivelmente relacionada a evento pontual externo à série.",
  "modelo_recomendado": "SARIMA",
  "justificativa_modelo": "A combinação de tendência crescente (não-estacionária), sazonalidade forte de período 12 e volume adequado de dados (48 pontos) favorece SARIMA(p,1,q)(P,1,Q)[12]. A anomalia em out/2022 deve ser tratada como intervenção antes do ajuste.",
  "proximo_passo_analise": "Investigar causa do spike em out/2022 com dados externos (campanhas, eventos, sazonalidade atípica). Após confirmação, imputar ou modelar como intervenção antes de ajustar o SARIMA.",
  "confianca_analise": 0.88,
  "alertas": [
    "Série com apenas 48 pontos: SARIMA sazonal pode ser instável para ordens P,Q > 1. Comece com (1,1,1)(1,1,1)[12]."
  ]
}
```

### Dataset gerado: `anomaly_investigation.json`

```json
[
  {
    "data": "2022-10-31",
    "valor": 231.60,
    "classificacao": "spike_positivo",
    "confianca_classificacao": 0.82,
    "hipoteses": [
      {
        "hipotese": "Evento promocional ou campanhas de marketing de alto impacto no período",
        "probabilidade": "alta",
        "dado_para_validar": "Cruzar com dados de campanhas e investimento em marketing de out/2022"
      },
      {
        "hipotese": "Erro de registro ou duplicação de lançamentos no sistema de origem",
        "probabilidade": "media",
        "dado_para_validar": "Auditar registros brutos da fonte de dados para o mês referente"
      }
    ],
    "impacto_no_forecast": "Sem tratamento, o spike inflará a componente de tendência e distorcerá a estimativa sazonal de outubro. SARIMA e Prophet são sensíveis a outliers aditivos.",
    "tratamento_recomendado": "investigar",
    "justificativa_tratamento": "Confiança insuficiente para imputar sem validar causa. Manter como flag até cruzamento com fontes externas."
  }
]
```

### Dataset gerado: `cost_report.json`

```json
{
  "total_chamadas": 3,
  "chamadas_sucedidas": 3,
  "custo_total_usd": 0.000342,
  "tokens_total": 1847,
  "latencia_media_ms": 1234,
  "por_tipo": {
    "analise_completa":  {"custo_usd": 0.000198, "tokens": 1024, "latencia_ms": 1450},
    "anomalia_2022-10-31": {"custo_usd": 0.000089, "tokens": 512, "latencia_ms": 980},
    "selecao_modelo":    {"custo_usd": 0.000055, "tokens": 311, "latencia_ms": 1272}
  }
}
```

**Custo total da análise completa: $0.000342 — menos de um centavo.**

---

## Após `kedro run` (pipeline completo)

### Dataset gerado: `evaluation_result.json`

```json
{
  "score_geral": 0.91,
  "passou": true,
  "status": "APROVADO",
  "checks": {
    "campos_obrigatorios": true,
    "tendencia_consistente": true,
    "anomalias_coerentes": true,
    "confianca_razoavel": true,
    "modelo_coerente": true
  },
  "erros": [],
  "avisos": [
    "Confiança 0.88 para série com 48 pontos — razoável, mas conserve ceticismo em séries mais curtas."
  ],
  "avaliado_em": "2024-11-15T14:32:01.123456"
}
```

### Dataset gerado: `final_report.json`

```json
{
  "serie": {
    "nome": "serie_principal",
    "periodo": "2020-01-31 → 2023-12-31",
    "n_pontos": 48,
    "frequencia": "mensal"
  },
  "resumo_executivo": {
    "narrativa": "A série apresenta crescimento consistente...",
    "tendencia": "crescente",
    "sazonalidade": "forte",
    "n_anomalias": 1,
    "modelo_recomendado": "SARIMA",
    "confianca": 0.88
  },
  "analise_completa": { ... },
  "anomalias_investigadas": [ ... ],
  "recomendacao_modelo": { ... },
  "qualidade": {
    "score": 0.91,
    "status": "APROVADO",
    "n_erros": 0,
    "n_avisos": 1
  },
  "custo": {
    "total_usd": 0.000342,
    "tokens_total": 1847,
    "chamadas": 3,
    "latencia_media_ms": 1234
  },
  "gerado_em": "2024-11-15T14:32:05.456789",
  "versao_pipeline": "0.1.0"
}
```

---

## O que o `kedro viz` mostra

Após instalar `pip install kedro-viz` e rodar `kedro viz`, você vê o grafo completo:

```
[params:synthetic_data] ──► [generate_synthetic_series] ──► (synthetic_series)
                                                                     │
[params:feature_extraction] ─────────────────────────────────────────┤
                                                                     ▼
                                                    [validate_and_clean_series]
                                                             │
                                                             ▼
                                                    (clean_series)
                                                             │
                                                             ▼
                                                    [extract_ts_context]
                                                             │
                                                             ▼
                                                    (ts_context) ──────────────┐
                                                             │                  │
                                                             ▼                  │
                                                    [build_prompt_inputs]       │
                                                             │                  │
                                                             ▼                  │
                                                    (prompt_inputs)             │
                                                    ╔═══╦═══╗                  │
                                                    ▼   ▼   ▼                  │
                                              [LLM] [LLM] [LLM]               │
                                                    ╚═══╩═══╝                  │
                                                         │                     │
                                              [consolidate_logs]               │
                                                    │         │                 │
                                             (cost_report)    └─────────────────┘
                                                                               │
                                                                ▼              ▼
                                                    [evaluate_llm_output]
                                                               │
                                                    (evaluation_result)
                                                               │
                                                    [generate_final_report]
                                                               │
                                                    (final_report) ◄── PRODUTO FINAL
```

Este grafo é o artefato que você apresenta para um time de engenharia como prova de que o pipeline é rastreável, reproduzível e documentado.

---

## Comparativo: com e sem LLM

| Análise | Abordagem tradicional | Com TS-LLM Bridge |
|---|---|---|
| Descrever série para CFO | Analista escreve manualmente (~1h) | Automático, 1.4s, $0.0002 |
| Classificar anomalia | Engenheiro analisa gráfico (~30min) | Automático com hipóteses |
| Escolher modelo forecast | Reunião de equipe (~2h) | Justificativa técnica imediata |
| Gerar código de pré-proc | Dev escreve (~45min) | Código adaptado à série |
| Documentar análise | Analista documenta (~2h) | `final_report.json` pronto |
