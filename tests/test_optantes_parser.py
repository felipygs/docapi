"""Regressões offline de 1.1–1.3, pela fronteira consultar_optantes existente.

Não simulamos evaluate/locators nem duplicamos o parser: somente goto é trocado
por set_content. Os controles de teste permitem o frontend atual, mas não fazem
consulta/Ajax: o resultado já está expandido e Mais informações está disabled.
Os casos sintéticos não alegam representar capturas adicionais do portal.
"""

import unittest




from support.optantes import (
    BrowserOffline, PaginaOffline, fixture, FIXTURES, DETALHAMENTO,
    SIMEI_DETALHAMENTO, TITULOS, ELIANE_PERIODOS, ELIANE_EVENTOS,
)


class TestFixturesOffline(BrowserOffline):
    async def test_fixtures_sem_scripts_referencias_ou_atributos_de_extensao(self):
        for nome in ("ivanusa.html", "barbara.html", "eliane_sintetica.html"):
            with self.subTest(fixture=nome):
                html = fixture(nome)
                self.assertIn("<!--", html)
                self.assertIn("Proveniência" if nome != "eliane_sintetica.html" else "SINTÉTICA", html)
                await self.page.set_content(html, wait_until="load")
                self.assertEqual(await self.page.title(), "Consulta Optantes")
                self.assertEqual(
                    await self.page.locator("h3").evaluate_all(
                        "els => els.map(el => el.textContent.trim())"
                    ), TITULOS,
                )
                self.assertEqual(await self.page.locator("#btnMaisInfo").is_disabled(), True)
                self.assertEqual(await self.page.locator("#maisInfo > .panel").count(), 4)
                self.assertEqual(await self.page.locator("[id='spnEvFutSimei']").count(), 2)
                recursos = await self.page.evaluate("""() => Array.from(document.querySelectorAll('*'))
                    .flatMap(el => {
                        const forbiddenTag = ['SCRIPT', 'LINK', 'BASE', 'IFRAME', 'OBJECT',
                            'EMBED', 'IMG', 'AUDIO', 'VIDEO', 'SOURCE'].includes(el.tagName);
                        const attrs = Array.from(el.attributes).filter(a =>
                            /^(src|srcset|href|action|formaction|poster|background)$/i.test(a.name)
                            || /^on/i.test(a.name) || /cursor|extension|inject|fiorilli/i.test(a.name)
                            || /chrome-extension:|url\\s*\\(|@import/i.test(a.value)
                            || (el.tagName === 'META' && !['charset'].includes(a.name)));
                        return forbiddenTag || attrs.length ? [el.outerHTML] : [];
                    })""")
                self.assertEqual(recursos, [])
                self.assertEqual(self.requests, [])

    async def test_ivanusa_dados_fiscais_e_titulos_preservados(self):
        # Oráculo transcrito da captura real indicada na proveniência (não do parser).
        await self.page.set_content(fixture("ivanusa.html"), wait_until="load")
        self.assertEqual(await self.page.locator("#hdnCnpj").input_value(), "45726608000136")
        texto = " ".join((await self.page.locator("#conteudo").inner_text()).split())
        for trecho in (
            "15/10/2026 17:58:47", "45.726.608/0001-36", "IVANUSA DE O MELO COMERCIO",
            "A opção pelo Simples Nacional e/ou SIMEI abrange todos os estabelecimentos da empresa",
            "Situação no Simples Nacional: Optante pelo Simples Nacional desde 01/01/2026",
            "Situação no SIMEI: NÃO enquadrado no SIMEI",
            "Opções pelo Simples Nacional em Períodos Anteriores:",
            "Enquadramentos no SIMEI em Períodos Anteriores:",
        ):
            self.assertIn(trecho, texto)
        self.assertEqual(await self.page.locator("table").evaluate_all("""tables => tables.map(t => ({
            cabecalhos: Array.from(t.querySelectorAll('th'), x => x.textContent.trim()),
            linhas: Array.from(t.querySelectorAll('tbody tr'), tr =>
                Array.from(tr.querySelectorAll('td'), x => x.textContent.trim()))
        }))"""), [
            {"cabecalhos": ["Data Inicial", "Data Final", "Detalhamento"],
             "linhas": [["21/03/2022", "31/12/2025", DETALHAMENTO]]},
            {"cabecalhos": ["Data Inicial", "Data Final", "Detalhamento"],
             "linhas": [["21/03/2022", "30/09/2023", SIMEI_DETALHAMENTO]]},
        ])
        self.assertEqual(texto.count("Não Existem"), 3)

    async def test_barbara_dados_fiscais_e_ausencias_preservados(self):
        await self.page.set_content(fixture("barbara.html"), wait_until="load")
        self.assertEqual(await self.page.locator("#hdnCnpj").input_value(), "53987789000182")
        texto = " ".join((await self.page.locator("#conteudo").inner_text()).split())
        for trecho in (
            "15/10/2026 18:00:03", "53.987.789/0001-82", "BARBARA C SILVA REPRESENTACOES",
            "A opção pelo Simples Nacional e/ou SIMEI abrange todos os estabelecimentos da empresa",
            "Situação no Simples Nacional: Optante pelo Simples Nacional desde 20/02/2024",
            "Situação no SIMEI: NÃO enquadrado no SIMEI",
            "Opções pelo Simples Nacional em Períodos Anteriores: Não Existem",
            "Enquadramentos no SIMEI em Períodos Anteriores: Não Existem",
        ):
            self.assertIn(trecho, texto)
        self.assertEqual(await self.page.locator("table").count(), 0)
        self.assertEqual(texto.count("Não Existem"), 5)

    async def test_eliane_sintetica_contem_exatamente_evidencias_do_design(self):
        await self.page.set_content(fixture("eliane_sintetica.html"), wait_until="load")
        self.assertEqual(await self.page.locator("#hdnCnpj").input_value(), "43996591000101")
        texto = " ".join((await self.page.locator("#conteudo").inner_text()).split())
        for trecho in ("15/10/2026 18:08:45", "ELIANE S MURTA CONSULTORIO ODONTOLOGICO",
                       "Enquadramentos no SIMEI em Períodos Anteriores: Não Existem"):
            self.assertIn(trecho, texto)
        self.assertEqual(await self.page.locator("table tbody tr").count(), 4)
        self.assertEqual(await self.page.locator("table").first.locator("tbody tr").count(), 3)
        self.assertIn("Exclusão de Ofício - Débitos", texto)
        self.assertIn("01/01/2027", texto)


