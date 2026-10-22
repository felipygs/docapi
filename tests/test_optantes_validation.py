"""Cenários comportamentais sintéticos: DOM real e nenhuma consulta externa."""
from functools import partial
from unittest.mock import patch

from fastapi import HTTPException

from app.api import _safe_call
from app.scrapers.optantes import consultar_optantes
from app.scrapers.optantes_parser import adquirir_snapshot, transformar_snapshot
from support.optantes import BrowserOffline, PaginaOffline, fixture, TITULOS


class TestOptantesValidation(BrowserOffline):
    async def test_paineis_em_mais_info_complementar_preservam_resultados(self):
        # Estrutura observada na captura real de 17/10/2026: os painéis
        # continuam dentro de #maisInfo, sob um contêiner intermediário.
        html = await self.html_mutado('''() => {
            const maisInfo = document.querySelector('#maisInfo');
            const complemento = document.createElement('div');
            complemento.id = 'maisInfoComplementar';
            [...maisInfo.querySelectorAll(':scope > .panel')].slice(1)
                .forEach(panel => complemento.append(panel));
            maisInfo.append(complemento);
        }''')
        resultado = await self.consultar(html)
        self.assertEqual(len(resultado['simples_nacional']['periodos_anteriores']), 3)
        self.assertEqual(resultado['simei']['periodos_anteriores'], [])
        self.assertEqual(resultado['simples_nacional']['eventos_futuros'], [
            {'descricao': 'Exclusão de Ofício - Débitos', 'data_efeito': '2027-01-01'},
        ])
        self.assertEqual(resultado['simei']['eventos_futuros'], [])
        self.assertEqual(resultado['mei_transportador'], {'possui_periodos': False})
        self.assertNotIn('dados_adicionais', resultado)

    async def test_historico_ibs_cbs_separado_dos_regimes_obrigatorios(self):
        rotulo = 'Opções pelo Regime Regular IBS/CBS em Períodos Anteriores:'
        for posicao, registros in (('antes', False), ('entre', False), ('depois', False), ('depois', True)):
            with self.subTest(posicao=posicao, registros=registros):
                html = await self.html_mutado('''({posicao, registros, rotulo}) => {
                    const body = document.querySelector('#maisInfo > .panel .panel-body');
                    const extra = document.createElement('div');
                    extra.innerHTML = '<span>' + rotulo + '</span>' + (registros
                        ? '<table><thead><tr><th>Data Inicial</th><th>Data Final</th><th>Detalhamento</th></tr></thead><tbody><tr><td>01/01/2026</td><td>31/12/2026</td><td>REGISTRO_IBS_CBS</td></tr></tbody></table>'
                        : '<span>Informação indisponível</span>');
                    if (posicao === 'antes') body.prepend(extra);
                    else if (posicao === 'entre') body.querySelector(':scope > span:last-child').before(extra);
                    else body.append(extra);
                }''', arg={'posicao': posicao, 'registros': registros, 'rotulo': rotulo})
                resultado = await self.consultar(html)
                self.assertEqual(len(resultado['simples_nacional']['periodos_anteriores']), 3)
                self.assertEqual(resultado['simei']['periodos_anteriores'], [])
                adicionais = resultado['dados_adicionais']
                self.assertEqual(len(adicionais), 1)
                self.assertEqual(adicionais[0]['secao'], 'Períodos Anteriores')
                self.assertIn(rotulo, adicionais[0]['texto'])
                if registros:
                    self.assertEqual(adicionais[0]['tabelas'][0]['linhas'], [
                        ['01/01/2026', '31/12/2026', 'REGISTRO_IBS_CBS'],
                    ])
                else:
                    self.assertIn('Informação indisponível', adicionais[0]['texto'])

    async def test_ausencia_ibs_cbs_nao_confirma_historico_simei_incompleto(self):
        for conteudo in ('', 'Informação indisponível'):
            with self.subTest(conteudo=conteudo):
                html = await self.html_mutado('''conteudo => {
                    const body = document.querySelector('#maisInfo > .panel .panel-body');
                    body.querySelector(':scope > span:last-child').innerHTML =
                        'Enquadramentos no SIMEI em Períodos Anteriores: <span>' + conteudo + '</span>';
                    body.insertAdjacentHTML('beforeend', '<div><span>Opções pelo Regime Regular IBS/CBS em Períodos Anteriores:</span><span>Não Existem</span></div>');
                }''', arg=conteudo)
                await self.erro(html, 'Períodos Anteriores (SIMEI)')

    async def test_painel_complementar_fora_de_mais_info_continua_invalido(self):
        html = await self.html_mutado('''() => {
            const maisInfo = document.querySelector('#maisInfo');
            const complemento = document.createElement('div');
            complemento.id = 'maisInfoComplementar';
            complemento.append(maisInfo.querySelectorAll(':scope > .panel')[1]);
            document.querySelector('#conteudo').append(complemento);
        }''')
        await self.erro(html, 'Eventos Futuros (Simples Nacional)')

    async def test_situacao_ibs_cbs_adicional_nao_contamina_simei(self):
        html = await self.html_mutado('''() => {
            const panel = [...document.querySelectorAll('.panel')].find(p => p.querySelector('h3')?.textContent.trim() === 'Situação Atual');
            panel.querySelector('.panel-body').insertAdjacentHTML('beforeend', '<p>Situação no Regime Regular do IBS: Informação indisponível</p><p>Situação no Regime Regular da CBS: Informação indisponível</p>');
        }''')
        result = await self.consultar(html)
        self.assertFalse(result['simei']['enquadrado'])
        self.assertEqual(result['simei']['situacao'], 'NÃO enquadrado no SIMEI')
        additional = [d for d in result['dados_adicionais'] if d['secao'] == 'Situação Atual']
        self.assertEqual(len(additional), 1)
        self.assertIn('Situação no Regime Regular do IBS: Informação indisponível', additional[0]['texto'])
        self.assertIn('Situação no Regime Regular da CBS: Informação indisponível', additional[0]['texto'])

    async def test_matriz_de_outra_raiz_nao_e_sucesso(self):
        await self.erro(fixture('eliane_sintetica.html'), 'identidade', cnpj='57435953000108')

    async def html_mutado(self, js, nome="eliane_sintetica.html", arg=None):
        await self.page.set_content(fixture(nome))
        await self.page.evaluate(js, arg)
        return await self.page.content()

    async def erro(self, html, secao, cnpj="43996591000101"):
        offline = PaginaOffline(self.page, html)
        async def esperar_curto(selector, **kwargs):
            # Prazo curto para seção ausente, mas tolerante ao Chrome sob carga
            # da suíte HTTP/browser concorrente; DOM e waits continuam reais.
            kwargs["timeout"] = 1500
            return await self.page.wait_for_selector(selector, **kwargs)
        with patch.object(offline, "wait_for_selector", esperar_curto):
            with self.assertRaises(HTTPException) as raised:
                await _safe_call(partial(consultar_optantes, offline, cnpj, max_retries=1))
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn(secao, raised.exception.detail)
        self.assertNotIn("SEGREDO", raised.exception.detail)
        return raised.exception.detail

    async def test_identidade_horario_abrangencia_e_texto_integral(self):
        resultado = await self.consultar(fixture("eliane_sintetica.html"), "43996591000282")
        self.assertEqual(resultado["cnpj_consultado"], "43996591000282")
        self.assertEqual(resultado["cnpj_matriz"], "43996591000101")
        self.assertEqual(resultado["nome_empresarial"], "ELIANE S MURTA CONSULTORIO ODONTOLOGICO")
        self.assertEqual(resultado["consultado_em"], "2026-10-15T18:08:45")
        self.assertIs(resultado["abrange_todos_estabelecimentos"], True)
        self.assertEqual(resultado["simples_nacional"]["situacao"], "Optante pelo Simples Nacional desde 01/01/2026")
        self.assertIs(resultado["simples_nacional"]["optante"], True)
        self.assertEqual(resultado["simei"]["situacao"], "NÃO enquadrado no SIMEI")
        self.assertIsNone(resultado["simei"]["data_desde"])

    async def test_status_caixa_acentos_positivo_sem_data_e_negativo(self):
        for simples, simei, ativo, enquadrado, data in [
            ("nao OPTANTE pelo SIMPLES NACIONAL", "ENQUADRADO no SIMEI desde 01/02/2024", False, True, "2024-02-01"),
            ("OPTANTE pelo SIMPLES NACIONAL", "Enquadrado no SIMEI", True, True, None),
        ]:
            with self.subTest(simples=simples):
                html = await self.html_mutado("""([sn, sm]) => {
                    const p = [...document.querySelectorAll('.panel')].find(p => p.querySelector(':scope > .panel-heading h3')?.textContent.trim() === 'Situação Atual');
                    const spans = p.querySelectorAll('.panel-body span');
                    spans[0].textContent = sn; spans[1].textContent = sm;
                }""", arg=[simples, simei])
                r = await self.consultar(html)
                self.assertEqual(r["simples_nacional"]["situacao"], simples)
                self.assertIs(r["simples_nacional"]["optante"], ativo)
                self.assertIs(r["simei"]["enquadrado"], enquadrado)
                self.assertEqual(r["simei"]["data_desde"], data)

    async def test_status_desconhecido_ou_data_invalida_nao_inferem_booleano(self):
        for texto in ("Processando SEGREDO", "Optante pelo Simples Nacional desde 31/02/2026", "NÃO optante pelo Simples Nacional SEGREDO"):
            with self.subTest(texto=texto):
                html = fixture("eliane_sintetica.html").replace("Optante pelo Simples Nacional desde 01/01/2026", texto)
                await self.erro(html, "Simples Nacional")

    async def test_identidade_abrangencia_horario_invalidos_falham(self):
        for antigo, novo, secao in [
            ("43.996.591/0001-01", "cnpj SEGREDO", "identificação"),
            ("ELIANE S MURTA CONSULTORIO ODONTOLOGICO", " ", "identificação"),
            ("15/10/2026 18:08:45", "31/02/2026 18:08:45", "Data da consulta"),
            ("abrange todos os estabelecimentos da empresa", "abrangência SEGREDO", "abrangência"),
        ]:
            with self.subTest(secao=secao):
                await self.erro(fixture("eliane_sintetica.html").replace(antigo, novo), secao)

    async def test_eventos_cabecalhos_reordenados_data_vazia_e_extras_repetidas(self):
        html = await self.html_mutado("""() => {
            const table = document.querySelectorAll('table')[1];
            table.innerHTML = '<thead><tr><th>Nota</th><th>Data Efeito</th><th>Descrição do Evento</th><th>Nota</th></tr></thead><tbody><tr><td>A integral</td><td></td><td>Descrição integral sintética</td><td></td></tr></tbody>';
        }""")
        r = await self.consultar(html)
        self.assertEqual(r["simples_nacional"]["eventos_futuros"], [{
            "descricao": "Descrição integral sintética", "data_efeito": None,
            "campos_adicionais": [{"coluna": "Nota", "valor": "A integral"}, {"coluna": "Nota", "valor": ""}],
        }])

    async def test_periodos_cabecalhos_reordenados_celulas_nulas_extras_repetidas(self):
        html = await self.html_mutado("""() => {
            const table = document.querySelector('table');
            table.innerHTML = '<thead><tr><th>Observação</th><th>Detalhamento</th><th>Data Final</th><th>Data Inicial</th><th>Observação</th></tr></thead><tbody><tr><td>Primeira</td><td>Detalhe integral</td><td></td><td>01/02/2024</td><td>Segunda</td></tr><tr><td></td><td></td><td></td><td></td><td>Fim</td></tr></tbody>';
        }""")
        r = await self.consultar(html)
        self.assertEqual(r["simples_nacional"]["periodos_anteriores"], [
            {"data_inicial": "2024-02-01", "data_final": None, "detalhamento": "Detalhe integral", "campos_adicionais": [{"coluna": "Observação", "valor": "Primeira"}, {"coluna": "Observação", "valor": "Segunda"}]},
            {"data_inicial": None, "data_final": None, "detalhamento": None, "campos_adicionais": [{"coluna": "Observação", "valor": ""}, {"coluna": "Observação", "valor": "Fim"}]},
        ])

    async def test_secao_nova_lossless_sem_controles_scripts_comentarios(self):
        html = await self.html_mutado("""() => {
            document.querySelector('#maisInfo').insertAdjacentHTML('beforeend', `<div class="panel"><div class="panel-heading"><h3>Seção fiscal sintética</h3></div><div class="panel-body"><p>Texto integral adicional</p><table><thead><tr><th>Extra</th><th>Extra</th></tr></thead><tbody><tr><td>Um</td><td>Dois</td></tr><tr><td></td><td>Três</td></tr></tbody></table><button>BOTAO_SECRETO</button><script type="application/json">SCRIPT_SECRETO</script><!--COMENTARIO_SECRETO--></div></div>`);
        }""")
        r = await self.consultar(html)
        self.assertEqual(len(r["dados_adicionais"]), 1)
        d = r["dados_adicionais"][0]
        self.assertEqual(d["secao"], "Seção fiscal sintética")
        self.assertIn("Texto integral adicional", d["texto"])
        self.assertIn("Três", d["texto"])
        self.assertNotIn("SECRETO", d["texto"])
        self.assertEqual(d["tabelas"], [{"cabecalhos": ["Extra", "Extra"], "linhas": [["Um", "Dois"], ["", "Três"]]}])
        normal = await self.consultar(fixture("barbara.html"), '53987789000182')
        self.assertNotIn("dados_adicionais", normal)

    async def test_transportador_vazio_real_e_preenchido_sintetico_lossless(self):
        self.assertEqual((await self.consultar(fixture("barbara.html"), '53987789000182'))["mei_transportador"], {"possui_periodos": False})
        # SINTÉTICO: não afirma conhecer o esquema real de Transportador preenchido.
        html = await self.html_mutado("""() => {
            document.querySelector('#maisInfo > .panel:last-child .panel-body').innerHTML = '<p>Períodos sintéticos como MEI Transportador</p><table><thead><tr><th>Registro</th><th>Informação</th></tr></thead><tbody><tr><td>01/01/2024 a 31/12/2024</td><td>Conteúdo integral</td></tr></tbody></table>';
        }""")
        r = (await self.consultar(html))["mei_transportador"]
        self.assertIs(r["possui_periodos"], True)
        self.assertIn("Períodos sintéticos", r["detalhes"]["texto"])
        self.assertEqual(r["detalhes"]["tabelas"], [{"cabecalhos": ["Registro", "Informação"], "linhas": [["01/01/2024 a 31/12/2024", "Conteúdo integral"]]}])

    async def test_transportador_registros_genericos_sem_exigir_esquema_de_datas(self):
        # SINTÉTICO: registros plausíveis não obrigam nomes de colunas/datas.
        html = await self.html_mutado("""() => {
            document.querySelector('#maisInfo > .panel:last-child .panel-body').innerHTML = '<p>Registros como MEI Transportador</p><table><thead><tr><th>Identificador</th><th>Modalidade</th></tr></thead><tbody><tr><td>Registro sintético 123</td><td>Transportador autônomo de cargas</td></tr></tbody></table>';
        }""")
        transportador = (await self.consultar(html))["mei_transportador"]
        self.assertIs(transportador["possui_periodos"], True)
        self.assertEqual(transportador["detalhes"]["tabelas"][0]["linhas"], [["Registro sintético 123", "Transportador autônomo de cargas"]])

    async def test_transportador_erro_ambiguo_nao_vira_true(self):
        for texto in ("", "Carregando...", "Erro ao carregar SEGREDO", "Consulta temporariamente indisponível", "Informação pendente", "Não Existem registros?", "<table><thead><tr><th>Registro</th></tr></thead><tbody><tr><td>Erro SEGREDO</td></tr></tbody></table>"):
            with self.subTest(texto=texto):
                html = await self.html_mutado("""texto => { document.querySelector('#maisInfo > .panel:last-child .panel-body').innerHTML = texto; }""", arg=texto)
                await self.erro(html, "Transportador")

    async def test_validacao_tabelas_502_por_secao_sem_perda_silenciosa(self):
        mutations = [
            "t.querySelector('th').remove()",
            "t.querySelectorAll('th')[1].textContent = t.querySelector('th').textContent",
            "t.querySelector('td').remove()",
            "t.querySelector('tbody tr').insertCell().textContent = 'SEGREDO'",
            "t.querySelector('tbody').textContent = ''",
            "t.querySelector('td').setAttribute('colspan', '2')",
        ]
        for index, secao in ((0, "Períodos Anteriores"), (1, "Eventos Futuros (Simples Nacional)")):
            for mutation in mutations:
                with self.subTest(index=index, mutation=mutation):
                    html = await self.html_mutado("""({index, mutation}) => { const t = document.querySelectorAll('table')[index]; eval(mutation); }""", arg={"index": index, "mutation": mutation})
                    await self.erro(html, secao)
        for antigo, novo, secao in [("01/01/2025", "31/02/2025", "Períodos Anteriores"), ("01/01/2027", "SEGREDO", "Eventos Futuros (Simples Nacional)")]:
            await self.erro(fixture("eliane_sintetica.html").replace(antigo, novo), secao)

    async def test_todas_secoes_obrigatorias_ausentes_ou_duplicadas_falham(self):
        for titulo in TITULOS:
            for duplicar in (False, True):
                with self.subTest(titulo=titulo, duplicar=duplicar):
                    html = await self.html_mutado("""({titulo, duplicar}) => {
                        const h = [...document.querySelectorAll('h3')].find(h => h.textContent.trim() === titulo);
                        const p = h.closest('.panel');
                        if (duplicar) p.after(p.cloneNode(true)); else p.remove();
                    }""", arg={"titulo": titulo, "duplicar": duplicar})
                    await self.erro(html, "Optantes")

    async def test_historicos_limites_invalidos_ausentes_duplicados_e_vazios_falham(self):
        for mutation in (
            "labels[0].remove()", "labels[1].remove()", "labels[0].after(labels[0].cloneNode(true))",
            "labels[1].innerHTML = 'Enquadramentos no SIMEI em Períodos Anteriores:'",
        ):
            with self.subTest(mutation=mutation):
                html = await self.html_mutado("""mutation => {
                    const history = document.querySelector('#maisInfo > .panel .panel-body');
                    const labels = history.querySelectorAll(':scope > span'); eval(mutation);
                }""", arg=mutation)
                await self.erro(html, "Períodos Anteriores")

    async def test_ausencia_nunca_default_conteudo_vazio_ou_misto(self):
        for index in (1, 2, 3):
            for conteudo in ("", "Não Existem<table><thead><tr><th>Descrição do Evento</th><th>Data Efeito</th></tr></thead><tbody><tr><td>Evento sintético</td><td>01/01/2027</td></tr></tbody></table>"):
                html = await self.html_mutado("""({index, conteudo}) => { document.querySelectorAll('#maisInfo > .panel .panel-body')[index].innerHTML = conteudo; }""", arg={"index": index, "conteudo": conteudo})
                with self.subTest(index=index, conteudo=conteudo):
                    await self.erro(html, "Optantes")

    async def test_alertas_visiveis_distintos_e_sem_ocultos(self):
        html = await self.html_mutado("""() => { document.querySelector('#conteudo').insertAdjacentHTML('beforeend', '<div class="alert alert-warning">Aviso fiscal integral</div><div role="alert">Aviso fiscal integral</div><div class="alert" style="display:none">SEGREDO</div>'); }""")
        self.assertEqual((await self.consultar(html))["alertas"], ["Aviso fiscal integral"])

    async def test_regressao_ausencia_historica_oculta_nao_confirma_lista_vazia(self):
        for estilo in ('display:none', 'visibility:hidden'):
            with self.subTest(estilo=estilo):
                html = await self.html_mutado("""estilo => {
                    document.querySelector('#maisInfo > .panel .panel-body > span span').style = estilo;
                }""", nome='barbara.html', arg=estilo)
                await self.erro(html, 'Períodos Anteriores', cnpj='53987789000182')

    async def test_regressao_historico_ignora_descendentes_ocultos_com_contexto_css(self):
        html = await self.html_mutado("""() => {
            document.head.insertAdjacentHTML('beforeend', '<style>#maisInfo .oculto-por-contexto { display:none }</style>');
            document.querySelector('table tbody tr td:last-child').insertAdjacentHTML('beforeend', '<span class="oculto-por-contexto">CONTEUDO_OCULTO</span><span hidden>CONTEUDO_OCULTO_2</span>');
        }""")
        r = await self.consultar(html)
        self.assertEqual(r['simples_nacional']['periodos_anteriores'][0]['detalhamento'], 'Excluída por Ato Administrativo praticado pela Receita Federal do Brasil')
        self.assertNotIn('CONTEUDO_OCULTO', str(r))

    async def test_regressao_rotulos_titulos_e_ancestrais_ocultos_nao_sao_resultado(self):
        for seletor in ('#maisInfo > .panel:first-of-type .panel-body > span:first-child', '#maisInfo > .panel:first-of-type h3', '#maisInfo > .panel:first-of-type', '#maisInfo', '#conteudo', 'h5'):
            with self.subTest(seletor=seletor):
                await self.html_mutado("""seletor => { document.querySelector(seletor).style.display = 'none'; }""", arg=seletor)
                # Testa a fronteira de extração; aquisição de resultado inteiro
                # invisível pode legitimamente expirar antes de chegar aqui.
                async def extrair():
                    return transformar_snapshot(await adquirir_snapshot(self.page), '43996591000101')
                with self.assertRaises(HTTPException) as raised:
                    await _safe_call(extrair)
                self.assertEqual(raised.exception.status_code, 502)

    async def test_regressao_prosa_em_eventos_historicos_e_fora_paineis_lossless(self):
        html = await self.html_mutado("""() => {
            const panels = document.querySelectorAll('#maisInfo > .panel');
            panels[1].querySelector('.panel-body table').insertAdjacentHTML('afterend', '<p>OBSERVACAO_FISCAL_NOVA</p><button>CONTROLE_OCULTO</button><script type="application/json">SCRIPT_OCULTO</script><!--COMENTARIO_OCULTO--><p hidden>PROSA_OCULTA</p>');
            panels[0].querySelector('table').insertAdjacentHTML('afterend', '<p>OBSERVACAO_HISTORICA_NOVA</p>');
            document.querySelector('#maisInfo').insertAdjacentHTML('beforeend', '<p>OBSERVACAO_FORA_PAINEL</p><table><thead><tr><th>Coluna nova</th></tr></thead><tbody><tr><td>Valor externo integral</td></tr></tbody></table>');
        }""")
        r = await self.consultar(html)
        adicionais = r.get('dados_adicionais', [])
        for marcador, contexto in (('OBSERVACAO_FISCAL_NOVA', 'Eventos Futuros (Simples Nacional)'), ('OBSERVACAO_HISTORICA_NOVA', 'Períodos Anteriores (Simples Nacional)'), ('OBSERVACAO_FORA_PAINEL', 'Mais informações')):
            with self.subTest(marcador=marcador):
                encontrados = [d for d in adicionais if marcador in d['texto']]
                self.assertEqual(len(encontrados), 1)
                self.assertEqual(encontrados[0]['secao'], contexto)
                if contexto != 'Mais informações':
                    self.assertEqual(encontrados[0]['tabelas'], [])
        self.assertNotIn('OCULTO', str(r))
        self.assertNotIn('Descrição do Evento', str(adicionais))
        externo = [d for d in adicionais if d['secao'] == 'Mais informações']
        self.assertEqual(len(externo), 1)
        self.assertEqual(externo[0]['tabelas'], [{'cabecalhos': ['Coluna nova'], 'linhas': [['Valor externo integral']]}])

    async def test_regressao_tabela_desconhecida_em_painel_conhecido_sem_duplicar(self):
        html = await self.html_mutado("""() => {
            document.querySelectorAll('#maisInfo > .panel')[1].querySelector('.panel-body').insertAdjacentHTML('beforeend', '<p>Nota da tabela adicional</p><table><thead><tr><th>Nova</th><th>Nova</th></tr></thead><tbody><tr><td>A</td><td>B</td></tr></tbody></table>');
        }""")
        r = await self.consultar(html)
        self.assertEqual(len(r['simples_nacional']['eventos_futuros']), 1)
        self.assertEqual(r.get('dados_adicionais'), [{'secao': 'Eventos Futuros (Simples Nacional)', 'texto': 'Nota da tabela adicional', 'tabelas': [{'cabecalhos': ['Nova', 'Nova'], 'linhas': [['A', 'B']]}]}])

    async def test_regressao_tabela_extra_historica_e_prosa_com_ausencia_explicita(self):
        html = await self.html_mutado("""() => {
            const panels = document.querySelectorAll('#maisInfo > .panel');
            panels[0].querySelector('table').insertAdjacentHTML('afterend', '<p>Nota histórica adicional</p><table><thead><tr><th>Nova</th></tr></thead><tbody><tr><td>Valor histórico adicional</td></tr></tbody></table>');
            panels[2].querySelector('.panel-body').insertAdjacentHTML('beforeend', '<p>Nota fiscal sem eventos</p>');
        }""")
        r = await self.consultar(html)
        self.assertEqual(len(r['simples_nacional']['periodos_anteriores']), 3)
        self.assertEqual(r['simei']['eventos_futuros'], [])
        self.assertEqual(r['dados_adicionais'], [
            {'secao': 'Períodos Anteriores (Simples Nacional)', 'texto': 'Nota histórica adicional', 'tabelas': [{'cabecalhos': ['Nova'], 'linhas': [['Valor histórico adicional']]}]},
            {'secao': 'Eventos Futuros (SIMEI)', 'texto': 'Nota fiscal sem eventos', 'tabelas': []},
        ])

    async def test_regressao_prosa_nao_substitui_marcador_de_ausencia(self):
        for conteudo in (
            '<p>Não Existem resultados confirmados? Aguarde</p>',
            '<p>Não Existem <span>resultados confirmados? Aguarde</span></p>',
        ):
            with self.subTest(conteudo=conteudo):
                html = await self.html_mutado("""conteudo => {
                    document.querySelectorAll('#maisInfo > .panel')[2].querySelector('.panel-body').innerHTML = conteudo;
                }""", arg=conteudo)
                await self.erro(html, 'Eventos Futuros (SIMEI)')

    async def test_regressao_tabela_extra_malformada_nao_desaparece(self):
        html = await self.html_mutado("""() => {
            document.querySelectorAll('#maisInfo > .panel')[1].querySelector('.panel-body').insertAdjacentHTML('beforeend', '<table><thead><tr><th>Extra</th><th>Outra</th></tr></thead><tbody><tr><td>SEGREDO</td></tr></tbody></table>');
        }""")
        await self.erro(html, 'Eventos Futuros (Simples Nacional)')

    async def test_final_ausencia_com_erro_ou_pendente_nao_e_lista_vazia(self):
        for mensagem in (
            'Erro ao carregar eventos futuros. Consulta não concluída.',
            'Não foi possível consultar os períodos.',
            'Carregando...', 'Consulta temporariamente indisponível',
            'Informação pendente', 'Aguarde',
        ):
            with self.subTest(mensagem=mensagem):
                html = await self.html_mutado("""mensagem => {
                    document.querySelectorAll('#maisInfo > .panel')[2].querySelector('.panel-body').innerHTML = '<span>Não Existem</span><p>' + mensagem + '</p>';
                }""", arg=mensagem)
                await self.erro(html, 'Eventos Futuros (SIMEI)')

    async def test_final_transportador_mensagem_de_falha_na_tabela_nao_e_registro(self):
        html = await self.html_mutado("""() => {
            document.querySelector('#maisInfo > .panel:last-child .panel-body').innerHTML = '<table><thead><tr><th>Mensagem</th></tr></thead><tbody><tr><td>Não foi possível consultar os períodos.</td></tr></tbody></table>';
        }""")
        await self.erro(html, 'Transportador')

    async def test_final_nota_antes_dos_rotulos_historicos_e_preservada_sem_duplicar(self):
        html = await self.html_mutado("""() => {
            document.querySelector('#maisInfo > .panel .panel-body').insertAdjacentHTML('afterbegin', '<p>NOTA_FISCAL_ANTES_DOS_HISTORICOS</p>');
        }""")
        r = await self.consultar(html)
        self.assertEqual(r.get('dados_adicionais'), [
            {'secao': 'Períodos Anteriores', 'texto': 'NOTA_FISCAL_ANTES_DOS_HISTORICOS', 'tabelas': []},
        ])
        self.assertEqual(len(r['simples_nacional']['periodos_anteriores']), 3)

    async def test_final_tfoot_nunca_e_truncado_em_tabelas_conhecidas_ou_genericas(self):
        for destino, secao in (('historico', 'Períodos Anteriores'), ('evento', 'Eventos Futuros (Simples Nacional)'), ('generica', 'Eventos Futuros (Simples Nacional)')):
            with self.subTest(destino=destino):
                html = await self.html_mutado("""destino => {
                    const body = document.querySelectorAll('#maisInfo > .panel')[1].querySelector('.panel-body');
                    if (destino === 'generica') body.insertAdjacentHTML('beforeend', '<table><thead><tr><th>Extra</th><th>Extra</th><th>Extra</th></tr></thead><tbody><tr><td>A</td><td>B</td><td>C</td></tr></tbody></table>');
                    const t = destino === 'historico' ? document.querySelector('table') : body.querySelector(destino === 'generica' ? 'table:last-child' : 'table');
                    t.insertAdjacentHTML('beforeend', '<tfoot><tr><td>01/01/2020</td><td>31/12/2020</td><td>PERIODO_FISCAL_ADICIONAL</td></tr></tfoot>');
                }""", arg=destino)
                await self.erro(html, secao)

    async def test_final_caption_adicional_e_conhecida_preservadas_sem_tabela_normalizada(self):
        for conhecida in (False, True):
            with self.subTest(conhecida=conhecida):
                html = await self.html_mutado("""conhecida => {
                    const body = document.querySelectorAll('#maisInfo > .panel')[1].querySelector('.panel-body');
                    if (!conhecida) body.insertAdjacentHTML('beforeend', '<table><thead><tr><th>Nova</th></tr></thead><tbody><tr><td>VALOR_FISCAL_EXTRA</td></tr></tbody></table>');
                    body.querySelector(conhecida ? 'table' : 'table:last-child').insertAdjacentHTML('afterbegin', '<caption>NOTA_FISCAL_NA_TABELA</caption>');
                }""", arg=conhecida)
                r = await self.consultar(html)
                self.assertEqual(r['simples_nacional']['eventos_futuros'], [{'descricao': 'Exclusão de Ofício - Débitos', 'data_efeito': '2027-01-01'}])
                self.assertEqual(r.get('dados_adicionais'), [{
                    'secao': 'Eventos Futuros (Simples Nacional)', 'texto': 'NOTA_FISCAL_NA_TABELA',
                    'tabelas': [] if conhecida else [{'cabecalhos': ['Nova'], 'linhas': [['VALOR_FISCAL_EXTRA']]}],
                }])

    async def test_final_cabecalho_com_celula_nao_th_nao_e_truncado(self):
        html = await self.html_mutado("""() => {
            document.querySelectorAll('table')[1].querySelector('thead tr').insertAdjacentHTML('beforeend', '<td>NOTA_FISCAL_NO_CABECALHO</td>');
        }""")
        await self.erro(html, 'Eventos Futuros (Simples Nacional)')

    async def test_final_multiplos_thead_inclusive_vazio_nao_sao_ignorados(self):
        for extra in ('<thead></thead>', '<thead><tr><th>NOTA_FISCAL_NO_CABECALHO</th></tr></thead>'):
            with self.subTest(extra=extra):
                html = await self.html_mutado("""extra => {
                    document.querySelectorAll('table')[1].insertAdjacentHTML('beforeend', extra);
                }""", arg=extra)
                await self.erro(html, 'Eventos Futuros (Simples Nacional)')

    async def test_final_textos_fiscais_normais_nao_sao_blacklist(self):
        html = await self.html_mutado("""() => {
            document.querySelector('table tbody tr td:last-child').textContent = 'Exclusão de Ofício - Débitos; pendências fiscais e erro cadastral no período';
            document.querySelectorAll('#maisInfo > .panel')[2].querySelector('.panel-body').insertAdjacentHTML('beforeend', '<p>Nota fiscal sobre pendências e erros cadastrais</p>');
            document.querySelector('#maisInfo > .panel:last-child .panel-body').innerHTML = '<table><thead><tr><th>Motivo</th></tr></thead><tbody><tr><td>Exclusão de Ofício - Débitos; pendências fiscais e erro cadastral no período</td></tr></tbody></table>';
        }""")
        r = await self.consultar(html)
        self.assertEqual(r['simples_nacional']['eventos_futuros'][0]['descricao'], 'Exclusão de Ofício - Débitos')
        self.assertIn('erro cadastral', r['simples_nacional']['periodos_anteriores'][0]['detalhamento'])
        self.assertTrue(r['mei_transportador']['possui_periodos'])
        self.assertEqual(r['simei']['eventos_futuros'], [])

    async def test_final_estado_explicito_apos_nota_nao_desaparece_na_prosa(self):
        for index, conteudo, secao in (
            (2, '<span>Não Existem</span><p>Nota fiscal complementar</p><p>Carregando...</p>', 'Eventos Futuros (SIMEI)'),
            (3, '<p>Nota fiscal complementar</p><p>Informação pendente</p><table><thead><tr><th>Registro</th></tr></thead><tbody><tr><td>123</td></tr></tbody></table>', 'Transportador'),
        ):
            with self.subTest(secao=secao):
                html = await self.html_mutado("""({index, conteudo}) => {
                    document.querySelectorAll('#maisInfo > .panel')[index].querySelector('.panel-body').innerHTML = conteudo;
                }""", arg={'index': index, 'conteudo': conteudo})
                await self.erro(html, secao)

    async def test_final_caption_nao_confirma_ausencia_de_eventos(self):
        html = await self.html_mutado("""() => {
            document.querySelectorAll('#maisInfo > .panel')[2].querySelector('.panel-body').innerHTML = '<table><caption>Não Existem</caption><thead><tr><th>Nota</th></tr></thead><tbody><tr><td>Conteúdo fiscal adicional</td></tr></tbody></table>';
        }""")
        await self.erro(html, 'Eventos Futuros (SIMEI)')

    async def test_validation_error_modelo_vira_502_seguro(self):
        # CNPJ de entrada já normalizado é um invariante do chamador; não expor
        # o input se uma futura alteração de extração violar o modelo final.
        await self.erro(fixture("barbara.html"), "cnpj_consultado", cnpj="SEGREDO")
