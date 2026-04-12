# Técnicas de LLM Usadas e Por Que Cada Uma

> *Cada técnica é uma escolha de design consciente — não foi usada "porque é comum".*

---

## Técnica 1 — Zero-Shot Prompting

### O que é
Fornecer uma instrução ao LLM sem nenhum exemplo de entrada/saída. O modelo usa apenas o treinamento base para inferir o formato e conteúdo esperados.

### Como é usado no projeto
A análise completa da série (`run_llm_analysis`) usa zero-shot. Você descreve o papel do modelo (system prompt), fornece o contexto TS e especifica o schema JSON de saída.

```
SYSTEM: "Você é analista sênior de séries temporais..."
USER:   "Contexto: {...} | Responda com: {narrativa, tendencia, modelo_recomendado, ...}"
```

### Por que zero-shot aqui
A análise completa tem **alta variabilidade de entrada** (qualquer série mensal, diária, trimestral) e **baixa variabilidade de saída** (schema JSON fixo). O modelo GPT-4 já tem conhecimento técnico suficiente para preencher o schema sem exemplos.

### Quando zero-shot falha
Se o modelo consistentemente errar o formato ou o tom, a próxima etapa é migrar para few-shot (Técnica 2). Neste projeto, o `evaluate.py` detecta esses casos — score baixo indica que zero-shot não está funcionando.

### Trade-off
- ✅ Sem custo de tokens com exemplos (~200 tokens a menos por chamada)
- ✅ Flexível para qualquer tipo de série
- ⚠️ Menos previsível que few-shot para outputs muito específicos

---

## Técnica 2 — Few-Shot Prompting

### O que é
Incluir 2–5 pares de exemplo (entrada → saída desejada) antes da pergunta real. O modelo aprende o padrão pelo exemplo, sem retreino.

### Como é usado no projeto
A investigação de anomalias (`run_anomaly_investigation`) se beneficiaria de few-shot para calibrar o vocabulário de classificação. O projeto implementa a estrutura, e o arquivo `docs/04_tecnicas_llm.md` é o local certo para documentar quando adicionar exemplos.

**Exemplo de few-shot para classificação de anomalias:**
```
--- Exemplo 1 ---
Série: vendas mensais, média=100, std=15
Anomalia: valor=185 em março (+5.7σ)
Resposta: {"classificacao": "outlier_sazonal", "confianca": 0.85,
           "hipotese": "Sazonalidade histórica de verão fora do padrão"}

--- Exemplo 2 ---
Série: temperatura servidor, média=65°C, std=3°C
Anomalia: valor=95°C em terça (+10σ)
Resposta: {"classificacao": "spike_positivo", "confianca": 0.95,
           "hipotese": "Sobrecarga de processamento ou falha de cooling"}
```

### Por que few-shot para anomalias (e não para análise completa)
Anomalias têm **nomenclatura especializada** (`spike_positivo`, `outlier_sazonal`, `mudanca_nivel`) que o modelo pode não usar espontaneamente. Exemplos ancoram o vocabulário. Já a análise completa tem schema JSON explícito suficiente para guiar o zero-shot.

### Trade-off
- ✅ Output muito mais consistente em terminologia técnica
- ✅ Calibra o nível de confiança reportado
- ⚠️ Custo +300-600 tokens por chamada (cada exemplo ~100-200 tokens)
- ⚠️ Exemplos ruins pioram o output — curadoria necessária

---

## Técnica 3 — System Prompt Engineering

### O que é
Design deliberado do prompt de sistema para definir persona, restrições e contrato de output. É a técnica de maior impacto por token — um system prompt bem escrito elimina a necessidade de repetir instruções em cada mensagem.

### Como é usado no projeto
O `_BASE_SYSTEM` em `llm_analysis/nodes.py` tem quatro componentes:

```python
_BASE_SYSTEM = """
[PERSONA]
Você é um analista sênior especializado em séries temporais com 15 anos de experiência.

[RESTRIÇÕES - o mais importante]
1. Nunca invente números, datas ou valores fora do contexto fornecido.
2. Se uma informação não estiver disponível, diga 'dado insuficiente'.
3. Toda afirmação quantitativa deve ser rastreável ao contexto de entrada.

[CONTRATO DE OUTPUT]
4. Responda APENAS com JSON válido — sem markdown, sem texto fora do JSON.

[LOCALIZAÇÃO]
5. Use português do Brasil, linguagem executiva e precisa.
"""
```

### Por que cada componente
- **Persona**: calibra o nível técnico das respostas. Sem ela, o modelo tende a simplificar demais.
- **Restrições**: são as "regras de negócio" do sistema. A mais importante: `"Nunca invente..."` é a principal defesa contra hallucination.
- **Contrato de output**: garante que o parser não vai encontrar markdown ao redor do JSON.
- **Localização**: pt-BR explícito evita respostas em inglês mesmo com contexto em português.

### Variações por pipeline
```python
_SYSTEM_ANALISE = _BASE_SYSTEM                              # análise geral
_SYSTEM_ANOMALIA = _BASE_SYSTEM + "\nEspecialização: classificação causal..."
_SYSTEM_MODELO   = _BASE_SYSTEM + "\nEspecialização: seleção de modelos..."
```

