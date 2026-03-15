"""
ROBÔ AUTO-PROGRAMÁVEL v3 - Backend Flask com OCR via Claude API
"""

from flask import Flask, request, jsonify, send_from_directory
import json, os, re, math, random, base64, urllib.request, urllib.error
from datetime import datetime

try:
    from sympy import symbols, solve, simplify, expand, factor, Eq
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations,
        implicit_multiplication_application, convert_xor)
    TRANS = standard_transformations + (implicit_multiplication_application, convert_xor)
    SYMPY_OK = True
except:
    SYMPY_OK = False

app = Flask(__name__, static_folder=".")
ARQUIVO = "cerebro_robo.json"
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

def carregar():
    if os.path.exists(ARQUIVO):
        with open(ARQUIVO, encoding="utf-8") as f:
            return json.load(f)
    return {
        "conhecimento": [], "regras": [], "formulas": {},
        "respostas": {}, "funcoes": {}, "historico": [],
        "stats": {"conversas": 0, "aprendizagens": 0,
                  "criado": datetime.now().isoformat()}
    }

def salvar(mem):
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)

def ler_imagem_claude(image_b64, media_type):
    if not CLAUDE_API_KEY:
        return None, "ANTHROPIC_API_KEY nao configurada. Va em Environment Variables no Render e adicione sua chave."
    payload = json.dumps({
        "model": "claude-opus-4-6",
        "max_tokens": 1024,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": "Extraia TODO o texto desta imagem exatamente como esta escrito. Se houver equacoes matematicas, escreva em formato de texto (ex: x**2 + 2x = 0). Se houver formulas, escreva no formato: nome = expressao. Responda SOMENTE com o texto extraido, sem explicacoes adicionais."}
            ]
        }]
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json", "x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"].strip(), None
    except urllib.error.HTTPError as e:
        return None, f"Erro API: {e.code} - {e.read().decode()[:200]}"
    except Exception as e:
        return None, str(e)

def detectar_ensino(texto, mem):
    t = texto.strip()
    m = re.match(r'(?:regra[:\s]+)?se\s+(?:o\s+usu[aá]rio\s+(?:disser?|perguntar?|falar?)\s+)?["\']?(.+?)["\']?\s+(?:ent[aã]o|responda?|fa[çc]a?)\s+["\']?(.+)["\']?$', t, re.IGNORECASE)
    if m:
        gatilho, acao = m.group(1).strip().lower(), m.group(2).strip()
        mem["regras"].append({"gatilho": gatilho, "codigo": f'if {repr(gatilho)} in entrada.lower():\n    return {repr(acao)}', "descricao": t, "criada": datetime.now().isoformat()})
        mem["stats"]["aprendizagens"] += 1
        return f'Regra aprendida! Quando disser "{gatilho}", responderei "{acao}".'
    m = re.match(r'(?:f[oó]rmula[:\s]+|calcular?\s+)?([a-zA-ZÀ-ú\s]{3,}?)\s*=\s*(.+)', t, re.IGNORECASE)
    if m and not re.search(r'^\s*\d', m.group(1)):
        nome, expr = m.group(1).strip().lower(), m.group(2).strip()
        vars_expr = sorted(set(re.findall(r'\b([a-z])\b', expr)))
        mem["formulas"][nome] = {"expr": expr, "vars": vars_expr, "criada": datetime.now().isoformat()}
        mem["stats"]["aprendizagens"] += 1
        return f'Formula "{nome}" aprendida! Use: calcular {nome} com {" e ".join(f"{x}=?" for x in vars_expr)}'
    m = re.match(r'(?:quando|se)\s+(?:perguntarem|disserem|falarem)\s+["\']?(.+?)["\']?\s+(?:responda?|a\s+resposta\s+[eé]|diga)\s+["\']?(.+)["\']?$', t, re.IGNORECASE)
    if m:
        pergunta, resposta = m.group(1).strip().lower(), m.group(2).strip()
        mem["respostas"][pergunta] = resposta
        mem["stats"]["aprendizagens"] += 1
        return f'Aprendi! "{pergunta}" -> "{resposta}"'
    return None

