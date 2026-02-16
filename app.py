import eel
import sqlite3
import re
from datetime import datetime
import yfinance as yf

# ==========================================
# CONFIGURAÇÃO DE BANCO DE DADOS (SQLITE)
# ==========================================
DB_NAME = "financeiro.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome (como RealDictCursor)
    conn.execute("PRAGMA foreign_keys = ON") # Habilita exclusão em cascata (ON DELETE CASCADE)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Rendas
    c.execute('''CREATE TABLE IF NOT EXISTS rendas (
        id_renda INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        tipo TEXT,
        categoria TEXT
    )''')

    # 2. Cartões
    c.execute('''CREATE TABLE IF NOT EXISTS cartoes (
        id_cartao INTEGER PRIMARY KEY AUTOINCREMENT,
        apelido TEXT NOT NULL,
        limite REAL,
        dia_fechamento INTEGER,
        dia_vencimento INTEGER
    )''')

    # 3. Gastos (Com todas as suas colunas detalhadas)
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (
        id_gasto INTEGER PRIMARY KEY AUTOINCREMENT,
        data_ocorrencia DATE NOT NULL,
        desc_compra TEXT,
        valor REAL,
        movimentacao TEXT,
        tipo_pagamento TEXT,
        origem_valor TEXT,
        grupo_valor TEXT,
        sub_grupo_valor TEXT,
        origem_cartao TEXT,
        origem TEXT,
        recorrente BOOLEAN DEFAULT 0,
        id_cartao INTEGER REFERENCES cartoes(id_cartao) ON DELETE CASCADE,
        parcelas INTEGER DEFAULT 1,
        categoria_meta TEXT
    )''')

    # 4. Metas / Orçamento
    c.execute('''CREATE TABLE IF NOT EXISTS orcamento_metas (
        id_meta INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT UNIQUE NOT NULL,
        percentual_limite REAL NOT NULL DEFAULT 0
    )''')

    # INSERTS PADRÃO (Com INSERT OR IGNORE para evitar duplicidade se rodar 2 vezes)
    c.execute('''
        INSERT OR IGNORE INTO orcamento_metas (categoria, percentual_limite) VALUES
        ('Gastos Fixos', 50),
        ('Conforto', 20),
        ('Metas', 10),
        ('Investimentos', 10),
        ('Educação', 10)
    ''')

    # 5. Investimentos
    c.execute('''CREATE TABLE IF NOT EXISTS meus_investimentos (
        id_investimento INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        quantidade INTEGER,
        preco_medio REAL,
        total_pago REAL,
        tipo TEXT
    )''')

    conn.commit()
    conn.close()

# Inicializa as tabelas ao rodar o script
init_db()
eel.init('web')

# ==========================================
# MOTOR DE REGEX E TRATAMENTO
# ==========================================
def limpar_valor(valor):
    try: return float(str(valor).replace(',', '.'))
    except: return 0.0

REGEX_PREFIXOS = r'^(PAG\s*\*|PG\s*\*|PAYPAL\s*\*|EBANX\s*\*|SHOPEE\s*\*|MERCADOPAGO\s*\*|MP\s*\*|APP\s*\*|GOOGLE\s*\*|APPLE\s*\*|EBN\s*\*|UBER\s*\*|UBER UBER\s*\*|99APP\s*\*||DL\s*\*|IOF\s*\*|AMAZON\s*\*|IFD\s*\*|IFD*\*|IFOOD\s*\*|SERVICOS CLA\s*\*)\s*'

CATEGORIAS_REGEX = {
    'TRANSPORTE': ['UBER', '99APP', 'POSTO', 'IPIRANGA', 'SHELL', 'ESTACIONAMENTO'],
    'ALIMENTACAO': ['IFOOD', 'RAPPI', 'RESTAURANTE', 'PADARIA', 'MERCADO', 'SUPERMERCADO', 'ASSAI', 'ATACADISTA', 'BURGER', 'MC DONALDS', 'LANCHE', 'AÇAI', 'PIZZARIA'],
    'SERVICOS': ['NETFLIX', 'SPOTIFY', 'AMAZON PRIME', 'HBO', 'DISNEY', 'GOOGLE', 'APPLE', 'AWS'],
    'COMPRAS': ['SHOPEE', 'MERCADOLIVRE', 'AMAZON', 'MAGALU', 'SHEIN', 'ALIEXPRESS'],
    'SAUDE': ['FARMACIA', 'DROGARIA', 'CONSULTA', 'EXAME', 'MEDICO', 'HOSPITAL', 'ODONTO'],
    'CASA': ['LEROY', 'C&C', 'TOKSTOK', 'MOBLY', 'IKEA', 'CONSTRUCAO']
}

def processar_parcelas(desc):
    match = re.search(r'[\s-]*(?:PARCELA)?\s*[\(]?(\d+)\s*(?:/|DE|-)\s*(\d+)[\)]?', str(desc), re.IGNORECASE)
    if match:
        parcela_atual = int(match.group(1))
        total_parcelas = int(match.group(2))
        desc_sem_parcela = re.sub(r'[\s-]*(?:PARCELA)?\s*[\(]?\d+\s*(?:/|DE|-)\s*\d+[\)]?', '', str(desc), flags=re.IGNORECASE)
        return desc_sem_parcela.strip(), parcela_atual, total_parcelas
    return str(desc).strip(), 1, 1

def limpar_nome_estabelecimento(nome):
    nome_limpo = re.sub(REGEX_PREFIXOS, '', nome, flags=re.IGNORECASE)
    nome_limpo = re.sub(r'^[\*\-\s\.]+', '', nome_limpo)
    nome_limpo = re.sub(r'\s(SAO PAULO|RIO DE JANEIRO|BR|BRA)$', '', nome_limpo, flags=re.IGNORECASE)
    return nome_limpo.strip().title()

def classificar_grupo(nome):
    nome_upper = nome.upper()
    for categoria, palavras in CATEGORIAS_REGEX.items():
        for palavra in palavras:
            if palavra in nome_upper: return categoria
    return 'OUTROS'


# ==========================================
# ENDPOINTS DO APLICATIVO
# ==========================================

@eel.expose
def get_dashboard_avancado(mes_atual, ano_atual):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fluxo Mensal (COALESCE virou IFNULL no SQLite)
    cursor.execute("SELECT IFNULL(SUM(valor), 0) FROM rendas")
    renda = cursor.fetchone()[0]
    
    cursor.execute("SELECT IFNULL(SUM(valor), 0) FROM gastos WHERE recorrente=1")
    gastos_fixos = cursor.fetchone()[0]
    
    cursor.execute("SELECT IFNULL(SUM(valor), 0) FROM gastos WHERE recorrente=0 OR recorrente IS NULL")
    gastos_avulsos = cursor.fetchone()[0]

    # 2. Resumo de Investimentos e Previsão de Dividendos
    cursor.execute("SELECT * FROM meus_investimentos")
    ativos = cursor.fetchall()
    
    patrimonio_total = lucro_total = dividendos_esperados = 0
    dias_pagamento = set()

    for ativo in ativos:
        ticker_full = f"{ativo['ticker']}.SA"
        try:
            stock = yf.Ticker(ticker_full)
            preco_atual = stock.fast_info['last_price']
            if preco_atual:
                valor_posicao = preco_atual * ativo['quantidade']
                patrimonio_total += valor_posicao
                lucro_total += (valor_posicao - float(ativo['total_pago']))

            hist_div = stock.dividends
            if not hist_div.empty:
                ultimo_div = hist_div.iloc[-1]
                data_ultimo_div = hist_div.index[-1]
                if ativo['tipo'] == 'FII' or (data_ultimo_div.month == int(mes_atual) % 12 or (data_ultimo_div.month == int(mes_atual) -1)):
                    dividendos_esperados += (ultimo_div * ativo['quantidade'])
                    dias_pagamento.add(str(data_ultimo_div.day))
        except Exception: pass

    # 3. Próximas Faturas
    faturas_lista = []
    cursor.execute("SELECT * FROM cartoes")
    cartoes = cursor.fetchall()
    
    for cartao in cartoes:
        total_fatura = 0
        cursor.execute("SELECT * FROM gastos WHERE id_cartao = ?", (cartao['id_cartao'],))
        compras = cursor.fetchall()
        for compra in compras:
            val_parcela = float(compra['valor']) / (compra['parcelas'] or 1)
            dt_compra = compra['data_ocorrencia'] 
            if isinstance(dt_compra, str):
                dt_compra = datetime.strptime(dt_compra, '%Y-%m-%d').date()

            for i in range(compra['parcelas'] or 1):
                mes_venc = dt_compra.month + i
                if dt_compra.day >= cartao['dia_fechamento']: mes_venc += 1
                ano_venc = dt_compra.year + (mes_venc - 1) // 12
                mes_venc_final = (mes_venc - 1) % 12 + 1
                
                if mes_venc_final == int(mes_atual) and ano_venc == int(ano_atual):
                    total_fatura += val_parcela
                    
        if total_fatura > 0:
            faturas_lista.append({"cartao": cartao['apelido'], "valor": float(total_fatura), "dia": cartao['dia_vencimento']})

    faturas_lista = sorted(faturas_lista, key=lambda x: x['dia'])
    conn.close()

    return {
        "fluxo": {"renda": float(renda), "gastos_fixos": float(gastos_fixos), "saldo": float(renda - gastos_fixos), "grafico_gastos": [float(gastos_fixos), float(gastos_avulsos)]},
        "investimentos": {"patrimonio": float(patrimonio_total), "lucro": float(lucro_total), "dividendos": float(dividendos_esperados), "dias_pagamento": list(dias_pagamento)},
        "faturas": faturas_lista
    }

@eel.expose
def salvar_transacao(tipo, dados):
    conn = get_db_connection()
    cursor = conn.cursor()
    val = limpar_valor(dados.get('val', 0))

    if tipo == 'renda':
        cursor.execute("INSERT INTO rendas (descricao, valor, tipo, categoria) VALUES (?, ?, ?, ?)", 
                       (dados['desc'], val, dados['tipo'], dados['categoria']))
                       
    elif tipo in ['gasto', 'compra_cartao']:
        desc_limpa, _, total_parcelas_regex = processar_parcelas(dados['desc'])
        nome_final = limpar_nome_estabelecimento(desc_limpa)
        grupo = classificar_grupo(nome_final)
        
        origem = "Cartão de Crédito" if tipo == 'compra_cartao' else "Conta Corrente"
        id_cartao = int(dados['id_cartao']) if tipo == 'compra_cartao' else None
        parcelas = int(dados['parc']) if tipo == 'compra_cartao' and int(dados.get('parc', 1)) > 1 else total_parcelas_regex
        
        cursor.execute("""
            INSERT INTO gastos 
            (desc_compra, valor, data_ocorrencia, recorrente, origem_valor, grupo_valor, categoria_meta, id_cartao, parcelas) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nome_final, val, dados['data'], 1 if dados.get('rec') else 0, origem, grupo, dados['categoria_meta'], id_cartao, parcelas))
        
    elif tipo == 'cartao':
        cursor.execute("INSERT INTO cartoes (apelido, limite, dia_fechamento, dia_vencimento) VALUES (?, ?, ?, ?)", 
                       (dados['apelido'], limpar_valor(dados['limite']), int(dados['fecha']), int(dados['vence'])))
                       
    elif tipo == 'investimento':
        cursor.execute("INSERT INTO meus_investimentos (ticker, quantidade, preco_medio, total_pago, tipo) VALUES (?, ?, ?, ?, ?)", 
                       (dados['ticker'].upper(), int(dados['qtd']), limpar_valor(dados['pm']), limpar_valor(dados['total_pago']), dados['tipo']))

    conn.commit()
    conn.close()
    return True

@eel.expose
def get_resumo_cartoes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cartoes")
    cartoes = cursor.fetchall()
    
    resultado = []
    for c in cartoes:
        cursor.execute("SELECT IFNULL(SUM(valor), 0) FROM gastos WHERE id_cartao = ?", (c['id_cartao'],))
        compras = cursor.fetchone()[0]
        resultado.append({
            "id": c['id_cartao'], "apelido": c['apelido'], "limite_total": float(c['limite'] or 0),
            "usado": float(compras), "disponivel": float((c['limite'] or 0) - compras)
        })
    conn.close()
    return resultado

@eel.expose
def get_investimentos_live():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM meus_investimentos")
    ativos = cursor.fetchall()
    conn.close()
    
    lista_final = []
    for ativo in ativos:
        ticker_full = f"{ativo['ticker']}.SA"
        try:
            stock = yf.Ticker(ticker_full)
            preco_atual = stock.fast_info['last_price']
            if not preco_atual:
                hist = stock.history(period="1d")
                preco_atual = hist['Close'].iloc[-1] if not hist.empty else float(ativo['preco_medio'])
        except: preco_atual = float(ativo['preco_medio'])

        total_pago_real = float(ativo['total_pago'])
        valor_atual_posicao = preco_atual * ativo['quantidade']
        lista_final.append({
            "id": ativo['id_investimento'], "ticker": ativo['ticker'], "qtd": ativo['quantidade'],
            "pm": float(ativo['preco_medio']), "total_pago": total_pago_real,
            "total_atual": valor_atual_posicao, "atual": preco_atual, "lucro": valor_atual_posicao - total_pago_real
        })
    return lista_final

@eel.expose
def get_historico_movimentacoes():
    conn = get_db_connection()
    cursor = conn.cursor()
    rendas = cursor.execute("SELECT id_renda as id, descricao, valor FROM rendas ORDER BY id_renda DESC").fetchall()
    gastos = cursor.execute("SELECT id_gasto as id, desc_compra as descricao, valor FROM gastos ORDER BY id_gasto DESC").fetchall()
    conn.close()
    return {
        'rendas': [{'id': r['id'], 'descricao': r['descricao'], 'valor': float(r['valor'])} for r in rendas], 
        'gastos': [{'id': g['id'], 'descricao': g['descricao'], 'valor': float(g['valor'])} for g in gastos]
    }

@eel.expose
def remover_item_banco(tabela, id_item):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if tabela == 'rendas': cursor.execute("DELETE FROM rendas WHERE id_renda = ?", (id_item,))
        elif tabela == 'gastos': cursor.execute("DELETE FROM gastos WHERE id_gasto = ?", (id_item,))
        elif tabela == 'investimentos': cursor.execute("DELETE FROM meus_investimentos WHERE id_investimento = ?", (id_item,))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        conn.close()

# ==========================================
# ENDPOINTS DE METAS E ORÇAMENTO
# ==========================================
@eel.expose
def get_metas_orcamento(mes_atual, ano_atual):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT IFNULL(SUM(valor), 0) FROM rendas")
    renda_total = float(cursor.fetchone()[0] or 0)

    cursor.execute("SELECT * FROM orcamento_metas ORDER BY id_meta")
    metas = cursor.fetchall()
    
    # Formata mês e ano para o padrão strftime do SQLite (Ex: '02', '2026')
    mes_str = f"{int(mes_atual):02d}"
    ano_str = str(ano_atual)
    
    resultado = []
    for meta in metas:
        cat = meta['categoria']
        percentual = float(meta['percentual_limite'])
        limite_reais = renda_total * (percentual / 100)
        
        # SQLite usa strftime ao invés de EXTRACT(MONTH FROM...)
        cursor.execute("""
            SELECT IFNULL(SUM(valor), 0) FROM gastos 
            WHERE categoria_meta = ? 
            AND strftime('%m', data_ocorrencia) = ? 
            AND strftime('%Y', data_ocorrencia) = ?
        """, (cat, mes_str, ano_str))
        
        gasto_atual = float(cursor.fetchone()[0] or 0)
        
        resultado.append({
            "categoria": cat, "percentual": percentual, "limite_reais": limite_reais,
            "gasto": gasto_atual, "disponivel": limite_reais - gasto_atual
        })
        
    conn.close()
    return {"renda_total": renda_total, "metas": resultado}

@eel.expose
def atualizar_meta(categoria, novo_percentual):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orcamento_metas SET percentual_limite = ? WHERE categoria = ?", (limpar_valor(novo_percentual), categoria))
    conn.commit()
    conn.close()
    return True

@eel.expose
def criar_meta(nome_categoria, percentual):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO orcamento_metas (categoria, percentual_limite) VALUES (?, ?)", 
                       (nome_categoria.strip(), limpar_valor(percentual)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()

@eel.expose
def get_categorias_meta():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT categoria FROM orcamento_metas ORDER BY id_meta")
    cats = [row['categoria'] for row in cursor.fetchall()]
    conn.close()
    return cats

# ==========================================
# INICIALIZAÇÃO
# ==========================================
print("Iniciando App - SQLite")
eel.start('index.html', size=(1250, 900))