Herança de system prompts: você define o comportamento base uma vez e especializa por caso de uso — exatamente como herança em OOP.

---

## Técnica 4 — Output Estruturado com Schema JSON

### O que é
Fornecer explicitamente o schema JSON esperado como parte do prompt do usuário, forçando o modelo a preencher campos definidos. Versão mais simples que Pydantic structured outputs, mas compatível com qualquer provider.

### Como é usado no projeto
Cada chamada ao LLM inclui o schema de saída esperado:

```python
user_msg = (
    "Analise esta série e responda com EXATAMENTE este JSON:\n"
    "{\n"
    '  "narrativa_executiva": "<3 frases para CFO>",\n'
    '  "tendencia": "<crescente|decrescente|estavel>",\n'
    '  "modelo_recomendado": "<SARIMA|Prophet|XGBoost|LSTM|ETS|Naive>",\n'
    '  "confianca_analise": 0.0\n'
    "}"
)
```

### Por que essa técnica
Três benefícios simultâneos:
1. **Documentação viva**: o schema no prompt é ao mesmo tempo instrução para o modelo e especificação do output para o desenvolvedor
2. **Vocabulário controlado**: `"<SARIMA|Prophet|XGBoost|LSTM|ETS|Naive>"` restringe o espaço de respostas — o modelo não vai inventar "AutoML" ou "deep learning genérico"
3. **Parser simples**: `json.loads(response.content)` funciona diretamente

### Limitação e como o projeto contorna
O modelo pode ignorar parcialmente o schema. Por isso o `evaluate.py` valida os campos obrigatórios com `_check_campos_obrigatorios`. Se `tendencia` está ausente, o score vai a zero.

---

## Técnica 5 — Prompt Chaining (via Kedro)

### O que é
Encadear múltiplas chamadas ao LLM onde a saída de uma alimenta a entrada da próxima. Em vez de uma chamada gigante, divide-se o problema em passos menores.

### Como é usado no projeto
O Kedro **é** o chain manager. Cada pipeline é uma cadeia de chamadas:

```
extract_ts_context → build_prompt_inputs → run_llm_analysis
                                        → run_anomaly_investigation
                                        → run_model_recommendation
                                                   ↓
                                        evaluate_llm_output
                                                   ↓
                                        generate_final_report
```

Cada step é um node independente. O `ts_context` produzido por um node é consumido por vários outros. O `llm_analysis_output` é consumido tanto pelo `evaluate_llm_output` quanto pelo `generate_final_report`.

### Por que chains em vez de uma chamada única
Uma única chamada com "faça tudo ao mesmo tempo" produz:
- Output de maior tamanho (mais caro)
- Menor foco em cada sub-tarefa
- Impossibilidade de reprocessar só uma parte

Com chains via Kedro:
- Você reexecuta só a avaliação sem repagar pelo LLM
- Cada chamada tem foco único → melhor qualidade
- O grafo de dependências é explícito e visualizável com `kedro viz`

### Trade-off
- ✅ Modular, testável, custo controlado por etapa
- ✅ Falha em uma etapa não invalida etapas anteriores (catálogo persiste)
- ⚠️ Latência total maior (3 chamadas em sequência > 1 chamada)
- ⚠️ Contexto não é automaticamente propagado entre chains (você passa explicitamente)

---

## Técnica 6 — Defensive Parsing (Parser Defensivo)

### O que é
Estratégia de parsing que tenta múltiplas abordagens antes de desistir, tratando o output do LLM como input não confiável.

### Como é usado no projeto
```python
def _parsear_json_resposta(content: str) -> dict:
    # Tentativa 1: JSON limpo
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Tentativa 2: JSON dentro de markdown ou texto
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        return json.loads(match.group())

    # Sem fallback — falha explícita é melhor que dado silencioso errado
    raise ValueError(f"Resposta não é JSON válido: {content[:300]}")
```

### Por que não simplesmente `json.loads()`
Em produção, 5–10% das chamadas a LLMs retornam JSON dentro de blocos de markdown mesmo com instrução explícita. `json.loads()` puro falha silenciosamente ou levanta exceção não tratada. O parser defensivo cobre os casos mais comuns sem aceitar qualquer string como "válida".

### Analogia TS
É como ter um `try-except` em torno do `pd.read_csv()` que tenta diferentes encodings e separadores antes de desistir. Você não assume que o dado vai chegar perfeito.

---

## Resumo das técnicas

| Técnica | Node que usa | Razão da escolha | Alternativa se falhar |
|---|---|---|---|
| Zero-shot | `run_llm_analysis` | Schema claro, modelo capaz | Migrar para few-shot |
| Few-shot | `run_anomaly_investigation` | Vocabulário especializado | Mais exemplos / instrução mais rígida |
| System prompt engineering | Todos os nodes LLM | Persona + restrições globais | Refinar restrições por tipo de erro |
| Output estruturado (schema) | Todos os nodes LLM | Vocabulário controlado | Pydantic structured outputs |
| Prompt chaining (Kedro) | Todo o pipeline | Modularidade + reuso de cache | LangGraph para fluxos condicionais |
| Defensive parsing | `_parsear_json_resposta` | Robustez em produção | Pydantic `.model_validate_json()` |