def executar_regras(entrada, mem):
    for regra in mem.get("regras", []):
        try:
            code = "def _r(entrada):\n" + "".join(f"    {ln}\n" for ln in regra["codigo"].splitlines()) + "    return None\n_res = _r(entrada)\n"
            g = {}; exec(code, g)
            if g.get("_res"): return g["_res"]
        except: pass
    return None

def tentar_formula(entrada, mem):
    m = re.match(r'calcular?\s+(.+?)\s+com\s+(.+)', entrada, re.IGNORECASE)
    if not m: return None
    nome_p, params = m.group(1).strip().lower(), m.group(2).strip()
    formula = next((d for n, d in mem.get("formulas", {}).items() if nome_p in n or n in nome_p), None)
    if not formula: return None
    valores = {k: float(v) for k, v in re.findall(r'([a-zA-Z])\s*=\s*([\d\.]+)', params)}
    expr = formula["expr"]
    try:
        for var, val in valores.items(): expr = re.sub(rf'\b{var}\b', str(val), expr)
        expr = expr.replace("^","**").replace("pi", str(math.pi))
        r = eval(expr, {"__builtins__": {}, "math": math, "sqrt": math.sqrt, "pi": math.pi})
        r = int(r) if isinstance(r, float) and r == int(r) else round(float(r), 6)
        return f"Resultado ({nome_p}): {r}"
    except Exception as e: return f"Erro na formula: {e}"

def resolver_algebra(texto):
    if not SYMPY_OK: return None
    t = re.sub(r'resolv[ae]\s+|calcul[ae]\s+|simplifiq[ue]+\s+|fator[e]\s+|expand[ae]\s+|quanto\s*[eé]\s*', '', texto, flags=re.IGNORECASE).replace("^","**")
    op = "fatorar" if re.search(r'fator', texto, re.IGNORECASE) else "expandir" if re.search(r'expand', texto, re.IGNORECASE) else "simplificar"
    try:
        if "=" in t:
            l, r = t.split("=", 1)
            eq = Eq(parse_expr(l, transformations=TRANS), parse_expr(r, transformations=TRANS))
            var = sorted(eq.free_symbols, key=str)
            if not var: return "Verdadeiro" if eq.lhs == eq.rhs else "Falso"
            sol = solve(eq, var[0])
            return f"{var[0]} = {', '.join(str(s) for s in sol)}" if sol else "Sem solucao."
        expr = parse_expr(t, transformations=TRANS)
        r2 = factor(expr) if op=="fatorar" else expand(expr) if op=="expandir" else simplify(expr)
        if r2.is_number:
            v = float(r2); return str(int(v)) if v == int(v) else str(round(v,6))
        return str(r2)
    except: return None

def e_algebra(t):
    return any(re.search(p, t, re.IGNORECASE) for p in [r'[a-z]\s*[\+\-\*\/\=\^]', r'[\+\-\*\/\^=]\s*[a-z]', r'\d+\s*[a-zA-Z]', r'resolv[ae]', r'simplifiq', r'fator', r'expand', r'[\d]+\s*[\+\-\*\/]\s*[\d]+'])

def buscar(entrada, mem):
    el = entrada.strip().lower()
    if el in mem.get("respostas", {}): return mem["respostas"][el]
    for p, r in mem.get("respostas", {}).items():
        if p in el or el in p: return r
    palavras = set(el.split())
    melhor, score_max = None, 0
    for item in mem.get("conhecimento", []):
        pp = set(item["texto"].lower().split())
        sc = len(palavras & pp) / len(pp) if pp else 0
        if sc > score_max and sc >= 0.45: score_max = sc; melhor = item["texto"]
    return melhor

