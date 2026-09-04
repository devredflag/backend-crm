"""
Agregação do funil por coorte — a parte que NÃO fala com o banco.

Está fora do `main.py` por um motivo prático: o backend recusa subir contra
produção fora do Railway e o `.env.dev` está sem banco, então importar `main.py`
para testar qualquer coisa é impossível. Aqui não há `engine`, nem `text()`, nem
FastAPI — só listas e datas, o que torna `test_funil.py` executável com um
`python test_funil.py` e sem dependência nenhuma.

A rota `GET /funil/transicoes` faz o SQL, entrega as linhas para cá e devolve o
que voltar. Se a lógica de coorte voltar para dentro do `main.py`, ela volta a
ser inverificável.
"""

from datetime import datetime, timedelta

# A ordem do funil desenhado. "Perdido" é saída, não etapa, e "Rascunho" está
# fora do funil — nenhum dos dois entra nesta lista.
ETAPAS_FUNIL_ORDEM = [
    "Lead", "Em contato", "Visita agendada", "Proposta", "Negociação", "Fechado",
]

# `Ganho` e `Cliente` são grafias legadas de `Fechado`. O frontend grava
# `Fechado` e nunca gravou as outras, mas elas aparecem em consultas antigas do
# `main.py` — inclusive em `/gerencia/dashboard`, que conta `status = 'Ganho'` e
# por isso devolve zero. Aceitar as três aqui evita que um registro histórico
# gravado com a grafia antiga desapareça do funil.
SINONIMOS_ETAPA = {"Ganho": "Fechado", "Cliente": "Fechado"}

POSICAO_ETAPA = {nome: i for i, nome in enumerate(ETAPAS_FUNIL_ORDEM)}
SAIDA_PERDIDO = "Perdido"


def normalizar_etapa(valor):
    """Nome canônico da etapa, ou None para o que não pertence ao funil
    desenhado (`Rascunho`, `Perdido`, grafia desconhecida)."""
    if not valor:
        return None
    nome = SINONIMOS_ETAPA.get(str(valor).strip(), str(valor).strip())
    return nome if nome in POSICAO_ETAPA else None


def mediana(valores):
    """Mediana, ou None sem amostra.

    Mediana e não média em todo lugar deste arquivo: uma empresa esquecida por
    um ano arrasta a média da etapa inteira e esconde que as outras estão
    saudáveis.
    """
    if not valores:
        return None
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    if len(ordenados) % 2:
        return float(ordenados[meio])
    return (ordenados[meio - 1] + ordenados[meio]) / 2.0


def janela_meses(meses, agora=None):
    """Do 1º dia do mês `meses-1` atrás até o último instante do mês corrente.

    É a mesma janela de `janelaMeses` no frontend (`utils/metricas.ts`). As duas
    pontas precisam concordar sobre o que é "os últimos 6 meses": se divergirem,
    o mesmo período devolve dois recortes na mesma tela e não há como saber qual
    está certo.
    """
    agora = agora or datetime.now()
    ano, mes = agora.year, agora.month - (meses - 1)
    while mes <= 0:
        mes += 12
        ano -= 1
    inicio = datetime(ano, mes, 1)
    if agora.month == 12:
        prox_ano, prox_mes = agora.year + 1, 1
    else:
        prox_ano, prox_mes = agora.year, agora.month + 1
    fim = datetime(prox_ano, prox_mes, 1) - timedelta(microseconds=1)
    return inicio, fim


