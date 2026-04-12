# Introdução ao Kedro

> *Para um cientista de dados que já usa sklearn.Pipeline e sabe que código de notebook não vai para produção.*

---

## O que é o Kedro

Kedro é um framework de ML engineering que força boas práticas antes que você precise aprender por experiência dolorosa.

A analogia mais direta: se `sklearn.Pipeline` organiza transformações de features em sequência com contratos de entrada e saída, o Kedro faz o mesmo para **todo o seu projeto** — da ingestão de dados ao relatório final, incluindo chamadas a APIs externas como LLMs.

O que o Kedro resolve:

| Problema sem Kedro | Solução Kedro |
|---|---|
| `df = pd.read_csv("../../data/raw/serie.csv")` espalhado em 12 notebooks | Catálogo central com um nome por dataset |
| API key no código ou em `.env` carregado manualmente | `credentials.yml` com injeção automática |
| "Não sei se esse CSV é o processado ou o bruto" | Camadas de dados nomeadas (`01_raw`, `02_intermediate`...) |
| Reprocessar tudo porque um step quebrou no final | Executar só a etapa que falhou com `kedro run --pipeline=...` |
| Hiperparâmetros no código, difíceis de rastrear | `parameters.yml` versionado no git |
| Teste de node requer mockar leitura de arquivo | Node é função pura — testa como qualquer função Python |

---

## Ambiente de desenvolvimento com uv

`uv` é o gerenciador de pacotes e ambientes virtuais que este projeto usa. É entre 10–100× mais rápido que `pip` e resolve dependências de forma determinística.

### Instalação do uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# ou via pip (se já tiver Python)
pip install uv
```

### Criando o ambiente e instalando as dependências

```bash
# Clonar o projeto
git clone <url-do-repo>
cd ts-llm-bridge

# Criar o .venv e instalar todas as dependências declaradas no pyproject.toml
uv sync

# Para instalar também as dependências de dev (pytest, ruff, etc.)
uv sync --extra dev

# Para instalar o extra de visualização (kedro-viz)
uv sync --extra viz
```

O `uv sync` lê o `pyproject.toml`, resolve o grafo de dependências e cria o `.venv` na raiz do projeto. Você não precisa rodar `pip install` separadamente.

### Ativando o ambiente

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Ou, sem ativar, rode diretamente com `uv run`:

```bash
uv run kedro run
uv run kedro run --pipeline=features_only
uv run python -c "import ts_llm_bridge; print('ok')"
```

### Adicionando dependências

```bash
# Adiciona ao pyproject.toml e instala imediatamente
uv add nome-do-pacote

# Adiciona só para dev
uv add --optional dev nome-do-pacote

# Remove
uv remove nome-do-pacote
```

Não use `pip install` direto no projeto — o `uv` não ficará ciente da mudança e o `pyproject.toml` ficará desatualizado.

### Configurando as credenciais

Antes da primeira execução, preencha o arquivo de credenciais (não está no git):

```bash
# O arquivo já existe com placeholders
cat conf/local/credentials.yml
```

```yaml
openai:
  api_key: "sk-..."        # https://platform.openai.com/api-keys

anthropic:
  api_key: "sk-ant-..."    # https://console.anthropic.com/
```

Edite com sua chave real. Só é necessária a chave do provider configurado em `conf/base/parameters.yml` (`llm.provider`).

### Verificando a instalação

```bash
# Deve listar os pipelines disponíveis sem erro
kedro run --pipeline=features_only

# Deve mostrar o catálogo configurado
kedro catalog list
```

Se o `kedro` não for encontrado, verifique se o `.venv` está ativado ou use `uv run kedro`.

---

## Os quatro conceitos centrais

### 1. Node

Um **node** é uma função Python com entrada e saída declaradas. Nada mais.

```python
from kedro.pipeline import node

node(
    func=extract_ts_context,        # função Python normal
    inputs=["clean_series",         # nomes no catálogo
            "params:feature_extraction"],
    outputs="ts_context",           # nome no catálogo
    name="extract_ts_context",
)
```

A função em si não sabe nada sobre Kedro:

```python
def extract_ts_context(clean_df: pd.DataFrame, parameters: dict) -> dict:
    # lógica pura — sem I/O, sem leitura de arquivo
    ...
    return contexto
