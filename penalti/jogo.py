#!/usr/bin/env python3
"""
⚽ Pênalti interativo do README — lucam05

Fluxo:
  1. O visitante clica num canto no README → abre uma issue com título "penalti|<canto>".
  2. O workflow .github/workflows/penalti.yml roda este script.
  3. O script sorteia o pulo do goleiro, atualiza penalti/estado.json,
     redesenha penalti/ultimo.svg e reescreve o bloco do placar no README.md.
  4. O workflow faz commit, comenta o resultado na issue e fecha a issue.

Segurança (entrada vem de usuários anônimos da internet!):
  - Título e autor chegam por variáveis de ambiente, nunca interpolados no shell.
  - Ambos são validados por regex estrita antes de qualquer uso.
  - Só stdlib do Python: nenhuma dependência para auditar.

Uso:
  TITULO="penalti|esquerda" AUTOR="fulano" python3 penalti/jogo.py
  python3 penalti/jogo.py --reset    # zera o placar e redesenha tudo
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────── Configuração ───────────────────────────
RAIZ = Path(__file__).resolve().parent.parent
ARQ_ESTADO = RAIZ / "penalti" / "estado.json"
ARQ_SVG = RAIZ / "penalti" / "ultimo.svg"
ARQ_README = RAIZ / "README.md"

MARCA_INICIO = "<!-- PENALTI:START -->"
MARCA_FIM = "<!-- PENALTI:END -->"

CANTOS = ("esquerda", "meio", "direita")
NOME_CANTO = {"esquerda": "↖️ Esquerda", "meio": "⬆️ Meio", "direita": "↗️ Direita"}

CHANCE_FORA = 0.08        # 8% de chance de isolar a bola
HISTORICO_MAX = 5         # quantas cobranças aparecem na tabela
ARTILHEIROS_MAX = 5       # tamanho do ranking

RE_TITULO = re.compile(r"^penalti\|(esquerda|meio|direita)$")
RE_USUARIO = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")  # regra do GitHub


# ─────────────────────────── Estado ───────────────────────────
def estado_vazio() -> dict:
    return {"cobrancas": 0, "gols": 0, "defesas": 0, "fora": 0,
            "ultimos": [], "artilheiros": {}}


def ler_estado() -> dict:
    if ARQ_ESTADO.exists():
        return json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))
    return estado_vazio()


def salvar_estado(estado: dict) -> None:
    ARQ_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")


# ─────────────────────────── Regra do jogo ───────────────────────────
def cobrar(canto: str, rng: random.Random) -> tuple[str, str]:
    """Retorna (canto_do_goleiro, resultado) com resultado em gol/defesa/fora."""
    goleiro = rng.choice(CANTOS)
    if rng.random() < CHANCE_FORA:
        return goleiro, "fora"
    return goleiro, ("defesa" if goleiro == canto else "gol")


def registrar(estado: dict, autor: str, canto: str, goleiro: str, resultado: str) -> None:
    estado["cobrancas"] += 1
    estado[{"gol": "gols", "defesa": "defesas", "fora": "fora"}[resultado]] += 1
    if resultado == "gol":
        estado["artilheiros"][autor] = estado["artilheiros"].get(autor, 0) + 1
    estado["ultimos"].insert(0, {
        "n": estado["cobrancas"], "autor": autor, "canto": canto,
        "goleiro": goleiro, "resultado": resultado,
        "data": datetime.now(timezone.utc).strftime("%d/%m/%Y"),
    })
    del estado["ultimos"][HISTORICO_MAX:]


# ─────────────────────────── SVG do último lance ───────────────────────────
def desenhar_svg(estado: dict) -> str:
    """Desenha o gol visto de frente com a bola e o goleiro do último lance."""
    W, H = 560, 300
    gx, gy, gw, gh = 90, 78, 380, 160            # trave
    x_canto = {"esquerda": gx + 70, "meio": gx + gw / 2, "direita": gx + gw - 70}

    ultimo = estado["ultimos"][0] if estado["ultimos"] else None
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#0b3d2e"/><stop offset="1" stop-color="#1f8a4c"/>'
        '</linearGradient></defs>',
        f'<rect width="{W}" height="{H}" rx="14" fill="url(#g)"/>',
    ]
    # faixas do gramado
    for i in range(0, W, 70):
        partes.append(f'<rect x="{i}" y="{gy + gh}" width="35" height="{H - gy - gh}" fill="#ffffff" opacity=".05"/>')
    # rede
    for x in range(gx, gx + gw + 1, 20):
        partes.append(f'<line x1="{x}" y1="{gy}" x2="{x}" y2="{gy + gh}" stroke="#ffffff" stroke-opacity=".18"/>')
    for y in range(gy, gy + gh + 1, 20):
        partes.append(f'<line x1="{gx}" y1="{y}" x2="{gx + gw}" y2="{y}" stroke="#ffffff" stroke-opacity=".18"/>')
    # trave
    partes.append(f'<path d="M{gx},{gy + gh} V{gy} H{gx + gw} V{gy + gh}" fill="none" '
                  f'stroke="#ffffff" stroke-width="7" stroke-linejoin="round"/>')
    partes.append(f'<line x1="20" y1="{gy + gh}" x2="{W - 20}" y2="{gy + gh}" stroke="#ffffff" stroke-opacity=".6" stroke-width="2"/>')

    fonte = 'font-family="Fira Code, Consolas, monospace"'
    if ultimo is None:
        partes.append(f'<text x="{W / 2}" y="{gy + gh / 2 + 8}" text-anchor="middle" fill="#ffffff" '
                      f'font-size="22" font-weight="700" {fonte}>Ninguém bateu ainda</text>')
        partes.append(f'<text x="{W / 2}" y="{H - 28}" text-anchor="middle" fill="#c8f7d1" '
                      f'font-size="15" {fonte}>Escolha um canto abaixo e seja o primeiro</text>')
    else:
        # goleiro (corpo + braços abertos), deslocado para o canto em que pulou
        kx = x_canto[ultimo["goleiro"]]
        ky = gy + gh - 55
        partes += [
            f'<g transform="translate({kx},{ky})">',
            '<line x1="-38" y1="-18" x2="38" y2="-18" stroke="#ffd60a" stroke-width="9" stroke-linecap="round"/>',
            '<rect x="-14" y="-28" width="28" height="48" rx="8" fill="#ffd60a"/>',
            '<circle cx="0" cy="-40" r="11" fill="#f1c27d"/>',
            '<line x1="-8" y1="20" x2="-14" y2="48" stroke="#111" stroke-width="7" stroke-linecap="round"/>',
            '<line x1="8" y1="20" x2="14" y2="48" stroke="#111" stroke-width="7" stroke-linecap="round"/>',
            '</g>',
        ]
        # bola: dentro do gol, nas mãos do goleiro ou por cima do travessão
        bx = x_canto[ultimo["canto"]]
        # na defesa a bola fica na luva (ponta do braço), não no rosto
        if ultimo["resultado"] == "defesa":
            bx, by = kx + 40, ky - 18
        else:
            by = {"gol": gy + 45, "fora": gy - 28}[ultimo["resultado"]]
        partes += [
            f'<circle cx="{bx}" cy="{by}" r="13" fill="#ffffff" stroke="#111" stroke-width="2"/>',
            f'<circle cx="{bx}" cy="{by}" r="4.5" fill="#111"/>',
        ]
        titulo = {"gol": "GOOOL!", "defesa": "DEFENDEU!", "fora": "ISOLOU!"}[ultimo["resultado"]]
        cor = {"gol": "#7CFC00", "defesa": "#ffd60a", "fora": "#ff6b6b"}[ultimo["resultado"]]
        partes.append(f'<text x="{W / 2}" y="36" text-anchor="middle" fill="{cor}" '
                      f'font-size="24" font-weight="800" {fonte}>{titulo}</text>')
        partes.append(f'<text x="{W / 2}" y="{H - 28}" text-anchor="middle" fill="#ffffff" font-size="15" {fonte}>'
                      f'@{ultimo["autor"]} · cobrança #{ultimo["n"]} · '
                      f'{plural(estado["gols"], "gol", "gols")} x '
                      f'{plural(estado["defesas"], "defesa", "defesas")}</text>')
    partes.append("</svg>")
    return "\n".join(partes) + "\n"


# ─────────────────────────── Bloco do README ───────────────────────────
def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"


def montar_bloco(estado: dict) -> str:
    linhas = [MARCA_INICIO, "",
              f'<p align="center"><img src="penalti/ultimo.svg?v={estado["cobrancas"]}" '
              f'width="520" alt="Último lance do pênalti"/></p>', ""]

    total = estado["cobrancas"]
    aproveitamento = f'{round(100 * estado["gols"] / total)}%' if total else "—"
    linhas += [f'<p align="center"><b>⚽ {plural(estado["gols"], "gol", "gols")} · '
               f'🧤 {plural(estado["defesas"], "defesa", "defesas")} · '
               f'🚀 {estado["fora"]} pra fora · 🎯 aproveitamento {aproveitamento}</b></p>', ""]

    if estado["ultimos"]:
        icone = {"gol": "⚽ Gol", "defesa": "🧤 Defesa", "fora": "🚀 Fora"}
        linhas += ["| # | Batedor | Chute | Goleiro | Resultado | Data |",
                   "|:-:|---|---|---|---|---|"]
        for c in estado["ultimos"]:
            linhas.append(f'| {c["n"]} | [@{c["autor"]}](https://github.com/{c["autor"]}) | '
                          f'{NOME_CANTO[c["canto"]]} | {NOME_CANTO[c["goleiro"]]} | '
                          f'{icone[c["resultado"]]} | {c["data"]} |')
        linhas.append("")

    if estado["artilheiros"]:
        ranking = sorted(estado["artilheiros"].items(), key=lambda kv: (-kv[1], kv[0]))[:ARTILHEIROS_MAX]
        medalhas = ["🥇", "🥈", "🥉", "4º", "5º"]
        # Dentro de <p> o GitHub não interpreta Markdown, então o link vai em HTML
        texto = " · ".join(f'{medalhas[i]} <a href="https://github.com/{u}">@{u}</a> ({g})'
                           for i, (u, g) in enumerate(ranking))
        linhas += [f'<p align="center"><b>🏆 Artilharia:</b> {texto}</p>', ""]

    linhas.append(MARCA_FIM)
    return "\n".join(linhas)


def atualizar_readme(estado: dict) -> None:
    conteudo = ARQ_README.read_text(encoding="utf-8")
    padrao = re.compile(re.escape(MARCA_INICIO) + r".*?" + re.escape(MARCA_FIM), re.S)
    if not padrao.search(conteudo):
        sys.exit("README.md sem os marcadores PENALTI:START/END")
    ARQ_README.write_text(padrao.sub(lambda _: montar_bloco(estado), conteudo), encoding="utf-8")


def salvar_tudo(estado: dict) -> None:
    salvar_estado(estado)
    ARQ_SVG.write_text(desenhar_svg(estado), encoding="utf-8")
    atualizar_readme(estado)


# ─────────────────────────── Saída para o workflow ───────────────────────────
def saida_workflow(resultado: str, mensagem: str) -> None:
    """Escreve outputs no formato do GitHub Actions (aceita mensagem multilinha)."""
    caminho = os.environ.get("GITHUB_OUTPUT")
    if caminho:
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(f"resultado={resultado}\n")
            f.write(f"mensagem<<FIM_MENSAGEM\n{mensagem}\nFIM_MENSAGEM\n")
    print(f"[{resultado}]\n{mensagem}")


def main() -> None:
    if "--reset" in sys.argv:
        salvar_tudo(estado_vazio())
        print("Placar zerado.")
        return

    titulo = os.environ.get("TITULO", "").strip().lower()
    autor = os.environ.get("AUTOR", "").strip()

    m = RE_TITULO.match(titulo)
    if not m or not RE_USUARIO.match(autor):
        saida_workflow("invalido", "🤔 Não entendi essa cobrança. Use um dos links do README "
                                   "(esquerda, meio ou direita) sem mudar o título da issue.")
        return

    canto = m.group(1)
    goleiro, resultado = cobrar(canto, random.SystemRandom())
    estado = ler_estado()
    registrar(estado, autor, canto, goleiro, resultado)
    salvar_tudo(estado)

    frase = {
        "gol": f"⚽ **GOOOL!** Você bateu no canto **{NOME_CANTO[canto]}** e o goleiro foi pro **{NOME_CANTO[goleiro]}**.",
        "defesa": f"🧤 **DEFENDEU!** O goleiro adivinhou o canto **{NOME_CANTO[canto]}**. Tenta de novo!",
        "fora": "🚀 **ISOLOU!** A bola foi parar na arquibancada. Acontece até com os melhores.",
    }[resultado]
    mensagem = (f"{frase}\n\n"
                f"Placar geral: **{plural(estado['gols'], 'gol', 'gols')}** x "
                f"**{plural(estado['defesas'], 'defesa', 'defesas')}** "
                f"em {estado['cobrancas']} cobranças.\n\n"
                f"Seu lance já está no [perfil do Luca](https://github.com/lucam05). Valeu pela visita! 👋")
    saida_workflow(resultado, mensagem)


if __name__ == "__main__":
    main()
