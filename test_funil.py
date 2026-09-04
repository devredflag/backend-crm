"""
Testes da agregação do funil.  Rode com:  python test_funil.py

Sem pytest de propósito: `requirements.txt` é o que o Railway instala em
produção, e uma dependência de teste ali entra na imagem de deploy sem nunca
rodar lá. `assert` puro resolve, não pede nada e roda com um comando.

Existem porque esta lógica NÃO pode ser exercitada contra o banco durante o
desenvolvimento — o processo recusa subir contra produção fora do Railway e o
`.env.dev` está sem banco. Sem isto, a condição temporal do "avançou" (a parte
que trata empresa que volta para uma etapa anterior) seria código que ninguém
nunca executou.
"""

from collections import namedtuple
from datetime import datetime

from funil import agregar_funil, janela_meses, mediana, normalizar_etapa

Linha = namedtuple("Linha", "empresa_id status_anterior status_novo alterado_em")

# Janela de teste: 1º de janeiro a 30 de junho de 2026. Datas fixas de
# propósito — teste de métrica temporal com `datetime.now()` passa hoje e quebra
# na virada do mês, e a falha aparece como número errado em produção, não como
# teste vermelho.
INICIO = datetime(2026, 1, 1)
FIM = datetime(2026, 6, 30, 23, 59, 59)


def d(dia_iso):
    return datetime.fromisoformat(dia_iso)


def etapa(resultado, nome):
    return [e for e in resultado["etapas"] if e["etapa"] == nome][0]


falhas = []


def checar(descricao, condicao, detalhe=""):
    if condicao:
        print(f"  ok   {descricao}")
    else:
        falhas.append(f"{descricao} {detalhe}".strip())
        print(f"  FALHA {descricao} {detalhe}")


# ═══════════════════════════════════════════════════════════════════════════
print("\njanela_meses")

ini, fim = janela_meses(6, datetime(2026, 6, 15, 12))
checar("6 meses terminam no fim de junho", ini == datetime(2026, 1, 1) and fim.month == 6 and fim.day == 30)

ini, fim = janela_meses(3, datetime(2026, 2, 10))
checar("atravessa a virada de ano", ini == datetime(2025, 12, 1) and fim.month == 2 and fim.day == 28)

ini, fim = janela_meses(1, datetime(2026, 12, 5))
checar("dezembro não estoura para o mês 13", ini == datetime(2026, 12, 1) and fim.year == 2026 and fim.month == 12 and fim.day == 31)


# ═══════════════════════════════════════════════════════════════════════════
print("\nnormalizar_etapa")

checar("grafia legada 'Ganho' vira 'Fechado'", normalizar_etapa("Ganho") == "Fechado")
checar("'Perdido' não é etapa do funil", normalizar_etapa("Perdido") is None)
checar("'Rascunho' não é etapa do funil", normalizar_etapa("Rascunho") is None)
checar("None não quebra", normalizar_etapa(None) is None)
checar("espaço em volta não atrapalha", normalizar_etapa("  Proposta ") == "Proposta")


# ═══════════════════════════════════════════════════════════════════════════
print("\nmediana")

checar("ímpar pega o do meio", mediana([1, 100, 3]) == 3.0)
checar("par tira a média dos dois do meio", mediana([2, 4]) == 3.0)
checar("vazio é None, não zero", mediana([]) is None)
checar("um caso extremo não arrasta a etapa", mediana([1, 3, 400]) == 3.0)


# ═══════════════════════════════════════════════════════════════════════════
print("\ncoorte: quem entra e quem fica de fora")

r = agregar_funil([
    # Entrou dentro da janela.
    Linha("A", None, "Lead", d("2026-02-01T10:00")),
    # Entrou ANTES da janela: outra safra, não conta — mesmo tendo avançado
    # dentro dela. É o ponto inteiro da análise por coorte.
    Linha("B", None, "Lead", d("2025-08-01T10:00")),
    Linha("B", "Lead", "Proposta", d("2026-03-01T10:00")),
], INICIO, FIM)
checar("só a empresa da safra entra na coorte", r["coorte"]["entraram"] == 1)
checar("quem entrou antes não engorda a etapa", etapa(r, "Lead")["alcancaram"] == 1)
checar("nem o avanço dele conta", etapa(r, "Proposta")["alcancaram"] == 0)


# ═══════════════════════════════════════════════════════════════════════════
print("\ntaxa de passagem")

r = agregar_funil([
    # Duas avançam de Lead, uma fica parada.
    Linha("A", None, "Lead", d("2026-02-01")),
    Linha("A", "Lead", "Em contato", d("2026-02-11")),
    Linha("B", None, "Lead", d("2026-02-01")),
    Linha("B", "Lead", "Em contato", d("2026-02-05")),
    Linha("C", None, "Lead", d("2026-02-01")),
], INICIO, FIM)
lead = etapa(r, "Lead")
checar("3 chegaram em Lead", lead["alcancaram"] == 3)
checar("2 avançaram", lead["avancaram"] == 2)
checar("taxa é 66,7%", lead["taxa_avanco"] == 66.7)
checar("1 continua parada", lead["parados"] == 1)
# A avançou em 10 dias (01/02 -> 11/02), B em 4 (01/02 -> 05/02): mediana 7.
checar("mediana de dias até avançar é 7", lead["dias_ate_avancar"] == 7.0, f'(veio {lead["dias_ate_avancar"]})')
checar("amostra de dias só conta quem avançou", lead["amostra_dias"] == 2)


