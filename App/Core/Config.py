"""Gerenciador centralizado de configurações da aplicação utilizando Pydantic Settings.

Carrega variáveis de ambiente do arquivo .env ou do sistema operacional,
fornecendo acesso seguro e tipado às chaves de API dos provedores de IA.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfiguracaoAplicacao(BaseSettings):
    """Classe responsável pelo carregamento e validação das configurações da aplicação.

    Attributes:
        HOST (str): Endereço IP em que a API escutará as conexões.
        PORT (int): Porta da aplicação.
        DEBUG (bool): Indicador de modo de depuração.
        GEMINI_API_KEY (Optional[str]): Chave de acesso à API do Google Gemini.
        OPENAI_API_KEY (Optional[str]): Chave de acesso à API da OpenAI.
        ANTHROPIC_API_KEY (Optional[str]): Chave de acesso à API da Anthropic Claude.
        DEEPSEEK_API_KEY (Optional[str]): Chave de acesso à API da DeepSeek.
        OPENROUTER_API_KEY (Optional[str]): Chave de acesso à API do OpenRouter.
    """

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None

    DIR_INPUT: Path = Path("Data/input")
    DIR_OUTPUT: Path = Path("Data/output")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def model_post_init(self, __context) -> None:
        """Garante que os diretórios de entrada e saída existam."""
        self.DIR_INPUT.mkdir(parents=True, exist_ok=True)
        self.DIR_OUTPUT.mkdir(parents=True, exist_ok=True)



# Instância única global para reuso na aplicação
configuracao: ConfiguracaoAplicacao = ConfiguracaoAplicacao()
