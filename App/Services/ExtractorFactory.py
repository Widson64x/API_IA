"""Fábrica de extratores para instanciação dinâmica dos serviços baseados no modelo escolhido.

Aplica o padrão de projeto Factory para desacoplar a escolha do provedor de IA
do endpoint HTTP principal.
"""

from typing import Dict, Type
from App.Services.BaseExtractorService import DANFEExtratorBase
from App.Services.GeminiExtractorService import ExtratorGemini
from App.Services.OpenAIExtractorService import ExtratorOpenAI
from App.Services.ClaudeExtractorService import ExtratorClaude
from App.Services.DeepSeekExtractorService import ExtratorDeepSeek


class ExtratorFabrica:
    """Fábrica responsável por criar e retornar instâncias de extratores de DANFE."""

    _MAPEAMENTO_EXTRATORES: Dict[str, Type[DANFEExtratorBase]] = {
        "gemini-flash": ExtratorGemini,
        "gemini-2.0-flash": ExtratorGemini,
        "gemini-1.5-flash": ExtratorGemini,
        "gpt-4o-mini": ExtratorOpenAI,
        "gpt-4o": ExtratorOpenAI,
        "openai": ExtratorOpenAI,
        "claude-3-5-sonnet": ExtratorClaude,
        "claude": ExtratorClaude,
        "deepseek-chat": ExtratorDeepSeek,
        "deepseek": ExtratorDeepSeek,
        "openrouter-free": ExtratorDeepSeek,
        "openrouter": ExtratorDeepSeek,
    }

    @classmethod
    def obter_extrator(cls, modelo_ia: str) -> DANFEExtratorBase:
        """Instancia o extrator correspondente ao identificador do modelo informado.

        Args:
            modelo_ia (str): Nome ou alias do modelo de IA (ex: 'gemini-flash', 'gpt-4o-mini').

        Returns:
            DANFEExtratorBase: Instância concreta de uma subclasse de DANFEExtratorBase.

        Raises:
            ValueError: Se o modelo solicitado não for suportado.
        """
        modelo_normalizado = modelo_ia.strip().lower()

        if modelo_normalizado not in cls._MAPEAMENTO_EXTRATORES:
            modelos_disponiveis = ", ".join(cls._MAPEAMENTO_EXTRATORES.keys())
            raise ValueError(
                f"Modelo de IA '{modelo_ia}' não suportado. Modelos disponíveis: {modelos_disponiveis}"
            )

        classe_extrator = cls._MAPEAMENTO_EXTRATORES[modelo_normalizado]

        # Passa o nome específico se o modelo exigir customização
        if issubclass(classe_extrator, ExtratorGemini):
            nome_modelo_real = "gemini-2.0-flash" if "2.0" in modelo_normalizado else "gemini-1.5-flash"
            return classe_extrator(nome_modelo=nome_modelo_real)
        elif issubclass(classe_extrator, ExtratorOpenAI):
            nome_modelo_real = "gpt-4o" if modelo_normalizado == "gpt-4o" else "gpt-4o-mini"
            return classe_extrator(nome_modelo=nome_modelo_real)
        elif issubclass(classe_extrator, ExtratorClaude):
            return classe_extrator(nome_modelo="claude-3-5-sonnet-20241022")
        elif issubclass(classe_extrator, ExtratorDeepSeek):
            return classe_extrator(nome_modelo=modelo_normalizado)

        return classe_extrator()
