"""
settings.py — Configurações do projeto Kedro.

Kedro lê este arquivo para descobrir hooks, config loaders e
outras extensões do framework.
"""

from kedro.config import OmegaConfigLoader
from kedro.framework.hooks import _create_hook_manager  # noqa

# Usa OmegaConf para suporte a interpolação de variáveis nos YAMLs
# Ex: ${oc.env:OPENAI_API_KEY} no credentials.yml
CONFIG_LOADER_CLASS = OmegaConfigLoader

CONFIG_LOADER_ARGS = {
    "base_env": "base",
    "default_run_env": "local",
    # Suporte a variáveis de ambiente com prefixo TS_LLM_
    # Permite sobrescrever qualquer param via env var em CI/CD
    "config_patterns": {
        "parameters": ["parameters*", "parameters*/**", "**/parameters*"],
        "credentials": ["credentials*", "credentials*/**", "**/credentials*"],
        "catalog": ["catalog*", "catalog*/**", "**/catalog*"],
        "logging": ["logging*"],
    },
}

# Hooks personalizados (adicionar aqui conforme necessário)
# from ts_llm_bridge.hooks import ProjectHooks
# HOOKS = (ProjectHooks(),)
HOOKS = ()