# ═══════════════════════════════════════════════════════════════════════════
print("\npular etapa conta como avanço")

r = agregar_funil([
    # Lead direto para Proposta: as etapas do meio nunca foram alcançadas, mas
    # Lead avançou. Exigir a etapa IMEDIATAMENTE seguinte diria que este lead
    # não avançou, o que é falso.
    Linha("A", None, "Lead", d("2026-03-01")),
    Linha("A", "Lead", "Proposta", d("2026-03-10")),
], INICIO, FIM)
checar("Lead avançou mesmo pulando duas etapas", etapa(r, "Lead")["avancaram"] == 1)
checar("as etapas puladas seguem em zero", etapa(r, "Em contato")["alcancaram"] == 0)
checar("Proposta registra a chegada", etapa(r, "Proposta")["alcancaram"] == 1)


# ═══════════════════════════════════════════════════════════════════════════
print("\nretrocesso: a condição temporal do 'avançou'")

r = agregar_funil([
    # Chegou em Proposta, VOLTOU para "Em contato" e parou ali.
    # "Em contato" NÃO avançou: a passagem por Proposta é anterior à volta.
    # Sem a condição de tempo, o evento antigo contaria como avanço do novo.
    Linha("A", None, "Lead", d("2026-02-01")),
    Linha("A", "Lead", "Proposta", d("2026-02-10")),
    Linha("A", "Proposta", "Em contato", d("2026-02-20")),
], INICIO, FIM)
checar("retrocesso é contado", r["retrocessos"] == 1)
checar("'Em contato' não ganha avanço de evento anterior", etapa(r, "Em contato")["avancaram"] == 0)
checar("'Em contato' fica como parado", etapa(r, "Em contato")["parados"] == 1)
checar("Lead avançou (foi a Proposta depois de chegar)", etapa(r, "Lead")["avancaram"] == 1)

r = agregar_funil([
    # Voltou e subiu de novo: agora "Em contato" avançou de verdade.
    Linha("A", None, "Lead", d("2026-02-01")),
    Linha("A", "Lead", "Proposta", d("2026-02-10")),
    Linha("A", "Proposta", "Em contato", d("2026-02-20")),
    Linha("A", "Em contato", "Negociação", d("2026-03-02")),
], INICIO, FIM)
checar("depois de subir de novo, 'Em contato' avançou", etapa(r, "Em contato")["avancaram"] == 1)

r = agregar_funil([
    # Ida e volta pela MESMA etapa: chega em "Em contato" em 05/02, cai de volta
    # para Lead, volta a "Em contato" em 20/02 e só então avança, em 02/03.
    #
    # O tempo de "Em contato" tem de contar da PRIMEIRA chegada (05/02 -> 02/03
    # = 25 dias). Contar da última (20/02 -> 02/03 = 10) apagaria o mês inteiro
    # de retrabalho e faria a etapa parecer o dobro de eficiente do que é.
    Linha("A", None, "Lead", d("2026-02-01")),
    Linha("A", "Lead", "Em contato", d("2026-02-05")),
    Linha("A", "Em contato", "Lead", d("2026-02-08")),
    Linha("A", "Lead", "Em contato", d("2026-02-20")),
    Linha("A", "Em contato", "Proposta", d("2026-03-02")),
], INICIO, FIM)
checar("o tempo conta da PRIMEIRA chegada, expondo o retrabalho",
       etapa(r, "Em contato")["dias_ate_avancar"] == 25.0,
       f'(veio {etapa(r, "Em contato")["dias_ate_avancar"]})')
checar("a volta é contada como retrocesso", r["retrocessos"] == 1)
checar("voltar não faz a empresa ser contada duas vezes em Lead",
       etapa(r, "Lead")["alcancaram"] == 1)


# ═══════════════════════════════════════════════════════════════════════════
print("\nperda")

r = agregar_funil([
    Linha("A", None, "Lead", d("2026-02-01")),
    Linha("A", "Lead", "Proposta", d("2026-02-10")),
    Linha("A", "Proposta", "Perdido", d("2026-02-20")),
], INICIO, FIM)
checar("a perda é atribuída à etapa onde parou", etapa(r, "Proposta")["perdidos"] == 1)
checar("Lead não é penalizado: ele avançou", etapa(r, "Lead")["perdidos"] == 0)
checar("Lead conta como avanço", etapa(r, "Lead")["avancaram"] == 1)
checar("a coorte registra a perda", r["coorte"]["perderam"] == 1)
checar("perdido não vira etapa do funil", all(e["etapa"] != "Perdido" for e in r["etapas"]))
checar("parados não conta quem se perdeu", etapa(r, "Proposta")["parados"] == 0)


