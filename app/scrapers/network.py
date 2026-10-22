"""Classificacao compartilhada somente das falhas de transporte reconhecidas."""
_NETWORK_ERRORS = ('net::ERR_CONNECTION_', 'net::ERR_NETWORK_',
                   'net::ERR_NAME_NOT_RESOLVED', 'net::ERR_INTERNET_DISCONNECTED')


def erro_rede_transitorio(erro: Exception) -> bool:
    return any(code in str(erro) for code in _NETWORK_ERRORS)
