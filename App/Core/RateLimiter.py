"""Rate limiter in-memory com algoritmo de sliding window.

Controla a quantidade de requisicoes por cliente dentro de uma janela
temporal deslizante de 60 segundos. Retorna headers padrao HTTP de rate limit.
Em producao com multiplas instancias, substituir por Redis (ex: redis-py + sliding window lua script).
"""

import time
from collections import defaultdict
from threading import Lock

from App.Core.Config import configuracao


# Armazena timestamps das requisicoes por cliente_id
_registros_requisicoes: dict[str, list[float]] = defaultdict(list)

# Lock para acesso thread-safe
_lock_registros = Lock()

# Janela temporal em segundos (1 minuto)
_JANELA_SEGUNDOS: int = 60


def verificar_limite(cliente_id: str) -> dict:
    """Verifica o status de rate limit para um cliente e registra a requisicao.

    Remove requisicoes fora da janela temporal antes de contar.
    Se o limite foi excedido, levanta ValueError com detalhes.

    Args:
        cliente_id (str): Identificador unico do cliente autenticado.

    Returns:
        dict: Headers de rate limit para inclusao na resposta HTTP.
            - limite (int): Total de requisicoes permitidas por janela.
            - restante (int): Requisicoes restantes na janela atual.
            - reset (int): Timestamp UNIX de quando a janela reseta.

    Raises:
        ValueError: Se o cliente excedeu o limite de requisicoes por minuto.
    """
    limite = configuracao.RATE_LIMIT_REQUISICOES_POR_MINUTO
    agora = time.time()
    inicio_janela = agora - _JANELA_SEGUNDOS

    with _lock_registros:
        # Remove registros fora da janela (sliding window cleanup)
        _registros_requisicoes[cliente_id] = [
            ts for ts in _registros_requisicoes[cliente_id]
            if ts > inicio_janela
        ]

        contagem_atual = len(_registros_requisicoes[cliente_id])

        if contagem_atual >= limite:
            # Calcula quando a primeira requisicao da janela vai expirar
            primeiro_registro = _registros_requisicoes[cliente_id][0]
            tempo_reset = int(primeiro_registro + _JANELA_SEGUNDOS)

            raise ValueError(
                f"Rate limit excedido. Limite: {limite} requisicoes por minuto. "
                f"Tente novamente em {tempo_reset - int(agora)} segundos."
            )

        # Registra a requisicao atual
        _registros_requisicoes[cliente_id].append(agora)
        restante = limite - len(_registros_requisicoes[cliente_id])

    return {
        "limite": limite,
        "restante": restante,
        "reset": int(agora + _JANELA_SEGUNDOS)
    }


def obter_headers_rate_limit(info_limite: dict) -> dict[str, str]:
    """Converte as informacoes de rate limit em headers HTTP padrao.

    Args:
        info_limite (dict): Dicionario retornado por verificar_limite().

    Returns:
        dict[str, str]: Headers formatados para inclusao na resposta HTTP.
    """
    return {
        "X-RateLimit-Limit": str(info_limite["limite"]),
        "X-RateLimit-Remaining": str(info_limite["restante"]),
        "X-RateLimit-Reset": str(info_limite["reset"])
    }
