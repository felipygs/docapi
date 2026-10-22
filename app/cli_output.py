"""Apresentação textual, sem executar consultas nem interpretar argumentos."""


def imprimir_resultado(r: dict) -> None:
    _imprimir_cadastro(r)
    _imprimir_optantes(r['optantes'])
    _imprimir_dasn(r['dasn'])


def _imprimir_cadastro(r: dict) -> None:
    cad = r["cadastro"]
    dasn = r["dasn"]
    print(f"CNPJ: {r['cnpj']}")
    print(f"Razao Social: {cad['nome_empresarial'] or dasn['razao_social']}")
    if cad["nome_fantasia"] and cad["nome_fantasia"] != "********":
        print(f"Nome Fantasia: {cad['nome_fantasia']}")
    print(f"Abertura: {cad['data_abertura']}  |  Porte: {cad['porte']}")
    print(f"Natureza Juridica: {cad['natureza_juridica']}")
    print(f"CNAE Principal: {cad['atividade_principal']}")
    if cad["atividades_secundarias"]:
        print(f"CNAE Secundario: {cad['atividades_secundarias']}")
    endereco = cad["endereco"]
    end = f"{endereco['logradouro'] or '-'}, {endereco['numero'] or '-'}"
    if endereco["complemento"] and endereco["complemento"] != "********":
        end += f" - {endereco['complemento']}"
    end += f" - {endereco['bairro'] or '-'}, {endereco['municipio'] or '-'}/{endereco['uf'] or '-'} - CEP {endereco['cep'] or '-'}"
    print(f"Endereco: {end}")
    contato = cad["contato"]
    telefone = contato["telefone"]
    if contato["email"] or telefone["numero"]:
        numero = ' '.join(parte for parte in (telefone['ddd'], telefone['numero']) if parte)
        print(f"Email: {contato['email'] or '-'}  |  Tel: {numero or '-'}")
    situacao = cad["situacao_cadastral"]
    estado = next((nome.upper() for nome in ('ativa', 'baixada', 'suspensa', 'inapta', 'nula') if situacao[nome]), 'Nao informada')
    print(f"Situacao Cadastral: {estado} desde {situacao['data'] or '-'}")
    if dasn["mei_baixada"]:
        print("*** MEI BAIXADA ***" + (f" em {dasn['data_baixa']}" if dasn["data_baixa"] else ""))
    print()



def _imprimir_optantes(opt: dict) -> None:
    print("--- Situacao Atual ---")
    print(f"  Simples Nacional: {opt['simples_nacional']['situacao']}")
    print(f"  SIMEI: {opt['simei']['situacao']}")
    print()

    for campo, titulo in (("simei", "SIMEI"), ("simples_nacional", "Simples Nacional")):
        periodos = opt[campo]["periodos_anteriores"]
        if periodos:
            print(f"--- Periodos {titulo} Anteriores ---")
            print(f"  {'DE':<12} {'ATE':<12} {'DETALHAMENTO'}")
            for p in periodos:
                print(f"  {p['data_inicial'] or '-':<12} {p['data_final'] or '-':<12} {p['detalhamento'] or '-'}")
            print()



def _imprimir_dasn(dasn: dict) -> None:
    print("--- Declaracoes DASN-SIMEI ---")
    print("=" * 70)
    print(f"{'ANO':<6} {'STATUS':<20} {'APRESENTACAO':<15} {'SIT.ESPECIAL':<15} {'PENDENTE'}")
    print("=" * 70)

    for d in dasn["declaracoes"] or []:
        if d["pendente"]:
            flag = ">>> SIM <<<"
        elif d["baixada"]:
            flag = "BAIXADA"
        else:
            flag = "Nao"
        sit = d["situacao_especial"] if d["situacao_especial"] not in (None, "-") else ""
        if d["data_baixa"] not in (None, "-"):
            sit = f"{sit} {d['data_baixa']}".strip()
        print(f"{d['ano']:<6} {d['status'] or '-':<20} {d['data_apresentacao'] or '-':<15} {sit:<15} {flag}")

    print("=" * 70)

    pendentes = dasn["pendentes"]
    if pendentes is None:
        print(f"\n[!] {dasn['mensagem']}")
    elif pendentes:
        anos = ", ".join(str(ano) for ano in pendentes)
        print(f"\n[!] Declaracoes PENDENTES: {anos}")
    else:
        print("\n[OK] Nenhuma declaracao pendente.")
