# Conceitos de LLM Usados no Projeto

> *Cada conceito é apresentado com analogia direta em time series.*

---

## Conceito 1 — Tokenização

### O que é
Tokens são as unidades básicas de processamento de um LLM. Não são palavras inteiras — são pedaços de texto que o modelo aprendeu a reconhecer durante o treino.

```
"sazonalidade" → ["sazon", "alidade"]        # 2 tokens
"STL"          → ["STL"]                     # 1 token
"2024-01-15"   → ["202", "4", "-", "01", "-15"]  # 5 tokens
```

### Por que importa no projeto
O `extract_ts_context` estima tokens antes de qualquer chamada à API. Enviar 48 datas no formato `2020-01-31` custa ~240 tokens só para o índice. Enviar `"periodo": "2020-01 → 2023-12"` custa 12 tokens.

### Analogia TS
Resolução temporal. Uma série diária tem 365× mais pontos que uma série anual, mas não necessariamente 365× mais informação. Tokens são como a "resolução de texto" — mais tokens não significa mais contexto útil.

### Onde aparece no código
```python
# features.py — estimativa de custo antes da chamada
def _estimar_tokens(contexto_dict: dict) -> int:
    texto = str(contexto_dict)
    return int(len(texto) * 1.3)  # ~1.3 tokens/caractere para pt-BR
```

---

## Conceito 2 — Janela de Contexto (Context Window)

### O que é
O número máximo de tokens que um LLM processa em uma única chamada. Inclui o sistema de prompt, a mensagem do usuário e a resposta gerada.

- `gpt-4o-mini`: 128.000 tokens (~100.000 palavras)
- `claude-3-5-sonnet`: 200.000 tokens

### Por que importa no projeto
Uma série mensal de 10 anos tem ~120 pontos. Enviada como CSV, ocupa ~2.000 tokens — bem dentro da janela. Mas uma série diária de 5 anos tem ~1.825 pontos e ocuparia ~20.000 tokens como CSV. O design de enviar contexto estruturado resolve isso independente do tamanho da série.

### Analogia TS
O **lag máximo** de um modelo AR ou a **profundidade histórica** de um LSTM. O modelo "esquece" o que está além da janela exatamente como um AR(24) não "vê" o que aconteceu há 25 períodos.

### Onde aparece no código
```python
# prompt_inputs construído em features.py
ctx_json = json.dumps(ts_context, ensure_ascii=False, indent=2)
# → ~200-400 tokens independente do tamanho da série original
```

---

## Conceito 3 — Roles (System / User / Assistant)

### O que é
O formato de mensagens de um LLM de chat. Três roles definem quem fala:

- **System**: instrução de comportamento global (tom, restrições, expertise)
- **User**: a pergunta ou tarefa específica
- **Assistant**: a resposta do modelo (usado para histórico multi-turn)

### Por que importa no projeto
O `system prompt` é onde você "configura" o modelo para se comportar como analista de séries temporais. Sem ele, o mesmo modelo que analisa series pode também escrever poesia e dar receitas de bolo — com resultados inconsistentes para análise técnica.

### Analogia TS
O system prompt é como os **hyperparâmetros fixos** do modelo. Você define antes do treino (aqui, antes da chamada) e eles não mudam entre observações. A mensagem `user` é a nova observação.

### Onde aparece no código
```python
# llm_analysis/nodes.py
_BASE_SYSTEM = """Você é um analista sênior especializado em séries temporais
com 15 anos de experiência. Regras inegociáveis:
1. Nunca invente números fora do contexto fornecido.
2. Responda APENAS com JSON válido."""

messages = [
    SystemMessage(content=_BASE_SYSTEM),   # comportamento fixo
    HumanMessage(content=user_msg),        # dado variável por execução
]
```

---

## Conceito 4 — Temperature e Sampling

### O que é
Parâmetro que controla a aleatoriedade na geração de tokens. Tecnicamente, escala os logits antes do softmax:

- `temperature=0`: determinístico — sempre escolhe o token mais provável
- `temperature=0.7`: alguma variação — útil para texto criativo
- `temperature=1.0`: distribuição original do modelo — máxima variação

### Por que importa no projeto
**Sempre use `temperature=0` para análise de dados.** Você quer que a mesma série, com o mesmo contexto, produza a mesma análise. Reprodutibilidade é um requisito de ciência de dados que não se negocia.

