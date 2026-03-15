"""
ROBÔ AUTO-PROGRAMÁVEL v4 - Aprendizado 100% local via JSON
"""
from flask import Flask, request, jsonify, send_from_directory
import json, os, re, math, random
from datetime import datetime

try:
    from sympy import solve, simplify, expand, factor, Eq
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations,
        implicit_multiplication_application, convert_xor)
    TRANS = standard_transformations + (implicit_multiplication_application, convert_xor)
    SYMPY_OK = True
except:
    SYMPY_OK = False

app = Flask(__name__, static_folder=".")
ARQUIVO = "cerebro_robo.json"

# ══════════════════════════════════════════════════════
#  MEMÓRIA
# ══════════════════════════════════════════════════════
def carregar():
    if os.path.exists(ARQUIVO):
        with open(ARQUIVO, encoding="utf-8") as f:
            return json.load(f)
    return {
        "fatos": {},        # chave → valor (aprendizado livre)
        "regras": [],       # [{gatilho, resposta}]
        "formulas": {},     # nome → {expr, vars}
        "conhecimento": [], # textos brutos guardados
        "stats": {"conversas": 0, "aprendizagens": 0, "criado": datetime.now().isoformat()}
    }

def salvar(mem):
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)

def resumo(mem):
    return {
        "fatos": len(mem.get("fatos", {})),
        "regras": mem.get("regras", []),
        "formulas": {n: {"expr": d["expr"], "vars": d["vars"]} for n, d in mem.get("formulas", {}).items()},
        "stats": mem["stats"]
    }

# ══════════════════════════════════════════════════════
#  NORMALIZAÇÃO
# ══════════════════════════════════════════════════════
def norm(t): return t.strip().lower()

def extrair_chave(texto):
    """Remove palavras interrogativas e artigos para gerar uma chave limpa."""
    t = norm(texto)
    t = re.sub(r'^(qual|quem|onde|quando|como|quanto|o que|me diz|diga|voce sabe|sabe me dizer|oque)[eé\s]+[eé]?\s*', '', t)
    t = re.sub(r'^(o|a|os|as|um|uma)\s+', '', t)
    t = re.sub(r'\?$', '', t).strip()
    return t

# ══════════════════════════════════════════════════════
#  DETECÇÃO DE PADRÕES DE ENSINO
# ══════════════════════════════════════════════════════
def detectar_ensino(texto, mem):
    t = texto.strip()
    tl = norm(t)

    # ── 1. "X é Y" / "X significa Y" / "X quer dizer Y" ──────────────────
    m = re.match(r'^(.+?)\s+(?:é|e|significa|quer dizer|=)\s+(.+)$', t, re.IGNORECASE)
    if m:
        chave = norm(m.group(1))
        valor = m.group(2).strip()
        # evita fórmulas matemáticas aqui
        if not re.search(r'[\+\-\*\/\^]', valor) or len(valor) > 40:
            mem["fatos"][chave] = valor
            mem["stats"]["aprendizagens"] += 1
            return f'✅ Guardei: "{chave}" → "{valor}"', "aprendizado"

    # ── 2. "quando/se X então/responda Y" ─────────────────────────────────
    m = re.match(r'(?:quando|se)\s+(?:eu\s+)?(?:disser?|perguntar?|falar?)\s*["\']?(.+?)["\']?\s+(?:ent[aã]o|responda?|diga|fale)\s*["\']?(.+)["\']?$', t, re.IGNORECASE)
    if m:
        gatilho = norm(m.group(1))
        resposta = m.group(2).strip()
        # remove duplicatas
        mem["regras"] = [r for r in mem.get("regras", []) if r["gatilho"] != gatilho]
        mem["regras"].append({"gatilho": gatilho, "resposta": resposta})
        mem["stats"]["aprendizagens"] += 1
        return f'✅ Regra aprendida! Quando você disser "{gatilho}", responderei "{resposta}".', "aprendizado"

    # ── 3. Fórmula: "nome = expressão" (com letras variáveis) ─────────────
    m = re.match(r'^([a-zA-ZÀ-ú][\w\sÀ-ú]{2,40}?)\s*=\s*(.+)$', t, re.IGNORECASE)
    if m:
        nome = norm(m.group(1))
        expr = m.group(2).strip()
        vars_expr = sorted(set(re.findall(r'\b([a-zA-Z])\b', expr)))
        # só salva como fórmula se tiver variáveis ou operadores
        if vars_expr or re.search(r'[\+\-\*\/\^]', expr):
            mem["formulas"][nome] = {"expr": expr, "vars": vars_expr, "criada": datetime.now().isoformat()}
            mem["stats"]["aprendizagens"] += 1
            uso = f"calcular {nome} com {' e '.join(f'{v}=?' for v in vars_expr)}" if vars_expr else f"calcular {nome}"
            return f'📐 Fórmula "{nome}" aprendida! Use: {uso}', "aprendizado"

    # ── 4. Texto longo → guarda como conhecimento ─────────────────────────
    if len(t) > 60:
        # extrai possíveis fatos do texto longo
        fatos_extraidos = 0
        sentencas = re.split(r'[.!;\n]', t)
        for s in sentencas:
            s = s.strip()
            mm = re.match(r'^(.+?)\s+(?:é|significa|quer dizer)\s+(.+)$', s, re.IGNORECASE)
            if mm and len(mm.group(1)) < 60:
                mem["fatos"][norm(mm.group(1))] = mm.group(2).strip()
                fatos_extraidos += 1
        mem["conhecimento"].append({"texto": t, "t": datetime.now().isoformat()})
        mem["stats"]["aprendizagens"] += 1
        msg = f'📚 Guardei esse conhecimento! Extraí {fatos_extraidos} fato(s) automaticamente.' if fatos_extraidos else '📚 Guardei esse conhecimento na memória!'
        return msg, "aprendizado"

    return None, None

