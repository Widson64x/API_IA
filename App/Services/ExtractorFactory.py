"""Fábrica de extratores para instanciação dinâmica dos serviços baseados no modelo escolhido.

Aplica o padrão de projeto Factory para desacoplar a escolha do provedor de IA
do endpoint HTTP principal e centraliza o catálogo e status de disponibilidade dos modelos.
"""

from typing import Dict, List, Optional, Tuple, Type
from App.Core.Config import configuracao
from App.Schemas.DanfeSchema import InfoModeloIA
from App.Services.BaseExtractorService import DANFEExtratorBase
from App.Services.GeminiExtractorService import ExtratorGemini
from App.Services.OpenAIExtractorService import ExtratorOpenAI
from App.Services.ClaudeExtractorService import ExtratorClaude
from App.Services.OpenRouterExtractorService import ExtratorOpenRouter
from App.Services.GroqExtractorService import ExtratorGroq
from App.Services.MistralExtractorService import ExtratorMistral


class ExtratorFabrica:
    """Fábrica responsável por criar, validar e listar os modelos de extratores de DANFE."""

    _MAPEAMENTO_EXTRATORES: Dict[str, Type[DANFEExtratorBase]] = {
        "gemini": ExtratorGemini,
        "openai": ExtratorOpenAI,
        "claude": ExtratorClaude,
        "openrouter": ExtratorOpenRouter,
        "groq": ExtratorGroq,
        "mistral": ExtratorMistral,
        "pixtral": ExtratorMistral,
    }

    # Catálogo com metadados de cada modelo suportado
    _CATALOGO_MODELOS: List[Dict[str, any]] = [
        {
            "id": "gemini",
            "nome": "Google Gemini 2.0 Flash",
            "provedor": "Google AI Studio",
            "env_key": "GEMINI_API_KEY",
            "descricao": "Processamento multimodal ultrarrápido com visão nativa e alta acurácia para leitura de DANFE/DACTE.",
            "suporta_imagem": True,
            "suporta_pdf": True
        },
        {
            "id": "openai",
            "nome": "OpenAI GPT-4o Mini",
            "provedor": "OpenAI",
            "env_key": "OPENAI_API_KEY",
            "descricao": "Modelo multimodal inteligente e econômico da OpenAI para extração estruturada em JSON.",
            "suporta_imagem": True,
            "suporta_pdf": True
        },
        {
            "id": "claude",
            "nome": "Anthropic Claude 3.5 Sonnet",
            "provedor": "Anthropic",
            "env_key": "ANTHROPIC_API_KEY",
            "descricao": "Alta capacidade de raciocínio e precisão na leitura de documentos fiscais complexos e devoluções.",
            "suporta_imagem": True,
            "suporta_pdf": True
        },
        {
            "id": "groq",
            "nome": "Groq LLaMA 3.3 70B / Vision",
            "provedor": "Groq",
            "env_key": "GROQ_API_KEY",
            "descricao": "Inferência ultrarrápida (LPU) com suporte a visão e alta performance em documentos digitalizados.",
            "suporta_imagem": True,
            "suporta_pdf": True
        },
        {
            "id": "mistral",
            "nome": "Mistral Pixtral 12B",
            "provedor": "Mistral AI",
            "env_key": "MISTRAL_API_KEY",
            "descricao": "Modelo de visão com 128k de contexto da Mistral AI para análise visual direta de notas fiscais.",
            "suporta_imagem": True,
            "suporta_pdf": True
        },
        {
            "id": "openrouter",
            "nome": "OpenRouter Multi-Model",
            "provedor": "OpenRouter",
            "env_key": "OPENROUTER_API_KEY",
            "descricao": "Roteamento inteligente entre modelos abertos com fallback automático e camadas gratuitas.",
            "suporta_imagem": True,
            "suporta_pdf": True
        }
    ]

    @classmethod
    def _obter_chave_configurada(cls, env_key: str) -> Optional[str]:
        """Obtém o valor da chave de ambiente configurada na aplicação."""
        return getattr(configuracao, env_key, None)

    @classmethod
    def modelo_esta_ativo(cls, modelo_ia: str) -> Tuple[bool, str]:
        """Verifica se um modelo está suportado e se sua chave de API está configurada.

        Args:
            modelo_ia (str): Identificador do modelo (ex: 'gemini', 'openai').

        Returns:
            Tuple[bool, str]: (ativo: bool, motivo: str)
        """
        modelo_normalizado = modelo_ia.strip().lower()

        if modelo_normalizado not in cls._MAPEAMENTO_EXTRATORES:
            modelos_validos = ", ".join([m["id"] for m in cls._CATALOGO_MODELOS])
            return False, f"Modelo '{modelo_ia}' não suportado. Modelos disponíveis: {modelos_validos}."

        # Mapeia pixtral para mistral
        id_busca = "mistral" if modelo_normalizado == "pixtral" else modelo_normalizado

        info = next((m for m in cls._CATALOGO_MODELOS if m["id"] == id_busca), None)
        if not info:
            return False, f"Metadados do modelo '{modelo_ia}' não encontrados."

        chave_valor = cls._obter_chave_configurada(info["env_key"])
        if not chave_valor or not str(chave_valor).strip():
            return False, f"O modelo '{info['nome']}' ({info['id']}) está desativado porque a chave {info['env_key']} não foi configurada no servidor."

        return True, "Modelo ativo e operacional."

    @classmethod
    def listar_modelos(cls) -> List[InfoModeloIA]:
        """Retorna o catálogo completo de modelos com seus status de ativação em tempo real.

        Returns:
            List[InfoModeloIA]: Lista estruturada com os modelos disponíveis e seu status operacional.
        """
        resultado = []
        for item in cls._CATALOGO_MODELOS:
            chave_valor = cls._obter_chave_configurada(item["env_key"])
            esta_ativo = bool(chave_valor and str(chave_valor).strip())

            motivo = None if esta_ativo else f"Chave {item['env_key']} não configurada no arquivo .env"

            resultado.append(InfoModeloIA(
                id=item["id"],
                nome=item["nome"],
                provedor=item["provedor"],
                ativo=esta_ativo,
                descricao=item["descricao"],
                suporta_imagem=item["suporta_imagem"],
                suporta_pdf=item["suporta_pdf"],
                motivo_inativo=motivo
            ))
        return resultado

    @classmethod
    def obter_modelo_padrao(cls) -> str:
        """Determina o melhor modelo padrão baseado nos modelos ativos atualmente."""
        # Prioridade de preferência caso estejam ativos
        prioridade = ["gemini", "groq", "openrouter", "openai", "mistral", "claude"]
        for mod_id in prioridade:
            ativo, _ = cls.modelo_esta_ativo(mod_id)
            if ativo:
                return mod_id
        return "gemini"

    @classmethod
    def obter_extrator(cls, modelo_ia: str) -> DANFEExtratorBase:
        """Instancia o extrator correspondente após validar se o modelo é suportado e está ativo.

        Args:
            modelo_ia (str): Nome exato do provedor ('gemini', 'openai', 'claude', 'openrouter', 'groq', 'mistral').

        Returns:
            DANFEExtratorBase: Instância concreta de uma subclasse de DANFEExtratorBase.

        Raises:
            ValueError: Se o modelo solicitado não for suportado ou estiver desativado.
        """
        modelo_normalizado = modelo_ia.strip().lower()

        if modelo_normalizado not in cls._MAPEAMENTO_EXTRATORES:
            modelos_disponiveis = ", ".join([m["id"] for m in cls._CATALOGO_MODELOS])
            raise ValueError(
                f"Provedor de IA '{modelo_ia}' não suportado. Modelos disponíveis: {modelos_disponiveis}"
            )

        # Validação do status de ativação
        ativo, motivo = cls.modelo_esta_ativo(modelo_normalizado)
        if not ativo:
            modelos_ativos = [m.id for m in cls.listar_modelos() if m.ativo]
            str_ativos = ", ".join(modelos_ativos) if modelos_ativos else "Nenhum modelo ativo no momento"
            raise ValueError(
                f"O modelo '{modelo_ia}' está desativado no momento. Motivo: {motivo}. "
                f"Modelos ativos disponíveis para uso: {str_ativos}."
            )

        classe_extrator = cls._MAPEAMENTO_EXTRATORES[modelo_normalizado]

        # Passa o nome específico se o provedor exigir customização
        if issubclass(classe_extrator, ExtratorGemini):
            return classe_extrator(nome_modelo="gemini-2.0-flash")
        elif issubclass(classe_extrator, ExtratorOpenAI):
            return classe_extrator(nome_modelo="gpt-4o-mini")
        elif issubclass(classe_extrator, ExtratorClaude):
            return classe_extrator(nome_modelo="claude-3-5-sonnet-20241022")
        elif issubclass(classe_extrator, ExtratorOpenRouter):
            return classe_extrator(nome_modelo="openrouter")
        elif issubclass(classe_extrator, ExtratorGroq):
            return classe_extrator(nome_modelo="llama-3.3-70b-versatile")
        elif issubclass(classe_extrator, ExtratorMistral):
            return classe_extrator(nome_modelo="pixtral-12b-2409")

        return classe_extrator()

