def eliane():
    """Alvo de design.md, não captura atual da Receita."""
    return {
        "cnpj_consultado": "43996591000101",
        "cnpj_matriz": "43996591000101",
        "nome_empresarial": "ELIANE S MURTA CONSULTORIO ODONTOLOGICO",
        "consultado_em": "2026-10-15T18:08:45",
        "abrange_todos_estabelecimentos": True,
        "simples_nacional": {
            "optante": True,
            "situacao": "Optante pelo Simples Nacional desde 01/01/2026",
            "data_desde": "2026-01-01",
            "periodos_anteriores": [
                {"data_inicial": inicio, "data_final": fim,
                 "detalhamento": "Excluída por Ato Administrativo praticado pela Receita Federal do Brasil"}
                for inicio, fim in (("2025-01-01", "2025-12-31"),
                                    ("2024-01-01", "2024-12-31"),
                                    ("2021-10-25", "2023-12-31"))
            ],
            "eventos_futuros": [{"descricao": "Exclusão de Ofício - Débitos", "data_efeito": "2027-01-01"}],
        },
        "simei": {
            "enquadrado": False, "situacao": "NÃO enquadrado no SIMEI",
            "data_desde": None, "periodos_anteriores": [], "eventos_futuros": [],
        },
        "mei_transportador": {"possui_periodos": False},
        "alertas": [],
    }


def conteudo():
    # Conteúdo preenchido sintético: colunas reais de Transportador desconhecidas.
    return {"texto": "Resultado sintético integral", "tabelas": [
        {"cabecalhos": ["Coluna", "Coluna"], "linhas": [["A", ""], ["B", "C"]]}
    ]}