# ══════════════════════════════════════════════════════
#  BUSCA NA MEMÓRIA
# ══════════════════════════════════════════════════════
def buscar_resposta(entrada, mem):
    el = norm(entrada)
    chave = extrair_chave(entrada)

    # 1. Regras exatas
    for r in mem.get("regras", []):
        if r["gatilho"] in el or el in r["gatilho"]:
            return r["resposta"], "regra"

    # 2. Fatos exatos
    if chave in mem.get("fatos", {}):
        return mem["fatos"][chave], "fato"

    # 3. Fatos parciais (qualquer palavra da chave bate)
    palavras_chave = set(chave.split())
    melhor_fato, melhor_score = None, 0
    for k, v in mem.get("fatos", {}).items():
        palavras_k = set(k.split())
        inter = palavras_chave & palavras_k
        score = len(inter) / max(len(palavras_k), 1)
        if score > melhor_score and score >= 0.5:
            melhor_score = score
            melhor_fato = v
    if melhor_fato:
        return melhor_fato, "fato"

    # 4. Busca no conhecimento bruto
    palavras = set(el.split())
    melhor_texto, melhor_sc = None, 0
    for item in mem.get("conhecimento", []):
        pp = set(item["texto"].lower().split())
        sc = len(palavras & pp) / max(len(pp), 1)
        if sc > melhor_sc and sc >= 0.3:
            melhor_sc = sc
            melhor_texto = item["texto"]
    if melhor_texto:
        trecho = melhor_texto[:300] + ("..." if len(melhor_texto) > 300 else "")
        return f'Encontrei isso na memória:\n"{trecho}"', "conhecimento"

    return None, None

# ══════════════════════════════════════════════════════
#  ÁLGEBRA
# ══════════════════════════════════════════════════════
def resolver_algebra(texto):
    if not SYMPY_OK: return None
    t = re.sub(r'resolv[ae]\s+|calcul[ae]\s+|simplifiq[ue]+\s+|fator[e]\s+|expand[ae]\s+|quanto\s*[eé]\s*', '', texto, flags=re.IGNORECASE)
    t = t.strip().replace("^","**")
    op = "fatorar" if re.search(r'fator', texto, re.IGNORECASE) else "expandir" if re.search(r'expand', texto, re.IGNORECASE) else "simplificar"
    try:
        if "=" in t:
            l, r = t.split("=", 1)
            eq = Eq(parse_expr(l, transformations=TRANS), parse_expr(r, transformations=TRANS))
            var = sorted(eq.free_symbols, key=str)
            if not var: return "Verdadeiro" if eq.lhs == eq.rhs else "Falso"
            sol = solve(eq, var[0])
            return f"{var[0]} = {', '.join(str(s) for s in sol)}" if sol else "Sem solução."
        expr = parse_expr(t, transformations=TRANS)
        r2 = factor(expr) if op=="fatorar" else expand(expr) if op=="expandir" else simplify(expr)
        if r2.is_number:
            v = float(r2); return str(int(v)) if v == int(v) else str(round(v, 6))
        return str(r2)
    except: return None

def e_algebra(t):
    return any(re.search(p, t, re.IGNORECASE) for p in [
        r'[a-zA-Z]\s*[\+\-\*\/\=\^]', r'[\+\-\*\/\^=]\s*[a-zA-Z]',
        r'\d+[a-zA-Z]', r'resolv[ae]', r'simplifiq', r'fator', r'expand',
        r'\d+\s*[\+\-\*\/]\s*\d+'])

