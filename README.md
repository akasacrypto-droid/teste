# 🤖 Robô Auto-Programável v3

## Instalação

```bash
pip install flask sympy pyttsx3 colorama
```

## Como rodar

```bash
python app.py
```

Depois abra no navegador: **http://localhost:5000**

---

## Como ensinar o robô

### Regras (ele age sozinho depois):
```
se o usuario disser "oi" entao "Olá! Tudo bem?"
regra: se perguntar "preço" então "Não trabalho com vendas."
```

### Fórmulas:
```
area do circulo = pi * r**2
calcular imc = peso / altura**2
```
Depois use:
```
calcular area do circulo com r=5
calcular imc com peso=70 e altura=1.75
```

### Respostas diretas:
```
quando perguntarem "capital do brasil" responda "Brasília"
```

### Álgebra (sempre funciona):
```
2x + 3 = 7
x**2 - 5x + 6 = 0
simplificar (x+1)**2
expandir (a+b)**3
```

---

## Arquivos

| Arquivo | Descrição |
|---|---|
| `app.py` | Backend Flask (servidor) |
| `static/index.html` | Interface visual |
| `cerebro_robo.json` | Memória do robô (gerada automaticamente) |

---

## Voz (opcional)

A voz funciona automaticamente se `pyttsx3` estiver instalado.
Para desativar: `python app.py --sem-voz`
