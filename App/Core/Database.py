"""Módulo de conexão e inicialização do banco de dados SQLite.

Responsável por criar as tabelas necessárias para armazenar as chaves de API
e as métricas de consumo de forma persistente e concorrente.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Caminho do banco de dados SQLite
CAMINHO_DB = Path("Data/IDocs.db")

def inicializar_banco() -> None:
    """Cria o arquivo do banco e as tabelas caso não existam."""
    CAMINHO_DB.parent.mkdir(parents=True, exist_ok=True)
    
    with obter_conexao() as conexao:
        cursor = conexao.cursor()
        
        # Ativa o Write-Ahead Logging (WAL) apenas na inicializacao (requer lock exclusivo)
        try:
            cursor.execute("PRAGMA journal_mode = WAL;")
        except sqlite3.OperationalError:
            pass # Ignora se o banco ja estiver travado por outro processo
        
        # Tabela de Clientes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                cliente_id TEXT PRIMARY KEY,
                nome TEXT UNIQUE NOT NULL,
                descricao TEXT,
                hash_api_key TEXT NOT NULL,
                ativo BOOLEAN NOT NULL CHECK (ativo IN (0, 1)),
                criado_em TEXT NOT NULL,
                ultimo_acesso TEXT
            )
        """)
        
        # Tabela de Métricas de Consumo
        # Utilizamos uma chave composta para contar requisições únicas por cliente, rota e modelo.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metricas_consumo (
                cliente_id TEXT NOT NULL,
                rota TEXT NOT NULL,
                modelo_ia TEXT NOT NULL,
                quantidade INTEGER DEFAULT 0,
                PRIMARY KEY (cliente_id, rota, modelo_ia),
                FOREIGN KEY (cliente_id) REFERENCES clientes (cliente_id) ON DELETE CASCADE
            )
        """)
        
        conexao.commit()

@contextmanager
def obter_conexao():
    """Context manager para fornecer conexões seguras ao SQLite.
    
    Yields:
        sqlite3.Connection: Conexão ativa com o banco de dados configurada.
    """
    conexao = sqlite3.connect(
        CAMINHO_DB, 
        check_same_thread=False,
        timeout=10.0
    )
    # Retorna resultados como dicionários em vez de tuplas
    conexao.row_factory = sqlite3.Row
    
    try:
        # Ativa suporte a chaves estrangeiras no SQLite
        conexao.execute("PRAGMA foreign_keys = ON;")
        yield conexao
    finally:
        conexao.close()
