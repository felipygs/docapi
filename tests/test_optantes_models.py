"""Contrato de modelos Optantes; sem HTTP, browser ou serviços externos."""

from copy import deepcopy
from datetime import date, datetime
import hashlib
import json
import unittest

from pydantic import ValidationError

from app.models import CadastroResponse, ConsultaResponse, DasnResponse, OptantesResponse


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


class TestOptantesModels(unittest.TestCase):
    def validar(self, payload=None):
        try:
            return OptantesResponse.model_validate(eliane() if payload is None else payload)
        except ValidationError as exc:
            self.fail(f"O contrato aprovado deve validar sem perder informações: {exc}")

    def test_exemplo_eliane_roundtrip_integral(self):
        self.assertEqual(self.validar().model_dump(mode="json"), eliane())

    def test_datas_e_horario_sao_tipos_civis_naive(self):
        modelo = self.validar()
        self.assertIsInstance(modelo.consultado_em, datetime)
        self.assertIsNone(modelo.consultado_em.tzinfo)
        self.assertIs(type(modelo.simples_nacional.data_desde), date)
        self.assertIs(type(modelo.simples_nacional.periodos_anteriores[0].data_inicial), date)
        self.assertIs(type(modelo.simples_nacional.eventos_futuros[0].data_efeito), date)

    def test_eventos_rejeitam_texto_e_null_em_ambos_regimes(self):
        for regime in ("simples_nacional", "simei"):
            for valor in (None, "Não Existem", "Descrição do Evento Data Efeito", {}):
                payload = eliane()
                payload[regime]["eventos_futuros"] = valor
                with self.subTest(regime=regime, valor=valor), self.assertRaises(ValidationError):
                    OptantesResponse.model_validate(payload)

    def test_campos_obrigatorios_nao_inferem_coleta_ausente(self):
        self.validar()
        caminhos = [(chave,) for chave in eliane()]
        caminhos += [(regime, chave) for regime in ("simples_nacional", "simei")
                     for chave in eliane()[regime]]
        caminhos += [("mei_transportador", "possui_periodos")]
        for caminho in caminhos:
            payload = eliane()
            alvo = payload
            for chave in caminho[:-1]:
                alvo = alvo[chave]
            del alvo[caminho[-1]]
            with self.subTest(campo=caminho), self.assertRaises(ValidationError):
                OptantesResponse.model_validate(payload)

    def test_campos_das_linhas_sao_obrigatorios_inclusive_datas_nullable(self):
        self.validar()
        for lista in ("periodos_anteriores", "eventos_futuros"):
            for campo in eliane()["simples_nacional"][lista][0]:
                payload = eliane()
                del payload["simples_nacional"][lista][0][campo]
                with self.subTest(lista=lista, campo=campo), self.assertRaises(ValidationError):
                    OptantesResponse.model_validate(payload)

    def test_cnpjs_sao_14_digitos_ascii_sem_mascara(self):
        self.validar()
        for campo in ("cnpj_consultado", "cnpj_matriz"):
            for valor in ("", "4399659100010", "439965910001010", "43.996.591/0001-01",
                          "４３９９６５９１０００１０１", "4399659100010a", 43996591000101, None):
                payload = eliane()
                payload[campo] = valor
                with self.subTest(campo=campo, valor=valor), self.assertRaises(ValidationError):
                    OptantesResponse.model_validate(payload)

    def test_cnpj_consultado_pode_diferir_da_matriz(self):
        payload = eliane()
        payload["cnpj_consultado"] = "43996591000292"
        self.assertEqual(self.validar(payload).model_dump(mode="json"), payload)

    def test_textos_obrigatorios_rejeitam_vazio_e_branco(self):
        self.validar()
        for caminho in (("nome_empresarial",), ("simples_nacional", "situacao"),
                        ("simei", "situacao"), ("simples_nacional", "eventos_futuros", 0, "descricao")):
            for valor in ("", " \t\n", None):
                payload = eliane()
                alvo = payload
                for chave in caminho[:-1]:
                    alvo = alvo[chave]
                alvo[caminho[-1]] = valor
                with self.subTest(campo=caminho, valor=valor), self.assertRaises(ValidationError):
                    OptantesResponse.model_validate(payload)

    def test_booleanos_nao_coagem_inteiros_ou_textos(self):
        self.validar()
        for caminho in (("abrange_todos_estabelecimentos",), ("simples_nacional", "optante"),
                        ("simei", "enquadrado"), ("mei_transportador", "possui_periodos")):
            for valor in (1, 0, "true", "false", None):
                payload = eliane()
                alvo = payload
                for chave in caminho[:-1]:
                    alvo = alvo[chave]
                alvo[caminho[-1]] = valor
                with self.subTest(campo=caminho, valor=valor), self.assertRaises(ValidationError):
                    OptantesResponse.model_validate(payload)

    def test_datas_invalidas_nao_viram_null_nem_timestamp(self):
        self.validar()
        caminhos = (("simples_nacional", "data_desde"), ("simei", "data_desde"),
                    ("simples_nacional", "periodos_anteriores", 0, "data_inicial"),
                    ("simples_nacional", "periodos_anteriores", 0, "data_final"),
                    ("simples_nacional", "eventos_futuros", 0, "data_efeito"))
        for caminho in caminhos:
            for valor in ("2026-02-30", "31/02/2026", "inválida", "", "0", 0, True):
                payload = eliane()
                alvo = payload
                for chave in caminho[:-1]:
                    alvo = alvo[chave]
                alvo[caminho[-1]] = valor
                with self.subTest(campo=caminho, valor=valor), self.assertRaises(ValidationError):
                    OptantesResponse.model_validate(payload)

    def test_horario_invalido_ou_com_fuso_e_rejeitado(self):
        self.validar()
        for valor in (None, "", "0", "2026-10-15", "2026-02-30T18:08:45", "2026-10-15T18:08:45Z",
                      "2026-10-15T18:08:45-03:00", 0, True):
            payload = eliane()
            payload["consultado_em"] = valor
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                OptantesResponse.model_validate(payload)

    def test_datas_null_continuam_presentes_e_detalhamento_vazio_vira_null(self):
        payload = eliane()
        payload["simples_nacional"]["data_desde"] = None
        payload["simples_nacional"]["periodos_anteriores"][0] = {
            "data_inicial": None, "data_final": None, "detalhamento": " \t"}
        payload["simples_nacional"]["eventos_futuros"][0]["data_efeito"] = None
        esperado = deepcopy(payload)
        esperado["simples_nacional"]["periodos_anteriores"][0]["detalhamento"] = None
        self.assertEqual(self.validar(payload).model_dump(mode="json"), esperado)

    def test_omissao_local_de_extensoes_vazias_ou_null(self):
        for vazio in ([], None):
            payload = eliane()
            payload["dados_adicionais"] = vazio
            for lista in ("periodos_anteriores", "eventos_futuros"):
                for linha in payload["simples_nacional"][lista]:
                    linha["campos_adicionais"] = vazio
            with self.subTest(vazio=vazio):
                modelo = self.validar(payload)
                self.assertEqual(modelo.model_dump(mode="json"), eliane())
                self.assertEqual(json.loads(modelo.model_dump_json()), eliane())
                self.assertIsNone(modelo.model_dump()["simei"]["data_desde"])

    def test_extensoes_preservam_ordem_colunas_repetidas_e_celulas(self):
        payload = eliane()
        for lista in ("periodos_anteriores", "eventos_futuros"):
            payload["simples_nacional"][lista][0]["campos_adicionais"] = [
                {"coluna": "Observação", "valor": "A"}, {"coluna": "Observação", "valor": ""}]
        payload["dados_adicionais"] = [{"secao": "Nova seção fiscal", **conteudo()}]
        self.assertEqual(self.validar(payload).model_dump(mode="json"), payload)

    def test_transportador_ausente_omite_detalhes_vazios(self):
        for detalhes in (None, {"texto": "", "tabelas": []}, {"texto": " \t", "tabelas": []}):
            payload = eliane()
            payload["mei_transportador"]["detalhes"] = detalhes
            with self.subTest(detalhes=detalhes):
                self.assertEqual(self.validar(payload).model_dump(mode="json"), eliane())

    def test_transportador_presente_preserva_conteudo_inteiro(self):
        payload = eliane()
        payload["mei_transportador"] = {"possui_periodos": True, "detalhes": conteudo()}
        self.assertEqual(self.validar(payload).model_dump(mode="json"), payload)

    def test_transportador_exige_coerencia_do_booleano_com_detalhes(self):
        self.validar()
        for transportador in (
            {"possui_periodos": True},
            {"possui_periodos": True, "detalhes": None},
            {"possui_periodos": True, "detalhes": {"texto": "", "tabelas": []}},
            {"possui_periodos": False, "detalhes": conteudo()},
        ):
            payload = eliane()
            payload["mei_transportador"] = transportador
            with self.subTest(transportador=transportador), self.assertRaises(ValidationError):
                OptantesResponse.model_validate(payload)

    def test_agregado_mesma_serializacao_local_sem_remover_nulls_outros_schemas(self):
        for preenchido in (False, True):
            payload = eliane()
            if preenchido:
                payload["dados_adicionais"] = [{"secao": "Nova seção fiscal", **conteudo()}]
                payload["mei_transportador"] = {"possui_periodos": True, "detalhes": conteudo()}
            else:
                payload["dados_adicionais"] = []
                payload["mei_transportador"]["detalhes"] = None
                payload["simples_nacional"]["eventos_futuros"][0]["campos_adicionais"] = []
            individual = self.validar(payload)
            agregado = ConsultaResponse.model_validate({
                "cnpj": "43.996.591/0001-01", "cadastro": {"endereco": {}, "contato": {}},
                "dasn": {}, "optantes": payload})
            with self.subTest(preenchido=preenchido):
                resultado = agregado.model_dump(mode="json")
                self.assertEqual(resultado["optantes"], individual.model_dump(mode="json"))
                self.assertEqual(json.loads(agregado.model_dump_json())["optantes"], resultado["optantes"])
                self.assertIsNone(resultado["optantes"]["simei"]["data_desde"])
                self.assertIn("data_abertura", resultado["cadastro"])
                self.assertIsNone(resultado["cadastro"]["data_abertura"])
                self.assertIn("data_baixa", resultado["dasn"])
                self.assertIsNone(resultado["dasn"]["data_baixa"])

    def test_json_schema_exemplos_validos_incluem_eliane(self):
        schema = OptantesResponse.model_json_schema()
        exemplos = schema.get("examples", [])
        self.assertTrue(exemplos)
        self.assertIn(eliane(), exemplos)
        for exemplo in exemplos:
            with self.subTest(exemplo=exemplo.get("nome_empresarial")):
                self.assertEqual(self.validar(exemplo).model_dump(mode="json"), exemplo)

    def test_schema_declaracoes_required_formatos_e_eventos_array(self):
        self.validar()
        schema = OptantesResponse.model_json_schema()
        self.assertEqual(set(schema["required"]), set(eliane()))
        self.assertEqual(schema["properties"]["consultado_em"]["format"], "date-time")
        for nome in ("SimplesInfo", "SimeiInfo"):
            props = schema["$defs"][nome]["properties"]
            self.assertEqual(props["eventos_futuros"]["type"], "array")
            self.assertEqual(props["eventos_futuros"]["items"]["$ref"], "#/$defs/EventoFuturo")
            self.assertIn({"type": "null"}, props["data_desde"]["anyOf"])
            self.assertIn({"type": "string", "format": "date"}, props["data_desde"]["anyOf"])
            self.assertTrue(all(campo.get("description") for campo in props.values()))
        self.assertEqual(ConsultaResponse.model_json_schema()["properties"]["optantes"]["$ref"],
                         "#/$defs/OptantesResponse")

    def test_cadastro_dasn_schemas_exatamente_inalterados(self):
        # Hashes obtidos antes da implementação, com Pydantic 2.14.1.
        for modelo, esperado in (
            (CadastroResponse, "7c6c24d7c94cca9ae5081f0f6b813cce731eb05e6c467d40b9b7d6b38ad1b77c"),
            (DasnResponse, "559005ebecc8b04da6392c07e88e8730da818f8778bdca233e2eb2755c81d7c5"),
        ):
            with self.subTest(modelo=modelo.__name__):
                digest = hashlib.sha256(json.dumps(modelo.model_json_schema(), sort_keys=True).encode()).hexdigest()
                self.assertEqual(digest, esperado)


if __name__ == "__main__":
    unittest.main()
