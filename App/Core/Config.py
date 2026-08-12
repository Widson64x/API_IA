"""Gerenciador centralizado de configuracoes da aplicacao utilizando Pydantic Settings.

Carrega variaveis de ambiente do arquivo .env ou do sistema operacional,
fornecendo acesso seguro e tipado as chaves de API dos provedores de IA
e parametros de seguranca JWT.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfiguracaoAplicacao(BaseSettings):
    """Classe responsavel pelo carregamento e validacao das configuracoes da aplicacao.

    Attributes:
        HOST (str): Endereco IP em que a API escutara as conexoes.
        PORT (int): Porta da aplicacao.
        DEBUG (bool): Indicador de modo de depuracao.
        GEMINI_API_KEY (Optional[str]): Chave de acesso a API do Google Gemini.
        OPENAI_API_KEY (Optional[str]): Chave de acesso a API da OpenAI.
        ANTHROPIC_API_KEY (Optional[str]): Chave de acesso a API da Anthropic Claude.
        DEEPSEEK_API_KEY (Optional[str]): Chave de acesso a API da DeepSeek.
        OPENROUTER_API_KEY (Optional[str]): Chave de acesso a API do OpenRouter.
        SECRET_KEY (str): Chave criptografica para assinatura dos tokens JWT.
        JWT_ALGORITHM (str): Algoritmo de assinatura JWT (padrao HS256).
        ACCESS_TOKEN_DURACAO_MINUTOS (int): Tempo de vida do access token em minutos.
        REFRESH_TOKEN_DURACAO_HORAS (int): Tempo de vida do refresh token em horas.
        RATE_LIMIT_REQUISICOES_POR_MINUTO (int): Limite de requisicoes por minuto por cliente.
        ADMIN_API_KEY (str): Chave de administracao para endpoints de gestao de clientes.
    """

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # Seguranca e Autenticacao JWT
    SECRET_KEY: str = "TROQUE_ESTA_CHAVE_EM_PRODUCAO"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_DURACAO_MINUTOS: int = 30
    REFRESH_TOKEN_DURACAO_HORAS: int = 24
    RATE_LIMIT_REQUISICOES_POR_MINUTO: int = 60
    ADMIN_API_KEY: str = "TROQUE_ESTA_CHAVE_EM_PRODUCAO"

    DIR_INPUT: Path = Path("Data/input")
    DIR_OUTPUT: Path = Path("Data/output")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def model_post_init(self, __context) -> None:
        """Garante que os diretorios de entrada e saida existam."""
        self.DIR_INPUT.mkdir(parents=True, exist_ok=True)
        self.DIR_OUTPUT.mkdir(parents=True, exist_ok=True)



# Instancia unica global para reuso na aplicacao
configuracao: ConfiguracaoAplicacao = ConfiguracaoAplicacao()

