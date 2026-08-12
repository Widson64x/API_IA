"""Fábrica de extratores para instanciação dinâmica dos serviços baseados no modelo escolhido.

Aplica o padrão de projeto Factory para desacoplar a escolha do provedor de IA
do endpoint HTTP principal.
"""

from typing import Dict, Type
from App.Services.BaseExtractorService import DANFEExtratorBase
from App.Services.GeminiExtractorService import ExtratorGemini
from App.Services.OpenAIExtractorService import ExtratorOpenAI
from App.Services.ClaudeExtractorService import ExtratorClaude
from App.Services.OpenRouterExtractorService import ExtratorOpenRouter
from App.Services.GroqExtractorService import ExtratorGroq


class ExtratorFabrica:
    """Fábrica responsável por criar e retornar instâncias de extratores de DANFE."""

    _MAPEAMENTO_EXTRATORES: Dict[str, Type[DANFEExtratorBase]] = {
        "gemini": ExtratorGemini,
        "openai": ExtratorOpenAI,
        "claude": ExtratorClaude,
        "openrouter": ExtratorOpenRouter,
        "groq": ExtratorGroq,
    }

    @classmethod
    def obter_extrator(cls, modelo_ia: str) -> DANFEExtratorBase:
        """Instancia o extrator correspondente ao identificador do modelo informado.

        Args:
            modelo_ia (str): Nome exato do provedor ('gemini', 'openai', 'claude', 'openrouter', 'groq').

        Returns:
            DANFEExtratorBase: Instância concreta de uma subclasse de DANFEExtratorBase.

        Raises:
            ValueError: Se o modelo solicitado não for suportado.
        """
        modelo_normalizado = modelo_ia.strip().lower()

        if modelo_normalizado not in cls._MAPEAMENTO_EXTRATORES:
            modelos_disponiveis = ", ".join(cls._MAPEAMENTO_EXTRATORES.keys())
            raise ValueError(
                f"Provedor de IA '{modelo_ia}' não suportado. Provedores disponíveis: {modelos_disponiveis}"
            )

        classe_extrator = cls._MAPEAMENTO_EXTRATORES[modelo_normalizado]

        # Passa o nome específico se o provedor exigir customização
        if issubclass(classe_extrator, ExtratorGemini):
            return classe_extrator(nome_modelo="gemini-1.5-flash")
        elif issubclass(classe_extrator, ExtratorOpenAI):
            return classe_extrator(nome_modelo="gpt-4o-mini")
        elif issubclass(classe_extrator, ExtratorClaude):
            return classe_extrator(nome_modelo="claude-3-5-sonnet-20241022")
        elif issubclass(classe_extrator, ExtratorOpenRouter):
            return classe_extrator(nome_modelo="openrouter")
        elif issubclass(classe_extrator, ExtratorGroq):
            return classe_extrator(nome_modelo="qwen/qwen3.6-27b")

        return classe_extrator()
