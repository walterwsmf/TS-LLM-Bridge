# TS-LLM Bridge — Documentação do Projeto

> **Público-alvo:** Cientista de dados sênior em time series fazendo transição para LLM.
> Você não está aprendendo Python do zero — está aprendendo a pensar diferente sobre modelos.

---

## O que é este projeto

O **TS-LLM Bridge** é um projeto de aprendizado estruturado como produto real. Ele conecta duas expertises: sua base sólida em séries temporais e o novo paradigma de Large Language Models. A metáfora central do projeto é simples:

> *Você já sabe detectar padrões. O LLM aprende a comunicá-los.*

Em vez de substituir seu conhecimento, o projeto usa tudo que você já domina — STL decomposition, detecção de anomalias, ADF test, seleção de modelos — como **input** para um LLM que gera narrativas executivas, hipóteses causais e código de pré-processamento adaptado.

---

## Por que Kedro

Kedro não é apenas estrutura de pastas. Para um cientista de dados sênior, ele resolve três problemas reais:

**1. Reproducibilidade de experimentos com LLM**
Chamadas a LLMs são não-determinísticas (temperature > 0) e custam dinheiro. O catálogo do Kedro persiste cada saída intermediária — você nunca repaga por um contexto que já foi extraído.

**2. Separação de concerns**
Parâmetros no `parameters.yml`, credenciais no `credentials.yml`, dados no catálogo. Quando você mudar de `gpt-4o-mini` para Claude, só muda uma linha no YAML — sem tocar em código.

**3. Testabilidade de nodes**
Cada node é uma função pura. Você testa `extract_ts_context(df, params)` exatamente como testaria um transformer sklearn, sem precisar mockar chamadas de API.

---

## Estrutura do projeto

```
ts_llm_bridge/              ← Projeto Kedro
├── conf/
│   ├── base/
│   │   ├── catalog.yml     ← Onde cada dataset vive (caminho, formato, tipo)
│   │   ├── parameters.yml  ← Todos os hiperparâmetros (STL, LLM, avaliação)
│   │   └── logging.yml     ← Logging por módulo
│   └── local/
│       └── credentials.yml ← API keys (nunca commitar — já no .gitignore)
│
├── src/ts_llm_bridge/
│   ├── pipelines/
│   │   ├── feature_extraction/ ← Pipeline 1: TS → contexto estruturado
│   │   ├── llm_analysis/       ← Pipeline 2: contexto → LLM → JSON validado
│   │   └── evaluation/         ← Pipeline 3: output LLM → score + relatório
│   ├── pipeline_registry.py    ← Composição de pipelines nomeados
│   ├── hooks.py                ← Timing + resumo de custo automático
│   └── settings.py             ← OmegaConf config loader
│
├── data/                   ← Camadas de dados (01_raw → 08_reporting)
├── docs/                   ← Esta documentação
└── pyproject.toml
```

---

## Como os pipelines se conectam

```
params:synthetic_data
       │
       ▼
[generate_synthetic_series] ──► synthetic_series (CSV)
       │
       ▼
[validate_and_clean_series] ──► clean_series (CSV validado)
       │
       ▼
[extract_ts_context] ──────────► ts_context (JSON com features STL/ADF)
       │
       ▼
[build_prompt_inputs] ─────────► prompt_inputs (JSON com templates prontos)
       │
       ├──► [run_llm_analysis] ──────────── llm_analysis_output (JSON)
       ├──► [run_anomaly_investigation] ──── anomaly_investigation (JSON)
       └──► [run_model_recommendation] ───── model_recommendation (JSON)
                                              │
                                              ▼
                                    [consolidate_llm_logs] ──► cost_report
                                              │
                                    [evaluate_llm_output] ───► evaluation_result
                                              │
                                    [generate_final_report] ──► final_report
```

Cada seta é um **dataset no catálogo** — persistido em disco, recarregável, versionável.

---

## Próximos documentos

| Arquivo | Conteúdo |
|---|---|
| `02_ganhos_de_entendimento.md` | O que você aprende de LLM que não aprenderia só lendo artigos |
| `03_conceitos_llm.md` | Tokenização, contexto, temperatura, roles — com analogias TS |
| `04_tecnicas_llm.md` | Prompt engineering, few-shot, chain-of-thought, structured output |
| `05_por_que_cada_tecnica.md` | Justificativa técnica de cada decisão de design do pipeline |
| `06_resultado_esperado.md` | O que o projeto produz ao final de cada etapa |
| `07_conclusoes.md` | Síntese do aprendizado e roadmap de próximos passos |