class TestOptantesBaseline(BrowserOffline):
    async def test_ivanusa_um_historico_independente_por_regime(self):
        resultado = await self.consultar(fixture("ivanusa.html"), "45726608000136")
        self.assertEqual(resultado["simples_nacional"]["periodos_anteriores"], [
            {"data_inicial": "2022-03-21", "data_final": "2025-12-31", "detalhamento": DETALHAMENTO},
        ])
        self.assertEqual(resultado["simei"]["periodos_anteriores"], [
            {"data_inicial": "2022-03-21", "data_final": "2023-09-30", "detalhamento": SIMEI_DETALHAMENTO},
        ])

    async def test_barbara_ambos_historicos_explicitamente_vazios(self):
        resultado = await self.consultar(fixture("barbara.html"), "53987789000182")
        self.assertEqual(resultado["simples_nacional"]["periodos_anteriores"], [])
        self.assertEqual(resultado["simei"]["periodos_anteriores"], [])


class TestOptantesParser(BrowserOffline):
    async def test_eliane_tres_periodos_simples_sem_contaminar_simei(self):
        resultado = await self.consultar(fixture("eliane_sintetica.html"))
        self.assertEqual(resultado["simples_nacional"]["periodos_anteriores"], ELIANE_PERIODOS)
        self.assertEqual(resultado["simei"]["periodos_anteriores"], [],
                         "SIMEI Não Existem não pode receber os três períodos do Simples")

    async def test_eliane_evento_2027_pertence_somente_ao_simples(self):
        resultado = await self.consultar(fixture("eliane_sintetica.html"))
        for regime, esperado in (("simples_nacional", ELIANE_EVENTOS), ("simei", [])):
            with self.subTest(regime=regime):
                self.assertEqual(resultado[regime]["eventos_futuros"], esperado)

    async def test_inverso_simples_vazio_simei_tres_periodos_na_ordem(self):
        # Sintético inverso: move SOMENTE a tabela histórica de ELIANE para SIMEI.
        # Não representa dados fiscais reais dessa empresa; evento permanece no Simples.
        await self.page.set_content(fixture("eliane_sintetica.html"), wait_until="load")
        await self.page.evaluate("""() => {
            const history = document.querySelector('#maisInfo > .panel .panel-body');
            const table = history.querySelector('table');
            const labels = history.querySelectorAll(':scope > span');
            labels[1].querySelector('span').remove();
            history.appendChild(table);
            labels[0].appendChild(Object.assign(document.createElement('span'), {
                className: 'spanValorVerde', textContent: 'Não Existem'
            }));
        }""")
        resultado = await self.consultar(await self.page.content())
        # Subtests executam ambos os oráculos, mesmo se o primeiro denunciar vazamento.
        for regime, esperado in (("simples_nacional", []), ("simei", ELIANE_PERIODOS)):
            with self.subTest(regime=regime):
                self.assertEqual(resultado[regime]["periodos_anteriores"], esperado)

    async def test_paineis_reordenados_nao_mudam_historicos(self):
        # Sintético: eventos ANTES do histórico e SIMEI antes de Simples; mantém
        # IDs duplicados do portal e tabela de evento, que nunca deve virar período.
        await self.page.set_content(fixture("eliane_sintetica.html"), wait_until="load")
        await self.page.evaluate("""() => {
            const root = document.querySelector('#maisInfo');
            const panels = root.querySelectorAll(':scope > .panel');
            [panels[2], panels[1], panels[3], panels[0]].forEach(p => root.appendChild(p));
        }""")
        resultado = await self.consultar(await self.page.content())
        for regime, esperado in (("simples_nacional", ELIANE_PERIODOS), ("simei", [])):
            with self.subTest(regime=regime):
                self.assertEqual(resultado[regime]["periodos_anteriores"], esperado)

    async def test_eventos_ids_duplicados_paineis_reordenados_preservam_regime_e_ordem(self):
        # Inteiramente sintético: eventos distintos em ambos regimes; repetição de
        # linha intencional no Simples exige preservação, não ordenação/deduplicação.
        # IDs iguais não identificam o regime: somente o título delimita a tabela.
        eventos_simples = [
            {"descricao": "Exclusão de Ofício - Débitos", "data_efeito": "2027-01-01"},
            {"descricao": "Evento sintético Simples posterior", "data_efeito": "2027-03-01"},
            {"descricao": "Exclusão de Ofício - Débitos", "data_efeito": "2027-01-01"},
        ]
        eventos_simei = [
            {"descricao": "Evento sintético SIMEI B", "data_efeito": "2028-02-01"},
            {"descricao": "Evento sintético SIMEI A", "data_efeito": "2027-04-01"},
        ]
        await self.page.set_content(fixture("barbara.html"), wait_until="load")
        await self.page.evaluate("""({simples, simei}) => {
            const root = document.querySelector('#maisInfo');
            const panels = root.querySelectorAll(':scope > .panel');
            [simples, simei].forEach((events, index) => {
                const span = panels[index + 1].querySelector('[id="spnEvFutSimei"]');
                span.textContent = '';
                const table = document.createElement('table');
                table.innerHTML = '<thead><tr><th>Descrição do Evento</th><th>Data Efeito</th></tr></thead><tbody></tbody>';
                for (const event of events) {
                    const row = table.tBodies[0].insertRow();
                    row.insertCell().textContent = event.descricao;
                    row.insertCell().textContent = event.data_efeito.split('-').reverse().join('/');
                }
                span.appendChild(table);
            });
            [panels[2], panels[3], panels[1], panels[0]].forEach(p => root.appendChild(p));
        }""", {"simples": eventos_simples, "simei": eventos_simei})
        self.assertEqual(await self.page.locator('[id="spnEvFutSimei"]').count(), 2)
        resultado = await self.consultar(await self.page.content(), "53987789000182")
        for regime, esperado in (("simples_nacional", eventos_simples), ("simei", eventos_simei)):
            with self.subTest(regime=regime, campo="eventos_futuros"):
                self.assertEqual(resultado[regime]["eventos_futuros"], esperado)
            with self.subTest(regime=regime, campo="periodos_anteriores"):
                self.assertEqual(resultado[regime]["periodos_anteriores"], [],
                                 "Tabelas de eventos não são históricos")


if __name__ == "__main__":
    unittest.main()