# ═══════════════════════════════════════════════════════════════════════════
print("\ndesfecho da coorte")

r = agregar_funil([
    Linha("A", None, "Lead", d("2026-02-01")),
    Linha("A", "Lead", "Fechado", d("2026-03-01")),
    Linha("B", None, "Lead", d("2026-02-01")),
    Linha("B", "Lead", "Perdido", d("2026-03-01")),
    Linha("C", None, "Lead", d("2026-02-01")),
], INICIO, FIM)
checar("fecharam 1", r["coorte"]["fecharam"] == 1)
checar("perderam 1", r["coorte"]["perderam"] == 1)
checar("1 segue em aberto", r["coorte"]["em_aberto"] == 1)
checar("taxa de fechamento da coorte é 33,3%", r["coorte"]["taxa_fechamento"] == 33.3)
checar("Fechado não tem taxa de avanço: é o fim do funil",
       etapa(r, "Fechado")["taxa_avanco"] is None)
checar("mas registra quem chegou lá", etapa(r, "Fechado")["alcancaram"] == 1)


# ═══════════════════════════════════════════════════════════════════════════
print("\nrascunho e transições")

r = agregar_funil([
    # Caminho da criação em massa pela busca: o rascunho não gera histórico, e a
    # primeira linha da empresa é a promoção para Lead.
    Linha("A", "Rascunho", "Lead", d("2026-02-01")),
    Linha("A", "Lead", "Em contato", d("2026-02-08")),
], INICIO, FIM)
checar("empresa que nasceu rascunho entra na coorte pelo Lead", r["coorte"]["entraram"] == 1)
checar("Rascunho não vira etapa alcançada", all(e["alcancaram"] <= 1 for e in r["etapas"]))
checar("a transição Rascunho->Lead aparece na lista",
       any(t["de"] == "Rascunho" and t["para"] == "Lead" for t in r["transicoes"]))

r = agregar_funil([
    Linha("A", None, "Lead", d("2026-02-01")),
], INICIO, FIM)
checar("status_anterior NULL vira '(entrada)'",
       r["transicoes"][0]["de"] == "(entrada)" and r["transicoes"][0]["para"] == "Lead")


# ═══════════════════════════════════════════════════════════════════════════
print("\nordem e bordas")

r = agregar_funil([
    # Linhas fora de ordem: a função reordena em vez de confiar num ORDER BY
    # que mora em outro arquivo.
    Linha("A", "Lead", "Proposta", d("2026-02-10")),
    Linha("A", None, "Lead", d("2026-02-01")),
], INICIO, FIM)
checar("reordena sozinha", r["coorte"]["entraram"] == 1 and etapa(r, "Lead")["avancaram"] == 1)

r = agregar_funil([], INICIO, FIM)
checar("sem dado nenhum não quebra", r["coorte"]["entraram"] == 0)
checar("taxa sem amostra é None, não 0%", etapa(r, "Lead")["taxa_avanco"] is None)
checar("taxa de fechamento sem coorte é None", r["coorte"]["taxa_fechamento"] is None)

r = agregar_funil([
    Linha("A", None, "Lead", INICIO),
    Linha("B", None, "Lead", FIM),
    Linha("C", None, "Lead", d("2025-12-31T23:59:59")),
], INICIO, FIM)
checar("as duas bordas da janela são inclusivas", r["coorte"]["entraram"] == 2)

r = agregar_funil([
    # Mesma data de chegada e de avanço: 0 dia, não negativo nem None.
    Linha("A", None, "Lead", d("2026-02-01T09:00")),
    Linha("A", "Lead", "Em contato", d("2026-02-01T17:00")),
], INICIO, FIM)
checar("avanço no mesmo dia conta como 0 dia", etapa(r, "Lead")["dias_ate_avancar"] == 0.0)


# ═══════════════════════════════════════════════════════════════════════════
print("\naviso de coorte imatura")

r = agregar_funil([
    Linha("A", None, "Lead", d("2026-06-01")),
    Linha("A", "Lead", "Em contato", d("2026-06-20")),
], datetime(2026, 6, 1), datetime(2026, 6, 30, 23, 59))
checar("janela de 1 mês com avanço de 19 dias avisa que é cedo",
       r["coorte"]["aviso_coorte_recente"] is True)

r = agregar_funil([
    Linha("A", None, "Lead", d("2026-02-01")),
    Linha("A", "Lead", "Em contato", d("2026-02-03")),
], INICIO, FIM)
checar("janela de 6 meses com avanço de 2 dias não avisa",
       r["coorte"]["aviso_coorte_recente"] is False)


# ═══════════════════════════════════════════════════════════════════════════
print()
if falhas:
    print(f"{len(falhas)} FALHA(S):")
    for f in falhas:
        print(f"  - {f}")
    raise SystemExit(1)
print("tudo verde")
