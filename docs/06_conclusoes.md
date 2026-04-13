# Conclusões e Roadmap

> *O que você construiu, o que aprendeu e para onde ir daqui.*

---

## O que você construiu

Ao completar este projeto, você tem em mãos:

1. **Um produto funcional** — não um tutorial descartável. Um pipeline Kedro que aceita qualquer série temporal mensal e produz análise executiva, investigação de anomalias e recomendação de modelo, tudo com rastreabilidade completa.

2. **Uma base de código extensível** — 3 pipelines independentes que você pode modificar sem quebrar os outros. Quer adicionar um node de geração de código de pré-processamento? É um node novo no `llm_analysis` pipeline.

3. **Entendimento profundo de LLMs** — não como caixa preta, mas como estimadores com características conhecidas: custo por token, janela de contexto finita, tendência à alucinação, necessidade de output estruturado.

---

## O que você aprendeu — síntese

### LLMs como extensão do seu toolkit, não substituição

Você já sabia modelar séries temporais. Agora sabe que um LLM pode:
- **Explicar** o que seus modelos detectam (em linguagem executiva)
- **Classificar** anomalias com hipóteses causais (sem treino supervisionado)
- **Recomendar** próximos passos com justificativa técnica
- **Gerar código** adaptado às propriedades específicas da série

O LLM não faz o STL decomposition — você faz. O LLM não detecta a anomalia — você detecta. O LLM **contextualiza e comunica** o resultado de tudo que você já sabia fazer.

### Prompt engineering é feature engineering

A maior lição técnica do projeto: o trabalho mais importante não é a chamada à API. É o `extract_ts_context` — transformar uma série de 48 números em 15 features interpretáveis que custam 80 tokens em vez de 1.400.

Isso é exatamente o que você já faz em ML: feature engineering reduz dimensionalidade, remove ruído e melhora o sinal. No mundo de LLMs, o mesmo princípio reduz custo, melhora qualidade e elimina ambiguidade.

### Validação de output é inegociável

Se você só levar uma coisa deste projeto: **nunca confie no output do LLM sem validar**. O `evaluate.py` com 5 checks não é perfeccionismo — é o mínimo necessário para usar LLMs em qualquer pipeline de dados.

Um analista humano pode errar. Um LLM pode errar com muito mais confiança e consistência. O rigor analítico que você aplica a dados brutos se aplica igualmente a saídas de modelos de linguagem.

### Kedro foi a escolha certa para LLM

A decisão de usar Kedro em vez de um script Python linear não foi estética. Foi prática:
- **Custo**: você reprocessa só o que mudou
- **Debug**: você inspeciona cada dataset intermediário isoladamente
- **Evolução**: você adiciona nodes sem refatorar código existente
- **Time**: qualquer pessoa com conhecimento de Kedro entende o projeto em 10 minutos pelo `kedro viz`

---

## O que este projeto não cobre (e por que)

### RAG (Retrieval-Augmented Generation)
RAG conecta o LLM a uma base de conhecimento externa via busca vetorial. Útil quando você tem documentos de contexto (relatórios históricos, comentários de analistas) que precisam alimentar a análise. Próximo passo natural após dominar este projeto.

### Agents e Tool Use
Agents permitem que o LLM decida quais ferramentas chamar baseado no input. Para time series, um agent poderia decidir autonomamente se aplica STL, se chama `adfuller`, se investigar anomalias — sem regras hard-coded. Requer domínio sólido de prompt engineering primeiro.

### Fine-tuning
Retreinar o LLM com seus dados específicos. Raramente necessário para análise de dados — geralmente um bom system prompt substitui. Vale considerar quando você tem terminologia muito proprietária ou estilo de narrativa muito específico.

### Avaliação automatizada em lote (LLM as judge)
Usar um LLM (geralmente mais capaz) para avaliar o output de outro LLM. O `evaluate.py` atual usa regras heurísticas — o próximo nível é usar `gpt-4o` para avaliar a qualidade narrativa das saídas do `gpt-4o-mini`.

