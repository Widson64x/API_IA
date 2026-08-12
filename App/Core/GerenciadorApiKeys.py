"""Gerenciador de API Keys e clientes da aplicação.

Camada de persistência local (SQLite) para CRUD de clientes autenticados.
Armazena apenas hashes bcrypt das API Keys — nunca o texto plano.
"""

import secrets
from datetime import datetime, timezone
from typing import Optional

from App.Core.Config import configuracao
from App.Core.Seguranca import gerar_hash_api_key, verificar_api_key
from App.Core.Database import obter_conexao


def registrar_cliente(nome: str, descricao: str = "") -> dict:
    """Registra um novo cliente e gera uma API Key única.

    A API Key é retornada em texto plano APENAS nesta operação.
    Internamente, apenas o hash bcrypt é armazenado.

    Args:
        nome (str): Nome identificador do cliente (ex: 'Sistema ERP Matriz').
        descricao (str): Descrição opcional do propósito do cliente.

    Returns:
        dict: Dados do cliente criado, incluindo a API Key em texto plano (única exibição).

    Raises:
        ValueError: Se já existir um cliente com o mesmo nome.
    """
    cliente_id = f"cli_{secrets.token_hex(12)}"
    api_key_texto_plano = f"idocs_{secrets.token_hex(24)}"
    hash_api_key = gerar_hash_api_key(api_key_texto_plano)
    agora = datetime.now(timezone.utc).isoformat()

    try:
        with obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute(
                """
                INSERT INTO clientes (cliente_id, nome, descricao, hash_api_key, ativo, criado_em, ultimo_acesso)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (cliente_id, nome, descricao, hash_api_key, 1, agora, None)
            )
            conexao.commit()
    except Exception as e:
        # SQLite levanta erro de integridade em chaves duplicadas (ex: nome UNIQUE)
        if "UNIQUE constraint failed" in str(e):
            raise ValueError(f"Ja existe um cliente cadastrado com o nome '{nome}'.")
        raise e

    return {
        "cliente_id": cliente_id,
        "nome": nome,
        "descricao": descricao,
        "api_key": api_key_texto_plano,
        "criado_em": agora
    }


def autenticar_por_api_key(api_key: str) -> Optional[dict]:
    """Valida uma API Key e retorna os dados do cliente autenticado.

    Compara a key fornecida contra todos os hashes armazenados.
    Atualiza o campo 'ultimo_acesso' em caso de sucesso.

    Args:
        api_key (str): API Key em texto plano enviada pelo cliente.

    Returns:
        Optional[dict]: Dados do cliente (sem hash) se autenticado, None caso contrário.
    """
    with obter_conexao() as conexao:
        cursor = conexao.cursor()
        
        # Como precisamos comparar hash bcrypt, devemos buscar todos os clientes ativos
        # (Em bancos maiores, a API Key normalmente tem um prefixo ou ID publico para lookup direto)
        cursor.execute("SELECT * FROM clientes WHERE ativo = 1")
        clientes = cursor.fetchall()
        
        for linha in clientes:
            if verificar_api_key(api_key, linha["hash_api_key"]):
                # Registra o último acesso
                agora = datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    "UPDATE clientes SET ultimo_acesso = ? WHERE cliente_id = ?",
                    (agora, linha["cliente_id"])
                )
                conexao.commit()
                
                return {
                    "cliente_id": linha["cliente_id"],
                    "nome": linha["nome"],
                    "descricao": linha["descricao"],
                    "ativo": bool(linha["ativo"]),
                    "criado_em": linha["criado_em"],
                    "ultimo_acesso": agora
                }

    return None


def listar_clientes() -> list[dict]:
    """Lista todos os clientes cadastrados sem expor os hashes das API Keys.

    Returns:
        list[dict]: Lista de dicionários com os dados públicos de cada cliente.
    """
    resultado = []
    with obter_conexao() as conexao:
        cursor = conexao.cursor()
        cursor.execute("SELECT cliente_id, nome, descricao, ativo, criado_em, ultimo_acesso FROM clientes")
        linhas = cursor.fetchall()
        
        for linha in linhas:
            resultado.append({
                "cliente_id": linha["cliente_id"],
                "nome": linha["nome"],
                "descricao": linha["descricao"],
                "ativo": bool(linha["ativo"]),
                "criado_em": linha["criado_em"],
                "ultimo_acesso": linha["ultimo_acesso"]
            })

    return resultado


def revogar_cliente(cliente_id: str) -> bool:
    """Desativa um cliente, impedindo-o de gerar novos tokens.

    Args:
        cliente_id (str): Identificador único do cliente.

    Returns:
        bool: True se o cliente foi desativado, False se não encontrado.
    """
    with obter_conexao() as conexao:
        cursor = conexao.cursor()
        
        # Verifica se existe
        cursor.execute("SELECT 1 FROM clientes WHERE cliente_id = ?", (cliente_id,))
        if not cursor.fetchone():
            return False
            
        cursor.execute("UPDATE clientes SET ativo = 0 WHERE cliente_id = ?", (cliente_id,))
        conexao.commit()

    return True