### Analogia TS
É literalmente o **desvio padrão do ruído** ε_t no modelo. `temperature=0` é o modelo sem componente estocástico: `y_t = f(contexto)` puro.

### Onde aparece no código
```python
# parameters.yml
llm:
  temperatura: 0.0  # determinístico para análise

# pipeline.py
llm = ChatOpenAI(model=modelo, temperature=temperatura)
```

---

## Conceito 5 — Structured Output / JSON Mode

### O que é
Mecanismo que força o LLM a retornar exclusivamente JSON válido, com schema definido. Implementado de duas formas:

1. **JSON mode** (OpenAI): garante JSON válido, mas não valida schema
2. **Structured outputs** (OpenAI): garante JSON + schema Pydantic exato
3. **Instrução no prompt** + parser defensivo: compatível com qualquer provider

### Por que importa no projeto
Sem structured output, o pipeline quebra em produção quando o modelo decide incluir um preâmbulo antes do JSON. Com ele, você tem a mesma garantia de tipo que tem com um DataFrame do pandas.

```python
# Sem structured output — frágil:
response.content  # pode ser "Claro! Aqui está a análise:\n```json\n{...}"

# Com instrução + parser defensivo — robusto:
try:
    return json.loads(content)
except:
    match = re.search(r"\{.*\}", content, re.DOTALL)
    return json.loads(match.group())
```

### Analogia TS
É o equivalente ao **schema de um DataFrame**. Você define os tipos e colunas esperadas antes de receber os dados — e rejeita (ou trata) qualquer saída que não conforme.

---

## Conceito 6 — Hallucination (Alucinação)

### O que é
Quando o LLM gera informação plausível mas factualmente incorreta. O modelo não "sabe" que está errado — ele gera o token mais provável dado o contexto, mesmo que esse token seja uma data que não existia ou um número inventado.

### Por que importa no projeto
O `evaluate.py` implementa checks explícitos contra hallucination:

```python
def _check_anomalias_consistentes(output, contexto):
    if contexto.n_anomalias == 0 and "anomalia" in output["resumo_anomalias"].lower():
        # LLM mencionou anomalia que não existe → possível hallucination
        avisos.append("LLM menciona anomalias não detectadas numericamente.")
```

### Analogia TS
É o equivalente ao **overfitting em extrapolação**. O modelo LSTM que performa perfeitamente no treino e gera previsões absurdas fora do domínio está "alucinando" exatamente como o LLM — gerando saídas plausíveis pelo padrão aprendido, mas incorretas para a realidade.

### Como mitigar no projeto
- Enviar contexto quantitativo preciso (não apenas texto vago)
- Instruir explicitamente: "Nunca invente números fora do contexto"
- Validar numericamente toda afirmação quantitativa no `evaluate.py`

---

## Conceito 7 — Latência e Rate Limits

### O que é
- **Latência**: tempo de resposta de uma chamada à API (tipicamente 500ms–5s)
- **TPM (Tokens Per Minute)**: limite de tokens processados por minuto
- **RPM (Requests Per Minute)**: limite de chamadas por minuto

### Por que importa no projeto
O `_chamar_com_retry` implementa **exponential backoff** para lidar com rate limits:

```python
for tentativa in range(1, max_tentativas + 1):
    try:
        response = llm.invoke(messages)
        return resultado, log
    except Exception as e:
        wait = 2 ** tentativa  # 2s, 4s, 8s...
        time.sleep(wait)
```

### Analogia TS
Rate limits são como **throttling em pipelines de dados em tempo real**. Você já lida com Kafka consumer lag ou limites de API de dados — mesma lógica, contexto diferente.

---

## Resumo dos conceitos

| Conceito | `temperature` | Onde no código | Impacto se ignorado |
|---|---|---|---|
| Tokenização | n/a | `features.py: _estimar_tokens` | Custo 10× maior |
| Janela de contexto | n/a | `features.py: ctx_json` | Séries longas falham |
| Roles | n/a | `nodes.py: SystemMessage` | Saídas inconsistentes |
| Temperature | 0.0 | `parameters.yml` | Resultados irreproducíveis |
| Structured output | n/a | `nodes.py: _parsear_json` | Pipeline quebra em produção |
| Hallucination | n/a | `evaluate.py: 5 checks` | Dados incorretos em relatórios |
| Rate limits | n/a | `nodes.py: _chamar_com_retry` | Pipeline falha sem retry |