def agregar_funil(linhas, inicio, fim):
    """Taxa de passagem entre etapas, para a coorte que ENTROU na janela.

    `linhas` são as mudanças de status, com `empresa_id`, `status_anterior`,
    `status_novo` e `alterado_em`, **ordenadas por empresa e por data**.

    ── COORTE, não fluxo ──────────────────────────────────────────────────────
    A pergunta certa é "dos leads que entraram neste período, quantos
    avançaram", e não "quantas transições aconteceram no período". A segunda
    mistura safras no mesmo denominador: uma empresa que entrou há dois anos e
    avançou ontem contaria como sucesso do mês, e a taxa passaria a medir a
    idade da base em vez do desempenho do time.

    Por isso a janela recorta pela PRIMEIRA entrada de cada empresa no
    histórico, e a progressão dela é seguida até o fim — mesmo que o avanço
    aconteça depois de a janela acabar.

    ⚠️ O viés inerente: coorte recente teve menos tempo para converter, então o
    período mais curto sempre parece pior. Não há como corrigir sem prever o
    futuro; o que dá para fazer é dizer, e é o que `aviso_coorte_recente` faz.
    """
    por_empresa = {}
    for linha in linhas:
        por_empresa.setdefault(str(linha.empresa_id), []).append(linha)

    transicoes = {}
    retrocessos = 0
    alcancaram = {e: 0 for e in ETAPAS_FUNIL_ORDEM}
    avancaram = {e: 0 for e in ETAPAS_FUNIL_ORDEM}
    perdidos_em = {e: 0 for e in ETAPAS_FUNIL_ORDEM}
    dias_por_etapa = {e: [] for e in ETAPAS_FUNIL_ORDEM}
    na_coorte = 0
    fecharam = 0
    perderam = 0

    for eventos in por_empresa.values():
        # As linhas chegam ordenadas do SQL; reordenar aqui é barato e evita que
        # a corretude dependa de um ORDER BY distante, em outro arquivo.
        eventos = sorted(eventos, key=lambda e: e.alterado_em)

        entrada = eventos[0].alterado_em
        if entrada is None or entrada < inicio or entrada > fim:
            continue                      # outra safra: não entra nesta coorte
        na_coorte += 1

        # PRIMEIRA chegada a cada etapa, não a última: uma empresa que voltou
        # para "Em contato" e subiu de novo levou o tempo desde a primeira vez
        # que chegou lá. Usar a última esconderia o retrabalho, que é justamente
        # o que este número deveria expor.
        primeira_chegada = {}
        perdida_em = None

        for ev in eventos:
            etapa = normalizar_etapa(ev.status_novo)
            anterior = normalizar_etapa(ev.status_anterior)

            bruto_anterior = (str(ev.status_anterior).strip() if ev.status_anterior else "")
            rotulo_de = anterior or (bruto_anterior or "(entrada)")
            rotulo_para = etapa or (str(ev.status_novo).strip() if ev.status_novo else "?")
            chave = (rotulo_de, rotulo_para)
            transicoes[chave] = transicoes.get(chave, 0) + 1

            if anterior and etapa and POSICAO_ETAPA[etapa] < POSICAO_ETAPA[anterior]:
                retrocessos += 1

            if etapa and etapa not in primeira_chegada:
                primeira_chegada[etapa] = ev.alterado_em
            if (ev.status_novo or "").strip() == SAIDA_PERDIDO and perdida_em is None:
                perdida_em = ev.alterado_em

        if "Fechado" in primeira_chegada:
            fecharam += 1
        if perdida_em is not None:
            perderam += 1

        for etapa, quando in primeira_chegada.items():
            alcancaram[etapa] += 1
            posicao = POSICAO_ETAPA[etapa]

            # Avançar = chegar a uma etapa POSTERIOR **depois** de ter chegado
            # nesta. A condição temporal não é decorativa: sem ela, uma empresa
            # que esteve em Proposta e voltou para "Em contato" contaria
            # "Em contato avançou" por causa de um evento anterior à volta.
            adiante = [
                q for outra, q in primeira_chegada.items()
                if POSICAO_ETAPA[outra] > posicao and q > quando
            ]
            if adiante:
                avancaram[etapa] += 1
                dias_por_etapa[etapa].append(max((min(adiante) - quando).days, 0))
            elif perdida_em is not None and perdida_em > quando:
                perdidos_em[etapa] += 1

    etapas = []
    ultima_posicao = len(ETAPAS_FUNIL_ORDEM) - 1
    for i, nome in enumerate(ETAPAS_FUNIL_ORDEM):
        chegaram = alcancaram[nome]
        subiram = avancaram[nome]
        etapas.append({
            "etapa": nome,
            "alcancaram": chegaram,
            "avancaram": subiram,
            # `Fechado` é o fim do funil: não existe "avançar" a partir dele, e
            # devolver 0% ali seria lido como fracasso do melhor resultado
            # possível. None = a pergunta não se aplica, diferente de zero.
            "taxa_avanco": (round(subiram / chegaram * 100, 1)
                            if chegaram and i != ultima_posicao else None),
            "perdidos": perdidos_em[nome],
            # Ainda ali: chegou, não avançou e não se perdeu.
            "parados": max(chegaram - subiram - perdidos_em[nome], 0),
            "dias_ate_avancar": mediana(dias_por_etapa[nome]),
            "amostra_dias": len(dias_por_etapa[nome]),
        })

    lista_transicoes = [
        {"de": de, "para": para, "total": total}
        for (de, para), total in transicoes.items()
    ]
    lista_transicoes.sort(key=lambda t: (-t["total"], t["de"], t["para"]))

    mediana_geral = mediana([d for lista in dias_por_etapa.values() for d in lista])
    dias_da_janela = max((fim - inicio).days, 1)

    return {
        "etapas": etapas,
        "transicoes": lista_transicoes,
        "retrocessos": retrocessos,
        "coorte": {
            "entraram": na_coorte,
            "fecharam": fecharam,
            "perderam": perderam,
            "em_aberto": max(na_coorte - fecharam - perderam, 0),
            "taxa_fechamento": (round(fecharam / na_coorte * 100, 1) if na_coorte else None),
            # Verdadeiro quando a janela é curta demais para a coorte ter
            # maturado — menos de três vezes a mediana de avanço de uma etapa.
            # A tela usa isto para avisar em vez de deixar o gerente concluir
            # que o time piorou, quando o que houve foi falta de tempo.
            "aviso_coorte_recente": bool(
                mediana_geral is not None and dias_da_janela < mediana_geral * 3
            ),
        },
    }
