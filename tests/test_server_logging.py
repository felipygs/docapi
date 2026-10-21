"""O comando documentado deve exibir os diagnosticos da aplicacao."""
from pathlib import Path
import subprocess
import sys
import unittest


class TestServerLogging(unittest.TestCase):
    def test_comando_server_exibe_logs_info_dos_modulos(self):
        script = '''
import logging
import logging.config
from unittest.mock import patch
import main

def iniciar(*args, **kwargs):
    logging.config.dictConfig(kwargs.get('log_config', main.uvicorn.config.LOGGING_CONFIG))
    logging.getLogger('app.consultar').info('modulo=DASN tentativa=1 codigo=ok')

with patch.object(main.uvicorn, 'run', iniciar):
    main.run_server()
'''
        resultado = subprocess.run(
            [sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn('modulo=DASN tentativa=1 codigo=ok', resultado.stderr)