def _cerebro_resumo(mem):
    return {
        "conhecimento": len(mem["conhecimento"]),
        "regras": [{"gatilho": r["gatilho"], "descricao": r["descricao"]} for r in mem["regras"]],
        "formulas": {n: {"expr": d["expr"], "vars": d["vars"]} for n, d in mem["formulas"].items()},
        "respostas": mem["respostas"],
        "stats": mem["stats"]
    }

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    entrada = data.get("mensagem", "").strip()
    if not entrada: return jsonify({"resposta": "Diga algo!", "tipo": "erro"})
    mem = carregar()
    mem["stats"]["conversas"] += 1
    mem["historico"].append({"usuario": entrada, "t": datetime.now().isoformat()})
    r = detectar_ensino(entrada, mem)
    if r: salvar(mem); return jsonify({"resposta": r, "tipo": "aprendizado", "cerebro": _cerebro_resumo(mem)})
    r = executar_regras(entrada, mem)
    if r: mem["historico"].append({"robo": r, "t": datetime.now().isoformat()}); salvar(mem); return jsonify({"resposta": r, "tipo": "regra"})
    r = tentar_formula(entrada, mem)
    if r: mem["historico"].append({"robo": r, "t": datetime.now().isoformat()}); salvar(mem); return jsonify({"resposta": r, "tipo": "formula"})
    if e_algebra(entrada):
        r = resolver_algebra(entrada)
        if r:
            resp = f"Resultado: {r}"
            mem["conhecimento"].append({"texto": entrada, "t": datetime.now().isoformat()})
            salvar(mem); return jsonify({"resposta": resp, "tipo": "algebra"})
    mem["conhecimento"].append({"texto": entrada, "t": datetime.now().isoformat()})
    encontrado = buscar(entrada, mem)
    resp = f'Isso me lembra: "{encontrado}"' if encontrado and encontrado.lower() != entrada.lower() else random.choice(["Ainda nao sei isso. Me ensine!", "Nao encontrei na memoria.", "Pode me ensinar mais?"])
    mem["historico"].append({"robo": resp, "t": datetime.now().isoformat()}); salvar(mem)
    return jsonify({"resposta": resp, "tipo": "busca"})

@app.route("/api/imagem", methods=["POST"])
def imagem():
    data = request.json
    image_b64  = data.get("imagem", "")
    media_type = data.get("tipo", "image/jpeg")
    if not image_b64: return jsonify({"erro": "Nenhuma imagem recebida."}), 400
    texto_extraido, erro = ler_imagem_claude(image_b64, media_type)
    if erro: return jsonify({"erro": erro}), 500
    mem = carregar()
    mem["stats"]["conversas"] += 1
    resultado_ensino = detectar_ensino(texto_extraido, mem)
    if resultado_ensino:
        salvar(mem)
        return jsonify({"texto_extraido": texto_extraido, "aprendizado": resultado_ensino, "tipo": "aprendizado", "cerebro": _cerebro_resumo(mem)})
    if e_algebra(texto_extraido):
        r = resolver_algebra(texto_extraido)
        if r:
            mem["conhecimento"].append({"texto": texto_extraido, "t": datetime.now().isoformat()}); salvar(mem)
            return jsonify({"texto_extraido": texto_extraido, "aprendizado": f"Resolvi da imagem: {r}", "tipo": "algebra", "cerebro": _cerebro_resumo(mem)})
    mem["conhecimento"].append({"texto": texto_extraido, "t": datetime.now().isoformat()})
    mem["stats"]["aprendizagens"] += 1; salvar(mem)
    return jsonify({"texto_extraido": texto_extraido, "aprendizado": "Guardei o conteudo da imagem na memoria!", "tipo": "conhecimento", "cerebro": _cerebro_resumo(mem)})

@app.route("/api/cerebro")
def cerebro():
    return jsonify(_cerebro_resumo(carregar()))

if __name__ == "__main__":
    print("\n Robo iniciado! Acesse: http://localhost:5000\n")
    app.run(debug=False, port=5000)
