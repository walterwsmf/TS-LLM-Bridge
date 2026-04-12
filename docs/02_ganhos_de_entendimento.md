# Ganhos de Entendimento

> *O que este projeto ensina que um tutorial de "Hello World com ChatGPT" nunca ensinaria.*

---

## 1. LLMs são modelos autoregressivos — você já conhece isso

A primeira coisa que um cientista de dados de séries temporais precisa internalizar é que um LLM **não é mágica**. É um modelo autoregressivo: P(token_t | token_0, token_1, ..., token_{t-1}).

Você já usa modelos assim. Um AR(p) simples é `y_t = φ₁·y_{t-1} + ... + φ_p·y_{t-p} + ε_t`. Um LLM faz exatamente a mesma coisa, mas:

- No espaço de tokens (não de valores numéricos)
- Com bilhões de parâmetros (não dezenas)
- Com atenção sobre toda a janela de contexto (não só os últimos p pontos)

**O ganho de entendimento aqui:** quando você vê um LLM "alucinar" uma data que não existia no input, está vendo o equivalente a um modelo AR extrapolando além do suporte dos dados de treino. Não é comportamento misterioso — é comportamento esperado de um modelo preditivo sem ancoragem forte.

---

## 2. Contexto é a sua janela deslizante

Em time series, você sabe que a qualidade do seu modelo depende criticamente da janela de features que você fornece. Um modelo que recebe os últimos 3 lags vai performar diferente de um que recebe 24 lags com decomposição sazonal.

**No LLM, o contexto é exatamente isso.** O que você coloca no `system prompt` + `user message` define completamente o que o modelo "vê". Enviar a série bruta como CSV (1.200 tokens para 48 meses) versus enviar as estatísticas chave (80 tokens) é equivalente a decidir entre raw features e features engenheiradas.

O `extract_ts_context` no projeto faz esse feature engineering **antes** da chamada ao LLM. Isso reduz custo em ~90% e, mais importante, **remove ambiguidade** — o modelo não precisa inferir tendência de uma sequência de números, você diz explicitamente `"tendencia": "crescente"`.

**O ganho aqui:** você aprende que "dar mais dados ao LLM" não é necessariamente melhor, exatamente como adicionar features irrelevantes piora um modelo de ML.

---

## 3. Temperatura é ruído estocástico — mas controlável

Em time series, você lida com decomposição `y_t = T_t + S_t + ε_t` onde ε é o componente estocástico. Você não quer ε no seu forecast; quer um modelo que capture T e S com fidelidade.

`temperature=0.0` em um LLM remove o componente estocástico da geração de tokens. Para análise de dados — onde você quer respostas determinísticas e reproduzíveis — **sempre use temperature=0**.

`temperature=1.0` seria útil para geração criativa (copys, histórias), mas é ruído indesejado quando você quer classificar uma anomalia ou recomendar um modelo de forecast.

**O ganho aqui:** você deixa de tratar o LLM como um oráculo imprevisível e passa a tratá-lo como um estimador com hiperparâmetro de variância controlável.

---

## 4. Output estruturado resolve o problema de "o modelo inventou um formato"

Este é provavelmente o **maior ganho prático** do projeto para quem quer usar LLMs em produção.

Em ML, você nunca aceita a saída de um modelo sem validação. Um `RandomForestClassifier.predict()` sempre retorna um array com as classes esperadas porque o contrato é garantido pelo tipo de retorno.

Com LLMs, sem structured output (Pydantic + JSON mode), o modelo pode retornar:
- `{"tendencia": "crescente"}` (correto)
- `A tendência é crescente.` (não parseável)
- `{"trend": "increasing"}` (campo errado, idioma errado)
- ` ```json\n{"tendencia": "crescente"}\n``` ` (markdown ao redor)

O `evaluate.py` implementa 5 checks automáticos exatamente para detectar esses casos. É o equivalente ao seu backtesting: você não confia no modelo sem medir a qualidade do output.

**O ganho aqui:** você aprende a tratar o output do LLM como dado não confiável até prova em contrário — o mesmo rigor epistemológico que você aplica a qualquer dado de entrada.

---

## 5. Custo é uma métrica de negócio, não um detalhe técnico

Em time series, você sabe que complexidade de modelo tem custo: LSTM leva 10x mais tempo para treinar que ARIMA. Você faz essa trade-off conscientemente.

Com LLMs, o custo é **literalmente financeiro**: cada token enviado e recebido tem preço. O projeto rastreia isso explicitamente no `consolidate_llm_logs`:

- `gpt-4o-mini`: ~$0.002 por análise completa de série mensal
- `gpt-4o`: ~$0.03 por análise completa (15× mais caro)
- `claude-3-5-sonnet`: ~$0.04 por análise

Enviar a série bruta vs. o contexto estruturado:
- Série bruta (48 meses): ~1.400 tokens → $0.00021
- Contexto estruturado: ~120 tokens → $0.000018 (**12× mais barato**)

**O ganho aqui:** você desenvolve o instinto de "quanto vai custar isso em produção?", que é uma habilidade crítica para qualquer DS que quer levar LLM para produto.

---

## 6. Kedro resolve o problema de "eu já chamei o LLM e não quero pagar de novo"

Este é um ganho de engenharia que você vai sentir na primeira vez que o pipeline quebrar no node de avaliação e você precisar rodar novamente.

Sem Kedro, você reexecutaria tudo — inclusive as chamadas ao LLM que custam dinheiro.

Com Kedro e o catálogo, o `llm_analysis_output.json` já está em disco. Você roda:

```bash
kedro run --pipeline=evaluation
```

E só o node de avaliação é executado. As chamadas ao LLM não são repetidas.

**O ganho aqui:** você aprende que infraestrutura de ML pipeline não é overhead burocrático — é o que torna LLMs viáveis em produção onde reprocessamento é caro.

---

## Resumo dos ganhos

| Conceito aprendido | Como se manifesta no projeto | Analogia TS |
|---|---|---|
| LLM como modelo autoregressivo | `temperature=0` para determinismo | AR(p) sem ruído |
| Contexto = janela de features | `extract_ts_context` reduz 90% dos tokens | Feature engineering |
| Output estruturado | Pydantic + JSON mode em `pipeline.py` | Schema de DataFrame |
| Validação de output | 5 checks em `evaluate.py` | Backtesting |
| Custo como métrica | `consolidate_llm_logs` + `cost_report` | Complexidade de modelo |
| Reprodutibilidade | Catálogo Kedro persiste cada saída | Versionamento de dados |
| Prompts como código | Templates em `prompts.py` versionados | Feature pipeline |