```

**Consequência prática:** você testa `extract_ts_context(df, params)` diretamente, sem fixtures complexas. Kedro só aparece na hora de conectar nodes em pipeline.

---

### 2. Pipeline

Uma **pipeline** é um grafo de nodes. O Kedro resolve a ordem de execução automaticamente a partir das dependências declaradas.

```python
from kedro.pipeline import pipeline

def create_pipeline() -> Pipeline:
    return pipeline([
        node(func=generate_synthetic_series, inputs="params:synthetic_data",  outputs="synthetic_series"),
        node(func=validate_and_clean_series, inputs=["synthetic_series", "params:feature_extraction"], outputs="clean_series"),
        node(func=extract_ts_context,        inputs=["clean_series", "params:feature_extraction"],    outputs="ts_context"),
        node(func=build_prompt_inputs,       inputs=["ts_context", "params:llm"],                    outputs="prompt_inputs"),
    ])
```

O Kedro infere o grafo: `synthetic_series` é output do primeiro node e input do segundo, então o primeiro sempre roda antes. Você não gerencia ordem manualmente.

---

### 3. Catálogo de dados

O **catálogo** (`conf/base/catalog.yml`) mapeia nomes simbólicos a arquivos reais. Quando um node retorna `"ts_context"`, o Kedro sabe onde salvar. Quando outro node precisa de `"ts_context"`, o Kedro sabe onde carregar.

```yaml
# conf/base/catalog.yml

clean_series:
  type: pandas.CSVDataset
  filepath: data/02_intermediate/clean_series.csv
  save_args:
    index: true

ts_context:
  type: kedro_datasets.json.JSONDataset
  filepath: data/03_primary/ts_context.json

llm_analysis_output:
  type: kedro_datasets.json.JSONDataset
  filepath: data/04_feature/llm_analysis_output.json
```

**O que isso resolve:** se você mudar `filepath` de local para S3, nenhum código de node muda. Se você mudar o formato de CSV para Parquet, nenhum código de node muda. A troca é em um YAML.

**Camadas convencionais do Kedro:**

| Camada | Pasta | Conteúdo |
|---|---|---|
| `01_raw` | `data/01_raw/` | Dados brutos — nunca modificar |
| `02_intermediate` | `data/02_intermediate/` | Dados limpos e validados |
| `03_primary` | `data/03_primary/` | Features extraídas |
| `04_feature` | `data/04_feature/` | Outputs de modelos/APIs |
| `08_reporting` | `data/08_reporting/` | Relatórios e logs finais |

---

### 4. Parâmetros e credenciais

**Parâmetros** (`conf/base/parameters.yml`) são configuração que vai no git:

```yaml
llm:
  provider: "openai"
  modelo: "gpt-4o-mini"
  temperatura: 0.0
  max_tokens: 1000
```

Um node os recebe com o prefixo `params:`:

```python
node(
    func=run_llm_analysis,
    inputs=["prompt_inputs", "params:llm"],  # ← injeta o subdict "llm"
    outputs="llm_analysis_output",
)
```

**Credenciais** (`conf/local/credentials.yml`) ficam **fora do git** (já no `.gitignore`):

```yaml
openai:
  api_key: "sk-..."

anthropic:
  api_key: "sk-ant-..."
```

Um node os recebe com o prefixo `credentials:`:

```python
inputs=["prompt_inputs", "params:llm", "credentials:openai"]
```

Separação clara: o que é configuração (versionável) vs. o que é segredo (nunca no repositório).

---

## Estrutura de arquivos

```
src/ts_llm_bridge/
├── __init__.py
├── settings.py              ← config loader, lista de hooks
├── hooks.py                 ← lógica cross-cutting (timing, custo)
├── pipeline_registry.py     ← registra todos os pipelines nomeados
└── pipelines/
    ├── feature_extraction/
    │   ├── nodes.py         ← funções puras (a lógica de negócio)
    │   └── pipeline.py      ← conecta os nodes com o catálogo
    ├── llm_analysis/
    │   ├── nodes.py
    │   └── pipeline.py
    └── evaluation/
        ├── nodes.py
        └── pipeline.py
```

`pipeline_registry.py` é o ponto de entrada que o Kedro usa para descobrir pipelines:

```python
def register_pipelines() -> dict[str, Pipeline]:
    return {
        "__default__": feature_pipeline + llm_pipeline + eval_pipeline,
        "features_only": feature_pipeline,
        "llm_analysis": llm_pipeline,
        "evaluation": eval_pipeline,
    }
