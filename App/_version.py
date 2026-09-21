"""Versão única da aplicação.

Este módulo é a fonte oficial da versão exibida no OpenAPI, no healthcheck e
pelos consumidores Python do pacote ``App``.
"""

__version__ = "2.0.1"
VERSAO = __version__
VERSAO_TUPLA = tuple(int(parte) for parte in __version__.split("."))
