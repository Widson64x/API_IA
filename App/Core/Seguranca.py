"""Modulo central de seguranca para geracao e validacao de tokens JWT.

Responsavel pela criacao de access/refresh tokens, decodificacao segura,
hashing bcrypt de API Keys e controle de revogacao (blacklist em memoria).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt

from App.Core.Config import configuracao


# Blacklist em memoria para tokens revogados (JTI - JWT ID)
# Em producao com multiplas instancias, substituir por Redis ou banco de dados
_tokens_revogados: set[str] = set()


def gerar_hash_api_key(api_key: str) -> str:
    """Gera um hash bcrypt seguro a partir de uma API Key em texto plano.

    Fatiado em 72 bytes para respeitar o limite maximo do algoritmo bcrypt.

    Args:
        api_key (str): API Key em texto plano para ser hasheada.

    Returns:
        str: Hash bcrypt codificado como string UTF-8.
    """
    bytes_chave = api_key.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    hash_bytes = bcrypt.hashpw(bytes_chave, salt)
    return hash_bytes.decode("utf-8")


def verificar_api_key(api_key_texto_plano: str, hash_armazenado: str) -> bool:
    """Verifica se uma API Key em texto plano corresponde ao hash bcrypt armazenado.

    Args:
        api_key_texto_plano (str): API Key enviada pelo cliente.
        hash_armazenado (str): Hash bcrypt armazenado no sistema.

    Returns:
        bool: True se a key corresponde ao hash, False caso contrario.
    """
    try:
        bytes_chave = api_key_texto_plano.encode("utf-8")[:72]
        bytes_hash = hash_armazenado.encode("utf-8")
        return bcrypt.checkpw(bytes_chave, bytes_hash)
    except (ValueError, TypeError):
        return False


def criar_access_token(dados: dict[str, Any], duracao_minutos: Optional[int] = None) -> str:
    """Gera um JWT access token assinado com claims customizados.

    O token inclui automaticamente os claims 'exp' (expiracao), 'iat' (emissao),
    'tipo' (access) e 'jti' (identificador unico para revogacao).

    Args:
        dados (dict[str, Any]): Claims customizados a incluir no payload (ex: cliente_id, nome).
        duracao_minutos (Optional[int]): Duracao em minutos. Se None, usa o valor do .env.

    Returns:
        str: Token JWT codificado como string.
    """
    import secrets

    payload = dados.copy()
    expiracao = datetime.now(timezone.utc) + timedelta(
        minutes=duracao_minutos or configuracao.ACCESS_TOKEN_DURACAO_MINUTOS
    )

    payload.update({
        "exp": expiracao,
        "iat": datetime.now(timezone.utc),
        "tipo": "access",
        "jti": secrets.token_hex(16)
    })

    return jwt.encode(
        payload,
        configuracao.SECRET_KEY,
        algorithm=configuracao.JWT_ALGORITHM
    )


def criar_refresh_token(dados: dict[str, Any], duracao_horas: Optional[int] = None) -> str:
    """Gera um JWT refresh token com duracao estendida para renovacao de sessao.

    Args:
        dados (dict[str, Any]): Claims customizados (tipicamente apenas o cliente_id).
        duracao_horas (Optional[int]): Duracao em horas. Se None, usa o valor do .env.

    Returns:
        str: Refresh token JWT codificado como string.
    """
    import secrets

    payload = dados.copy()
    expiracao = datetime.now(timezone.utc) + timedelta(
        hours=duracao_horas or configuracao.REFRESH_TOKEN_DURACAO_HORAS
    )

    payload.update({
        "exp": expiracao,
        "iat": datetime.now(timezone.utc),
        "tipo": "refresh",
        "jti": secrets.token_hex(16)
    })

    return jwt.encode(
        payload,
        configuracao.SECRET_KEY,
        algorithm=configuracao.JWT_ALGORITHM
    )


def decodificar_token(token: str) -> dict[str, Any]:
    """Decodifica e valida um token JWT, verificando assinatura, expiracao e revogacao.

    Args:
        token (str): Token JWT codificado.

    Returns:
        dict[str, Any]: Payload decodificado com os claims do token.

    Raises:
        ValueError: Se o token estiver expirado.
        ValueError: Se o token foi revogado (presente na blacklist).
        ValueError: Se o token for invalido ou a assinatura nao corresponder.
    """
    try:
        payload = jwt.decode(
            token,
            configuracao.SECRET_KEY,
            algorithms=[configuracao.JWT_ALGORITHM]
        )
    except ExpiredSignatureError:
        raise ValueError("Token expirado. Realize o refresh ou autentique-se novamente.")
    except JWTError:
        raise ValueError("Token invalido ou assinatura comprometida.")

    # Verifica se o token foi explicitamente revogado via blacklist
    jti = payload.get("jti")
    if jti and token_esta_revogado(jti):
        raise ValueError("Token revogado. Autentique-se novamente.")

    return payload


def revogar_token(jti: str) -> None:
    """Adiciona o identificador unico do token (JTI) a blacklist de revogacao.

    Args:
        jti (str): JWT ID extraido do claim 'jti' do token.
    """
    _tokens_revogados.add(jti)


def token_esta_revogado(jti: str) -> bool:
    """Verifica se um token foi revogado pela sua identificacao unica.

    Args:
        jti (str): JWT ID a verificar.

    Returns:
        bool: True se o token foi revogado, False caso contrario.
    """
    return jti in _tokens_revogados