```

Cada chave do dict vira um `--pipeline=` disponível na CLI.

---

## Como executar

```bash
# Pipeline completo (chave "__default__")
kedro run

# Pipeline específico
kedro run --pipeline=features_only

# Node específico
kedro run --node=extract_ts_context

# Do node X até o final (sem reprocessar o que já está no catálogo)
kedro run --from-nodes=evaluate_llm_output

# Com parâmetro sobrescrito via CLI
kedro run --params="llm.modelo=gpt-4o"

# Ver o grafo de dependências (requer kedro-viz)
kedro viz
```

**O fluxo mais comum durante desenvolvimento:**

```bash
# 1. Primeira execução completa
kedro run

# 2. Você ajusta o prompt em llm_analysis/nodes.py
# 3. Reprocessa só o que mudou — features já estão no catálogo
kedro run --pipeline=llm_analysis
kedro run --pipeline=evaluation
```

Você não repaga pelo `extract_ts_context` porque o `ts_context.json` já existe em disco.

---

## Hooks

Hooks são o mecanismo do Kedro para **cross-cutting concerns** — lógica que roda em torno de nodes sem poluir a lógica de negócio.

Exemplos do projeto:

```python
class NodeTimingHook:
    @hook_impl
    def before_node_run(self, node, ...):
        self._start_times[node.name] = time.monotonic()

    @hook_impl
    def after_node_run(self, node, ...):
        elapsed = time.monotonic() - self._start_times[node.name]
        logger.info(f"✓ {node.name} ({elapsed*1000:.0f}ms)")

class LLMCostHook:
    @hook_impl
    def after_pipeline_run(self, ...):
        cost_report = catalog.load("cost_report")
        logger.info(f"Custo total: ${cost_report['custo_total_usd']:.6f}")
```

Para ativar, registre em `settings.py`:

```python
from ts_llm_bridge.hooks import NodeTimingHook, LLMCostHook

HOOKS = (NodeTimingHook(), LLMCostHook())
```

Cada node passa a ser cronometrado automaticamente, sem nenhuma mudança no código dos nodes.

---

## Testando nodes

Como nodes são funções puras, o teste é direto:

```python
# tests/pipelines/test_feature_extraction.py
from ts_llm_bridge.pipelines.feature_extraction.nodes import extract_ts_context

def test_extract_ts_context_detecta_tendencia_crescente():
    df = pd.DataFrame({"valor": [10, 20, 30, 40, 50] * 12}, index=pd.date_range("2020", periods=60, freq="ME"))
    params = {"coluna_valor": "valor", "limiar_anomalia": 2.8, "max_anomalias": 5, "serie_nome": "teste", "validar_frequencia": True}

    resultado = extract_ts_context(df, params)

    assert resultado["tendencia"] == "crescente"
    assert resultado["n_pontos"] == 60
```

Nenhum mock de catálogo, nenhuma fixture de Kedro. A função recebe DataFrame, retorna dict.

---

## Kedro Viz

O `kedro viz` gera um grafo interativo do pipeline no browser:

```bash
pip install kedro-viz   # ou: uv pip install kedro-viz
kedro viz
```

Você vê cada node, cada dataset, as dependências, e pode clicar em cada elemento para ver parâmetros e metadados. Útil para:
- Apresentar o pipeline para stakeholders
- Debugar dependências inesperadas
- Entender projetos de outros times

---

## Referência rápida de comandos

```bash
kedro run                                    # pipeline padrão
kedro run --pipeline=<nome>                  # pipeline específico
kedro run --node=<nome>                      # node único
kedro run --from-nodes=<nome>                # do node até o final
kedro run --to-nodes=<nome>                  # do início até o node
kedro run --params="chave=valor"             # sobrescreve parâmetro
kedro run --env=staging                      # usa conf/staging/ em vez de conf/local/
kedro viz                                    # abre grafo no browser
kedro catalog list                           # lista todos os datasets do catálogo
kedro catalog describe <nome>                # detalhes de um dataset
kedro ipython                                # Jupyter/IPython com catálogo disponível
```

No shell IPython do `kedro ipython`, você tem acesso ao catálogo diretamente:

```python
# kedro ipython
ts_context = catalog.load("ts_context")
clean_series = catalog.load("clean_series")
catalog.save("ts_context", meu_dict)
```

Útil para inspeção interativa sem precisar rodar o pipeline completo.