def tentar_formula(entrada, mem):
    m = re.match(r'calcular?\s+(.+?)\s+com\s+(.+)', entrada, re.IGNORECASE)
    if not m:
        # tenta "X de Y" como "calcular X com y=Y"
        m2 = re.match(r'(?:calcular?|quanto [eé])\s+(.+)', entrada, re.IGNORECASE)
        if m2:
            nome_p = norm(m2.group(1))
            formula = next((d for n, d in mem.get("formulas", {}).items() if nome_p in n or n in nome_p), None)
            if formula and not formula["vars"]:
                try:
                    expr = formula["expr"].replace("^","**").replace("pi", str(math.pi))
                    r = eval(expr, {"__builtins__": {}, "math": math, "sqrt": math.sqrt, "pi": math.pi})
                    return f"Resultado: {int(r) if float(r)==int(r) else round(float(r),6)}"
                except: pass
        return None
    nome_p = norm(m.group(1))
    params = m.group(2)
    formula = next((d for n, d in mem.get("formulas", {}).items() if nome_p in n or n in nome_p), None)
    if not formula: return None
    valores = {k: float(v) for k, v in re.findall(r'([a-zA-Z])\s*=\s*([\d\.]+)', params)}
    expr = formula["expr"]
    try:
        for var, val in valores.items(): expr = re.sub(rf'\b{var}\b', str(val), expr)
        expr = expr.replace("^","**").replace("pi", str(math.pi))
        r = eval(expr, {"__builtins__": {}, "math": math, "sqrt": math.sqrt, "pi": math.pi})
        return f"Resultado de {nome_p}: {int(r) if isinstance(r,float) and r==int(r) else round(float(r),6)}"
    except Exception as e: return f"Erro na fórmula: {e}"

# ══════════════════════════════════════════════════════
#  ROTAS
# ══════════════════════════════════════════════════════
@app.route("/")
def index(): return send_from_directory(".", "index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    entrada = data.get("mensagem", "").strip()
    if not entrada: return jsonify({"resposta": "Diga algo!", "tipo": "erro"})

    mem = carregar()
    mem["stats"]["conversas"] += 1

    # 1. tenta ensinar
    resp_ensino, tipo_ensino = detectar_ensino(entrada, mem)
    if resp_ensino:
        salvar(mem)
        return jsonify({"resposta": resp_ensino, "tipo": tipo_ensino, "cerebro": resumo(mem)})

    # 2. fórmula aprendida
    r = tentar_formula(entrada, mem)
    if r: salvar(mem); return jsonify({"resposta": r, "tipo": "formula", "cerebro": resumo(mem)})

    # 3. álgebra direta
    if e_algebra(entrada):
        r = resolver_algebra(entrada)
        if r: salvar(mem); return jsonify({"resposta": f"Resultado: {r}", "tipo": "algebra", "cerebro": resumo(mem)})

    # 4. busca na memória
    resp_mem, tipo_mem = buscar_resposta(entrada, mem)
    if resp_mem: salvar(mem); return jsonify({"resposta": resp_mem, "tipo": tipo_mem, "cerebro": resumo(mem)})

    # 5. não sabe
    salvar(mem)
    return jsonify({
        "resposta": random.choice([
            "Ainda não aprendi isso. Me ensine! Ex: 'fotossíntese é o processo pelo qual plantas produzem energia'",
            "Não encontrei na memória. Me explique usando: 'X é Y' ou 'quando eu disser X, responda Y'",
            "Não sei ainda! Me ensine assim: 'capital do brasil é Brasília'"
        ]),
        "tipo": "nao_sei",
        "cerebro": resumo(mem)
    })

@app.route("/api/imagem", methods=["POST"])
def imagem():
    data = request.json
    texto_extraido = data.get("texto", "").strip()
    if not texto_extraido: return jsonify({"erro": "Nenhum texto recebido."}), 400
    mem = carregar()
    resp_ensino, tipo = detectar_ensino(texto_extraido, mem)
    if resp_ensino:
        salvar(mem)
        return jsonify({"aprendizado": resp_ensino, "tipo": tipo, "cerebro": resumo(mem)})
    mem["conhecimento"].append({"texto": texto_extraido, "t": datetime.now().isoformat()})
    mem["stats"]["aprendizagens"] += 1
    salvar(mem)
    return jsonify({"aprendizado": "📚 Guardei o conteúdo na memória!", "tipo": "conhecimento", "cerebro": resumo(mem)})

@app.route("/api/cerebro")
def cerebro(): return jsonify(resumo(carregar()))

if __name__ == "__main__":
    print("\n🤖 Robô v4 iniciado! http://localhost:5000\n")
    app.run(debug=False, port=5000)