---

## Roadmap de próximos passos

### Nível 1 — Consolidar (1-2 semanas)
- [ ] Adicionar testes unitários para cada node com `pytest` + dados sintéticos
- [ ] Implementar few-shot no `run_anomaly_investigation` com 3-5 exemplos anotados
- [ ] Testar com séries reais do domínio de interesse
- [ ] Implementar o node `gerar_codigo_preprocessing` usando o `PROMPT_CODIGO_PREPROCESSING`

### Nível 2 — Expandir (2-4 semanas)
- [ ] Adicionar suporte a múltiplas séries em paralelo (Kedro multi-dataset)
- [ ] Implementar `LLMCostHook` ativo com alerta quando custo > threshold
- [ ] Criar dashboard Streamlit que carrega o `final_report.json`
- [ ] Versionar datasets com `kedro-mlflow` ou `kedro-datasets[versioned]`

### Nível 3 — Aprofundar LLM (4-8 semanas)
- [ ] Estudar LangGraph para pipelines com lógica condicional (agent-like)
- [ ] Implementar RAG com documentos contextuais (ex: documentos históricos)
- [ ] Explorar Anthropic Claude para comparar com OpenAI no mesmo pipeline
- [ ] Estudar embeddings e busca semântica com `pgvector` ou `FAISS`

### Nível 4 — Produtizar
- [ ] Documentar trade-offs de custo (gpt-4o-mini vs gpt-4o) para decisão executiva
- [ ] Escrever proposta de valor: "o que este pipeline economiza em horas de analista?"
- [ ] Mapear casos de uso adicionais no domínio do seu projeto
- [ ] Estruturar como produto interno: API FastAPI que recebe CSV e retorna `final_report`

---

## Métricas de sucesso do aprendizado

Você completou este projeto com sucesso se:

**Técnico**
- [ ] Consegue explicar a diferença entre `temperature=0` e `temperature=1` sem consultar docs
- [ ] Sabe quando usar few-shot vs zero-shot (e por que)
- [ ] Entende por que o `extract_ts_context` é mais valioso que a chamada ao LLM
- [ ] Consegue adicionar um novo node ao pipeline sem quebrar os existentes
- [ ] Sabe o custo estimado de analisar 100 séries mensais com `gpt-4o-mini`

**Produto**
- [ ] Consegue descrever o pipeline para um stakeholder não-técnico em 2 minutos
- [ ] Sabe quais casos de uso **não** se beneficiam de LLM (e por que)
- [ ] Consegue estimar esforço e custo de adaptar o projeto para um novo domínio

**Mindset**
- [ ] Trata saídas de LLM com o mesmo ceticismo que trata dados brutos
- [ ] Pensa em prompts como código: versionados, testados, documentados
- [ ] Vê Kedro (ou qualquer pipeline framework) como aliado, não overhead

---

## Reflexão final

Integrar LLMs em pipelines de dados não é aprender uma tecnologia do zero — é reconhecer que boas práticas de engenharia de dados já cobrem a maior parte do caminho.

O que muda ao incorporar LLMs:

| Antes (TS clássico) | Com LLM |
|---|---|
| Features numéricas como input | Texto + features como contexto |
| Modelos sklearn/statsmodels | Chamadas à API com prompts |
| Métricas: MAPE, RMSE | Métricas: score de avaliação, hallucination rate |
| Custo: tempo de CPU | Custo: tokens × preço/1M |
| Reproducibilidade: random_state | Reproducibilidade: temperature=0 + Kedro |
| Validação: backtesting | Validação: checks automáticos de output |

O que **não** muda: o rigor científico, a desconfiança saudável de qualquer modelo, a necessidade de validar antes de confiar, e o foco em entregar valor para o negócio — não em usar a tecnologia mais nova por ser nova.
