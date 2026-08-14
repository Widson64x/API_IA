"""Gerenciador de Métricas e Consumo.

Camada de persistência local (SQLite) para contabilidade de uso da API.
Armazena o consumo por cliente, incluindo rotas acessadas e modelos de IA utilizados.
"""

from App.Core.Database import obter_conexao


def registrar_consumo(cliente_id: str, rota: str, modelo_ia: str = "padrao") -> None:
    """Registra uma execucao de sucesso atrelada a um cliente.

    Atualiza a contagem total, por rota e por modelo de IA utilizado.
    Esta funcao deve ser chamada preferencialmente como uma BackgroundTask no FastAPI.

    Args:
        cliente_id (str): Identificador unico do cliente autenticado.
        rota (str): Endpoint consumido (ex: '/api/v1/danfe/extrair').
        modelo_ia (str, optional): Modelo da IA utilizado. Defaults to "padrao".
    """
    with obter_conexao() as conexao:
        cursor = conexao.cursor()
        
        # O SQLite possui suporte a UPSERT nativo com ON CONFLICT
        # A primary key da tabela é composta (cliente_id, rota, modelo_ia)
        cursor.execute(
            """
            INSERT INTO metricas_consumo (cliente_id, rota, modelo_ia, quantidade)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(cliente_id, rota, modelo_ia)
            DO UPDATE SET quantidade = quantidade + 1;
            """,
            (cliente_id, rota, modelo_ia)
        )
        
        conexao.commit()


def obter_metricas() -> dict:
    """Retorna o consolidado de consumo atual do sistema lendo do SQLite.

    Reconstroi o formato de dicionario aninhado que era usado no JSON
    para manter compatibilidade com a rota existente.

    Returns:
        dict: Dicionario completo contendo as estatisticas de todos os clientes.
    """
    metricas = {}
    
    with obter_conexao() as conexao:
        cursor = conexao.cursor()
        cursor.execute("SELECT cliente_id, rota, modelo_ia, quantidade FROM metricas_consumo")
        linhas = cursor.fetchall()
        
        for linha in linhas:
            cid = linha["cliente_id"]
            if cid not in metricas:
                metricas[cid] = {
                    "total_requisicoes": 0,
                    "rotas": {},
                    "modelos": {}
                }
            
            qtd = linha["quantidade"]
            
            # Incrementa metricas gerais
            metricas[cid]["total_requisicoes"] += qtd
            
            # Incrementa rotas
            rota = linha["rota"]
            metricas[cid]["rotas"][rota] = metricas[cid]["rotas"].get(rota, 0) + qtd
            
            # Incrementa modelos
            modelo = linha["modelo_ia"]
            metricas[cid]["modelos"][modelo] = metricas[cid]["modelos"].get(modelo, 0) + qtd
            
    return metricas


def obter_consumo_cliente(cliente_id: str) -> dict:
    """Retorna o consolidado de consumo de um cliente específico lendo do SQLite.

    Args:
        cliente_id (str): Identificador único do cliente.

    Returns:
        dict: Dicionário contendo total de requisições, detalhamento por modelo e por rota.
    """
    consumo = {
        "cliente_id": cliente_id,
        "total_requisicoes": 0,
        "rotas": {},
        "modelos": {}
    }

    with obter_conexao() as conexao:
        cursor = conexao.cursor()
        cursor.execute(
            "SELECT rota, modelo_ia, quantidade FROM metricas_consumo WHERE cliente_id = ?",
            (cliente_id,)
        )
        linhas = cursor.fetchall()

        for linha in linhas:
            qtd = linha["quantidade"]
            consumo["total_requisicoes"] += qtd

            rota = linha["rota"]
            consumo["rotas"][rota] = consumo["rotas"].get(rota, 0) + qtd

            modelo = linha["modelo_ia"]
            consumo["modelos"][modelo] = consumo["modelos"].get(modelo, 0) + qtd

    return consumo

