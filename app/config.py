import os
import platform
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)

IS_LINUX = platform.system() == "Linux"

DASN_URL = "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/dasnsimei.app"
OPTANTES_URL = "https://consopt.www8.receita.fazenda.gov.br/consultaoptantes"
CNPJ_URL = "https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/"

NOPECHA_API_KEY = os.environ.get("NOPECHA_API_KEY", "")
NONECAP_API_KEY = os.environ.get("NONECAP_API_KEY", "")

UFS_VALIDAS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
    "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
    "SE", "SP", "TO",
}
