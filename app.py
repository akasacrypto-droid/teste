"""
ROBÔ AUTO-PROGRAMÁVEL v3 - Backend Flask
=========================================
Instalação:
  pip install flask colorama sympy pyttsx3

Uso:
  python app.py
  Abra: http://localhost:5000
"""

from flask import Flask, request, jsonify, send_from_directory
import json, os, re, math, random, threading
from datetime import datetime

try:
    import pyttsx3
    _engine = pyttsx3.init()
    _engine.setProperty("rate", 155)
    for v in _engine.getProperty("voices"):
        if any(k in v.id.lower() for k in ("brazil","portuguese","pt_br","pt-br")):
            _engine.setProperty("voice", v.id); break
    VOZ_OK = True
except:
    VOZ_OK = False

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

# ── memória ────────────────────────────────────────────────────────────────
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

# ── voz ────────────────────────────────────────────────────────────────────
def falar(texto):
    if not VOZ_OK: return
    def _f():
        try: _engine.say(texto); _engine.runAndWait()
        except: pass
    threading.Thread(target=_f, daemon=True).start()

# ── detectar ensino ────────────────────────────────────────────────────────
def detectar_ensino(texto, mem):
    t = texto.strip()

    # REGRA condicional
    m = re.match(
        r'(?:regra[:\s]+)?se\s+(?:o\s+usu[aá]rio\s+(?:disser?|perguntar?|falar?)\s+)?["\']?(.+?)["\']?\s+'
        r'(?:ent[aã]o|responda?|fa[çc]a?)\s+["\']?(.+)["\']?$',
        t, re.IGNORECASE)
    if m:
        gatilho = m.group(1).strip().lower()
        acao    = m.group(2).strip()
        codigo  = f'if {repr(gatilho)} in entrada.lower():\n    return {repr(acao)}'
        mem["regras"].append({"gatilho": gatilho, "codigo": codigo,
                               "descricao": t, "criada": datetime.now().isoformat()})
        mem["stats"]["aprendizagens"] += 1
        return f'✅ Regra aprendida! Quando você disser "{gatilho}", responderei "{acao}".'

    # FÓRMULA
    m = re.match(r'(?:f[oó]rmula[:\s]+|calcular?\s+)?([a-zA-ZÀ-ú\s]{3,}?)\s*=\s*(.+)', t, re.IGNORECASE)
    if m and not re.search(r'^\s*\d', m.group(1)):
        nome = m.group(1).strip().lower()
        expr = m.group(2).strip()
        vars_expr = sorted(set(re.findall(r'\b([a-z])\b', expr)))
        mem["formulas"][nome] = {"expr": expr, "vars": vars_expr,
                                  "criada": datetime.now().isoformat()}
        mem["stats"]["aprendizagens"] += 1
        v = ", ".join(vars_expr) if vars_expr else "nenhuma"
        return f'📐 Fórmula "{nome}" aprendida! Variáveis: {v}. Use: calcular {nome} com {" e ".join(f"{x}=?" for x in vars_expr)}'

    # RESPOSTA DIRETA
    m = re.match(
        r'(?:quando|se)\s+(?:perguntarem|disserem|falarem)\s+["\']?(.+?)["\']?\s+'
        r'(?:responda?|a\s+resposta\s+[eé]|diga)\s+["\']?(.+)["\']?$',
        t, re.IGNORECASE)
    if m:
        pergunta = m.group(1).strip().lower()
        resposta = m.group(2).strip()
        mem["respostas"][pergunta] = resposta
        mem["stats"]["aprendizagens"] += 1
        return f'💬 Aprendi! "{pergunta}" → "{resposta}"'

    return None

# ── executar regras ─────────────────────────────────────────────────────────
def executar_regras(entrada, mem):
    for regra in mem.get("regras", []):
        try:
            code = f"def _r(entrada):\n"
            for ln in regra["codigo"].splitlines():
                code += f"    {ln}\n"
            code += "    return None\n_res = _r(entrada)\n"
            g = {}; exec(code, g)
            if g.get("_res"): return g["_res"]
        except: pass
    return None

# ── fórmula aprendida ────────────────────────────────────────────────────────
def tentar_formula(entrada, mem):
    m = re.match(r'calcular?\s+(.+?)\s+com\s+(.+)', entrada, re.IGNORECASE)
    if not m: return None
    nome_p = m.group(1).strip().lower()
    params = m.group(2).strip()
    formula = next((d for n, d in mem.get("formulas", {}).items()
                    if nome_p in n or n in nome_p), None)
    if not formula: return None
    pares = re.findall(r'([a-zA-Z])\s*=\s*([\d\.]+)', params)
    valores = {k: float(v) for k, v in pares}
    expr = formula["expr"]
    try:
        for var, val in valores.items():
            expr = re.sub(rf'\b{var}\b', str(val), expr)
        expr = expr.replace("^","**").replace("pi", str(math.pi))
        r = eval(expr, {"__builtins__": {}, "math": math,
                         "sqrt": math.sqrt, "pi": math.pi})
        r = int(r) if isinstance(r, float) and r == int(r) else round(float(r), 6)
        return f"📐 Resultado ({nome_p}): {r}"
    except Exception as e:
        return f"Erro na fórmula: {e}"

