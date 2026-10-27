#!/usr/bin/env python3
"""
📈 Cards de estatísticas do README — gerados pelo próprio repositório.

Substitui o github-readme-stats (instância pública que vive fora do ar ou
estourando o limite da API). O workflow .github/workflows/stats.yml roda este
script uma vez por dia, e ele:

  1. consulta a API GraphQL do GitHub com o token do próprio Action;
  2. gera stats/stats.svg (números do último ano) e stats/linguagens.svg;
  3. o workflow commita os SVGs, que o README exibe por caminho relativo.

Só usa a biblioteca padrão do Python.

Uso:
  GITHUB_TOKEN=xxx USUARIO=lucam05 python3 stats/gerar_stats.py
  python3 stats/gerar_stats.py --fixture dados.json   # testa sem chamar a API
"""

from __future__ import annotations

import html
import json
import os
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

PASTA = Path(__file__).resolve().parent

# Paleta do perfil (mesmo verde do banner e do pênalti)
FUNDO_1, FUNDO_2 = "#0b3d2e", "#1f8a4c"
TITULO, TEXTO, DESTAQUE = "#ffffff", "#e6e6e6", "#7CFC00"
FONTE = "Segoe UI, Ubuntu, Helvetica, Arial, sans-serif"

LINGUAGENS_MAX = 6
IGNORAR_LINGUAGENS = {"Jupyter Notebook"}  # adicione aqui o que não quiser contar

CONSULTA = """
query($login: String!) {
  user(login: $login) {
    name
    login
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100,
                 orderBy: {field: UPDATED_AT, direction: DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


# ─────────────────────────── Coleta ───────────────────────────
def buscar_dados(usuario: str, token: str) -> dict:
    corpo = json.dumps({"query": CONSULTA, "variables": {"login": usuario}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=corpo,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "readme-stats-lucam05"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        dados = json.load(resp)
    if "errors" in dados:
        sys.exit(f"Erro da API do GitHub: {dados['errors']}")
    return dados["data"]["user"]


def resumir(u: dict) -> dict:
    """Transforma a resposta da API nos números que os cards mostram."""
    contrib = u["contributionsCollection"]
    repos = u["repositories"]["nodes"]

    bytes_por_ling: dict[str, int] = defaultdict(int)
    cor_por_ling: dict[str, str] = {}
    for repo in repos:
        for aresta in repo["languages"]["edges"]:
            nome = aresta["node"]["name"]
            if nome in IGNORAR_LINGUAGENS:
                continue
            bytes_por_ling[nome] += aresta["size"]
            cor_por_ling[nome] = aresta["node"]["color"] or "#8b949e"

    total = sum(bytes_por_ling.values()) or 1
    ranking = sorted(bytes_por_ling.items(), key=lambda kv: -kv[1])[:LINGUAGENS_MAX]

    return {
        "nome": u["name"] or u["login"],
        "contribuicoes": contrib["contributionCalendar"]["totalContributions"],
        "commits": contrib["totalCommitContributions"] + contrib["restrictedContributionsCount"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "estrelas": sum(r["stargazerCount"] for r in repos),
        "repos": u["repositories"]["totalCount"],
        "seguidores": u["followers"]["totalCount"],
        "linguagens": [(n, cor_por_ling[n], 100 * b / total) for n, b in ranking],
    }


# ─────────────────────────── Desenho ───────────────────────────
def moldura(largura: int, altura: int, titulo: str, miolo: list[str]) -> str:
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" role="img" aria-label="{html.escape(titulo)}">',
        '<defs><linearGradient id="f" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{FUNDO_1}"/><stop offset="1" stop-color="{FUNDO_2}"/>'
        '</linearGradient></defs>',
        f'<rect width="{largura}" height="{altura}" rx="12" fill="url(#f)"/>',
        f'<text x="24" y="38" fill="{TITULO}" font-family="{FONTE}" font-size="18" '
        f'font-weight="700">{html.escape(titulo)}</text>',
        *miolo,
        "</svg>",
    ]) + "\n"


def card_stats(r: dict) -> str:
    itens = [
        ("Contribuições (último ano)", r["contribuicoes"]),
        ("Commits (último ano)", r["commits"]),
        ("Pull requests", r["prs"]),
        ("Issues", r["issues"]),
        ("Repositórios", r["repos"]),
        ("Estrelas recebidas", r["estrelas"]),
    ]
    miolo = []
    for i, (rotulo, valor) in enumerate(itens):
        y = 72 + i * 25
        miolo += [
            f'<circle cx="30" cy="{y - 5}" r="4" fill="{DESTAQUE}"/>',
            f'<text x="44" y="{y}" fill="{TEXTO}" font-family="{FONTE}" font-size="14">{rotulo}</text>',
            f'<text x="326" y="{y}" fill="{TITULO}" font-family="{FONTE}" font-size="14" '
            f'font-weight="700" text-anchor="end">{valor}</text>',
        ]
    return moldura(350, 225, f"Temporada de {r['nome'].split()[0]}", miolo)


def card_linguagens(r: dict) -> str:
    largura_barra = 252
    miolo, x = [], 24.0
    # barra empilhada no topo, com clip para cantos arredondados
    miolo.append('<clipPath id="b"><rect x="24" y="56" width="252" height="10" rx="5"/></clipPath>')
    miolo.append('<g clip-path="url(#b)">')
    for _, cor, pct in r["linguagens"]:
        w = largura_barra * pct / 100
        miolo.append(f'<rect x="{x:.2f}" y="56" width="{w:.2f}" height="10" fill="{cor}"/>')
        x += w
    miolo.append("</g>")
    # legenda em duas colunas
    for i, (nome, cor, pct) in enumerate(r["linguagens"]):
        cx = 24 + (i % 2) * 130
        cy = 96 + (i // 2) * 28
        miolo += [
            f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{cor}"/>',
            f'<text x="{cx + 16}" y="{cy}" fill="{TEXTO}" font-family="{FONTE}" font-size="13">'
            f'{html.escape(nome)} <tspan fill="{TITULO}" font-weight="700">{pct:.1f}%</tspan></text>',
        ]
    if not r["linguagens"]:
        miolo.append(f'<text x="24" y="100" fill="{TEXTO}" font-family="{FONTE}" font-size="13">'
                     'Nenhum código público ainda</text>')
    return moldura(300, 225, "Linguagens mais usadas", miolo)


# ─────────────────────────── Main ───────────────────────────
def main() -> None:
    if "--fixture" in sys.argv:
        bruto = json.loads(Path(sys.argv[sys.argv.index("--fixture") + 1]).read_text(encoding="utf-8"))
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("Defina GITHUB_TOKEN (no Action ele já vem pronto).")
        bruto = buscar_dados(os.environ.get("USUARIO", "lucam05"), token)

    resumo = resumir(bruto)
    (PASTA / "stats.svg").write_text(card_stats(resumo), encoding="utf-8")
    (PASTA / "linguagens.svg").write_text(card_linguagens(resumo), encoding="utf-8")
    print(json.dumps({k: v for k, v in resumo.items() if k != "linguagens"}, ensure_ascii=False))
    print("Linguagens:", ", ".join(f"{n} {p:.1f}%" for n, _, p in resumo["linguagens"]))


if __name__ == "__main__":
    main()
