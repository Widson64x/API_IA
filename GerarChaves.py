"""Script utilitario para geracao rapida de chaves de seguranca da API IDocs_IA.

Gera as chaves SECRET_KEY e ADMIN_API_KEY com o prefixo fixo 'IDOCS-'
a partir de uma palavra-chave ou senha digitada pelo usuario, podendo atualizar
automaticamente o arquivo .env.
"""

import hmac
import hashlib
import re
from pathlib import Path

CAMINHO_ENV = Path(".env")
PREFIXO_FIXO = "IDOCS-"


def derivar_chave_hash(senha: str, contexto: str) -> str:
    """Deriva uma string hexadecimal a partir da senha e contexto informado.

    Utiliza HMAC-SHA256 para derivar chaves unicas e deterministicas
    para SECRET_KEY e ADMIN_API_KEY no formato IDOCS-<hash>.

    Args:
        senha (str): Palavra-chave ou senha digitada pelo usuario.
        contexto (str): Identificador do tipo de chave (ex: 'SECRET_KEY', 'ADMIN_API_KEY').

    Returns:
        str: Chave gerada no formato IDOCS-<hash_hexadecimal>.
    """
    hash_derivado = hmac.new(
        key=senha.encode("utf-8"),
        msg=contexto.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()

    return f"{PREFIXO_FIXO}{hash_derivado}"


def atualizar_arquivo_env(chave_secret: str, chave_admin: str) -> bool:
    """Atualiza as chaves SECRET_KEY e ADMIN_API_KEY no arquivo .env local.

    Args:
        chave_secret (str): Novo valor para SECRET_KEY.
        chave_admin (str): Novo valor para ADMIN_API_KEY.

    Returns:
        bool: True se o arquivo foi atualizado com sucesso, False caso contrario.
    """
    if not CAMINHO_ENV.exists():
        print("Erro: Arquivo .env nao encontrado no diretorio raiz.")
        return False

    conteudo = CAMINHO_ENV.read_text(encoding="utf-8")

    if "SECRET_KEY=" in conteudo:
        conteudo = re.sub(r"SECRET_KEY=.*", f"SECRET_KEY={chave_secret}", conteudo)
    else:
        conteudo += f"\nSECRET_KEY={chave_secret}\n"

    if "ADMIN_API_KEY=" in conteudo:
        conteudo = re.sub(r"ADMIN_API_KEY=.*", f"ADMIN_API_KEY={chave_admin}", conteudo)
    else:
        conteudo += f"ADMIN_API_KEY={chave_admin}\n"

    CAMINHO_ENV.write_text(conteudo, encoding="utf-8")
    return True


def executar_gerador_chaves() -> None:
    """Executa o fluxo interativo de geracao de chaves e atualizacao do .env."""
    print("=" * 60)
    print("GERADOR DE CHAVES DE SEGURANCA IDOCS")
    print("=" * 60)

    senha = input("Digite a senha ou palavra-chave: ").strip()

    if not senha:
        print("Erro: A senha digitada nao pode estar vazia.")
        return

    chave_secret = derivar_chave_hash(senha, "SECRET_KEY")
    chave_admin = derivar_chave_hash(senha, "ADMIN_API_KEY")

    print("\nChaves geradas:")
    print(f"SECRET_KEY={chave_secret}")
    print(f"ADMIN_API_KEY={chave_admin}")
    print("-" * 60)

    confirmacao = input("Deseja atualizar o arquivo .env automaticamente com estas chaves? (s/n): ").strip().lower()
    if confirmacao in ("s", "sim", "y", "yes"):
        if atualizar_arquivo_env(chave_secret, chave_admin):
            print("\nArquivo .env atualizado com sucesso.")
        else:
            print("\nFalha ao atualizar o arquivo .env.")
    else:
        print("\nOperacao concluida sem alterar o arquivo .env.")


if __name__ == "__main__":
    executar_gerador_chaves()
