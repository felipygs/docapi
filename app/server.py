"""Inicialização do servidor e configuração dos logs."""
import sys
from copy import deepcopy
import uvicorn


def run_server():
    port = 8000
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    log_config = deepcopy(uvicorn.config.LOGGING_CONFIG)
    log_config['formatters']['default']['fmt'] = '%(asctime)s %(levelprefix)s %(name)s %(message)s'
    log_config['loggers']['app'] = {
        'handlers': ['default'], 'level': 'INFO', 'propagate': False,
    }

    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_config=log_config,
    )