# ── álgebra ──────────────────────────────────────────────────────────────────
def resolver_algebra(texto):
    if not SYMPY_OK: return None
    t = re.sub(r'resolv[ae]\s+|calcul[ae]\s+|simplifiq[ue]+\s+|fator[e]\s+|expand[ae]\s+|quanto\s*[eé]\s*',
               '', texto, flags=re.IGNORECASE).replace("^","**")
    op = ("fatorar" if re.search(r'fator', texto, re.IGNORECASE)
          else "expandir" if re.search(r'expand', texto, re.IGNORECASE) else "simplificar")
    try:
        if "=" in t:
            l, r = t.split("=", 1)
            esq = parse_expr(l, transformations=TRANS)
            dir_ = parse_expr(r, transformations=TRANS)
            eq = Eq(esq, dir_)
            var = sorted(eq.free_symbols, key=str)
            if not var: return "Verdadeiro" if esq == dir_ else "Falso"
            sol = solve(eq, var[0])
            return f"{var[0]} = {', '.join(str(s) for s in sol)}" if sol else "Sem solução."
        expr = parse_expr(t, transformations=TRANS)
        r2 = factor(expr) if op=="fatorar" else expand(expr) if op=="expandir" else simplify(expr)
        if r2.is_number:
            v = float(r2); return str(int(v)) if v == int(v) else str(round(v,6))
        return str(r2)
    except: return None

def e_algebra(t):
    return any(re.search(p, t, re.IGNORECASE) for p in [
        r'[a-z]\s*[\+\-\*\/\=\^]', r'[\+\-\*\/\^=]\s*[a-z]',
        r'\d+\s*[a-zA-Z]', r'resolv[ae]', r'simplifiq', r'fator',
        r'expand', r'[\d]+\s*[\+\-\*\/]\s*[\d]+'])

# ── buscar memória ────────────────────────────────────────────────────────────
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
        if sc > score_max and sc >= 0.45:
            score_max = sc; melhor = item["texto"]
    return melhor

# ── ROTAS ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data    = request.json
    entrada = data.get("mensagem", "").strip()
    if not entrada:
        return jsonify({"resposta": "Diga algo!", "tipo": "erro"})

    mem = carregar()
    mem["stats"]["conversas"] += 1
    mem["historico"].append({"usuario": entrada, "t": datetime.now().isoformat()})

    # ensino
    r = detectar_ensino(entrada, mem)
    if r:
        salvar(mem); falar(r)
        return jsonify({"resposta": r, "tipo": "aprendizado", "stats": mem["stats"],
                        "cerebro": _cerebro_resumo(mem)})

    # regras
    r = executar_regras(entrada, mem)
    if r:
        mem["historico"].append({"robo": r, "t": datetime.now().isoformat()})
        salvar(mem); falar(r)
        return jsonify({"resposta": r, "tipo": "regra", "stats": mem["stats"]})

    # fórmula
    r = tentar_formula(entrada, mem)
    if r:
        mem["historico"].append({"robo": r, "t": datetime.now().isoformat()})
        salvar(mem); falar(r)
        return jsonify({"resposta": r, "tipo": "formula", "stats": mem["stats"]})

    # álgebra
    if e_algebra(entrada):
        r = resolver_algebra(entrada)
        if r:
            resp = f"Resultado: {r}"
            mem["conhecimento"].append({"texto": entrada, "t": datetime.now().isoformat()})
            mem["historico"].append({"robo": resp, "t": datetime.now().isoformat()})
            salvar(mem); falar(resp)
            return jsonify({"resposta": resp, "tipo": "algebra", "stats": mem["stats"]})

    # memória
    mem["conhecimento"].append({"texto": entrada, "t": datetime.now().isoformat()})
    encontrado = buscar(entrada, mem)
    nao_sei = ["Ainda não sei isso. Me ensine uma regra ou fórmula!",
                "Hmm, não encontrei isso na memória.",
                "Pode me ensinar mais sobre isso?"]
    resp = f'Isso me lembra: "{encontrado}"' if encontrado and encontrado.lower() != entrada.lower() \
           else random.choice(nao_sei)
    mem["historico"].append({"robo": resp, "t": datetime.now().isoformat()})
    salvar(mem); falar(resp)
    return jsonify({"resposta": resp, "tipo": "busca", "stats": mem["stats"]})

@app.route("/api/cerebro")
def cerebro():
    mem = carregar()
    return jsonify(_cerebro_resumo(mem))

@app.route("/api/stats")
def stats():
    mem = carregar()
    return jsonify(mem["stats"])

def _cerebro_resumo(mem):
    return {
        "conhecimento": len(mem["conhecimento"]),
        "regras": [{"gatilho": r["gatilho"], "descricao": r["descricao"]} for r in mem["regras"]],
        "formulas": {n: {"expr": d["expr"], "vars": d["vars"]} for n, d in mem["formulas"].items()},
        "respostas": mem["respostas"],
        "stats": mem["stats"]
    }

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    print("\n🤖 Robô iniciado! Acesse: http://localhost:5000\n")
    app.run(debug=False, port=5000)
