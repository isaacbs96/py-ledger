let chartGastosInstance = null;
let chartMetasInstance = null;

// ==========================================
// CONTROLE DO LOADER GLOBAL
// ==========================================
function showLoading() {
    const loader = document.getElementById('global-loader');
    if (loader) loader.classList.add('active');
}

function hideLoading() {
    const loader = document.getElementById('global-loader');
    if (loader) loader.classList.remove('active');
}

function openTab(tabName, element) {
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    const target = document.getElementById(tabName);
    if (target) target.classList.add('active');
    if (element) element.classList.add('active');

    try {
        if (typeof eel !== 'undefined') {
            if (tabName === 'dashboard') loadDashboard();
            if (tabName === 'movimentacoes') loadMovimentacoes();
            if (tabName === 'cartoes') loadCartoesInfo();
            if (tabName === 'investimentos') loadInvestimentos();
            if (tabName === 'metas') loadMetas();
        }
    } catch (e) { }
}

function formatBRL(val) {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);
}

async function runEel(funcName, ...args) {
    if (typeof eel !== 'undefined' && eel[funcName]) {
        return await eel[funcName](...args)();
    }
    return null;
}

// --- INTEGRAÇÃO COM LOADING ---
async function removerItem(tabela, id) {
    if (confirm("Tem certeza que deseja apagar?")) {
        showLoading(); // Liga o Spinner
        
        await runEel('remover_item_banco', tabela, id);
        if (tabela === 'investimentos') {
            await loadInvestimentos();
        } else {
            await loadMovimentacoes();
        }
        await loadDashboard();
        
        hideLoading(); // Desliga o Spinner
    }
}

// --- CATEGORIAS DINÂMICAS ---
async function atualizarDropdownsCategorias(categoriasExistentes = null) {
    let categorias = categoriasExistentes;
    if (!categorias) {
        categorias = await runEel('get_categorias_meta');
    }
    const selectGasto = document.getElementById('gasto-cat-meta');
    const selectCompra = document.getElementById('compra-cat-meta');
    if (selectGasto) selectGasto.innerHTML = categorias.map(c => `<option value="${c}">${c}</option>`).join('');
    if (selectCompra) selectCompra.innerHTML = categorias.map(c => `<option value="${c}">${c}</option>`).join('');
}

document.addEventListener("DOMContentLoaded", () => {
    atualizarDropdownsCategorias();
});

// --- DASHBOARD ---
async function loadDashboard() {
    const hoje = new Date();
    const mesAtual = hoje.getMonth() + 1;
    const anoAtual = hoje.getFullYear();

    document.getElementById('dash-dias-pagamento').innerText = "Consultando B3...";
    const dados = await runEel('get_dashboard_avancado', mesAtual, anoAtual);
    
    if (dados) {
        document.getElementById('dash-renda').innerText = formatBRL(dados.fluxo.renda);
        document.getElementById('dash-gastos').innerText = formatBRL(dados.fluxo.gastos_fixos);
        const elSobra = document.getElementById('dash-sobra');
        elSobra.innerText = formatBRL(dados.fluxo.saldo);
        elSobra.className = dados.fluxo.saldo >= 0 ? 'big-number text-success' : 'big-number text-danger';

        document.getElementById('dash-patrimonio').innerText = formatBRL(dados.investimentos.patrimonio);
        const elLucro = document.getElementById('dash-lucro-inv');
        elLucro.innerText = formatBRL(dados.investimentos.lucro);
        elLucro.className = dados.investimentos.lucro >= 0 ? 'text-success' : 'text-danger';

        document.getElementById('dash-dividendos').innerText = formatBRL(dados.investimentos.dividendos);
        const diasText = dados.investimentos.dias_pagamento.length > 0 
            ? `Dias previstos: ${dados.investimentos.dias_pagamento.sort((a,b)=>a-b).join(', ')}/${mesAtual}` 
            : "Sem previsão no momento.";
        document.getElementById('dash-dias-pagamento').innerText = diasText;

        const divFaturas = document.getElementById('dash-lista-faturas');
        divFaturas.innerHTML = '';
        if (dados.faturas.length > 0) {
            dados.faturas.forEach(f => {
                divFaturas.innerHTML += `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: var(--bg-app); border: 1px solid var(--border); border-radius: 12px;">
                        <div>
                            <strong style="color: var(--text-primary); font-size: 0.95rem;">${f.cartao}</strong>
                            <span style="display: block; font-size: 0.8rem; color: var(--text-secondary);">Vence dia ${f.dia}</span>
                        </div>
                        <strong class="text-danger">${formatBRL(f.valor)}</strong>
                    </div>`;
            });
        } else {
            divFaturas.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">Sem faturas para este mês.</p>';
        }

        const ctx = document.getElementById('chartGastos').getContext('2d');
        if (chartGastosInstance) { chartGastosInstance.destroy(); } 
        chartGastosInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Gastos Fixos', 'Gastos Avulsos'],
                datasets: [{
                    data: dados.fluxo.grafico_gastos,
                    backgroundColor: ['#006FEE', '#F31260'], 
                    borderColor: '#18181B', borderWidth: 4, hoverOffset: 4
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '75%',
                plugins: { legend: { position: 'bottom', labels: { color: '#A1A1AA' } } }
            }
        });
    }
}

// --- MOVIMENTAÇÕES ---
async function loadMovimentacoes() {
    const dados = await runEel('get_historico_movimentacoes');
    const tbRenda = document.querySelector('#tabela-rendas tbody');
    tbRenda.innerHTML = '';
    dados.rendas.forEach(r => {
        tbRenda.innerHTML += `<tr><td>${r.descricao}</td><td class="text-success" style="font-weight: 500;">${formatBRL(r.valor)}</td><td style="text-align: right;"><button class="btn-danger-flat" onclick="removerItem('rendas', ${r.id})">Remover</button></td></tr>`;
    });
    const tbGasto = document.querySelector('#tabela-gastos tbody');
    tbGasto.innerHTML = '';
    dados.gastos.forEach(g => {
        tbGasto.innerHTML += `<tr><td>${g.descricao}</td><td class="text-danger" style="font-weight: 500;">${formatBRL(g.valor)}</td><td style="text-align: right;"><button class="btn-danger-flat" onclick="removerItem('gastos', ${g.id})">Remover</button></td></tr>`;
    });
}

async function addRenda() {
    const desc = document.getElementById('renda-desc').value;
    const val = document.getElementById('renda-val').value;
    const tipo = document.getElementById('renda-tipo').value;
    const categoria = document.getElementById('renda-categoria').value;
    
    if (!desc || !val) return alert("Preencha descrição e valor.");
    
    showLoading();
    await runEel('salvar_transacao', 'renda', { desc, val, tipo, categoria });
    await loadMovimentacoes(); 
    hideLoading();
    await loadDashboard();
}

async function addGasto() {
    const desc = document.getElementById('gasto-desc').value;
    const val = document.getElementById('gasto-val').value;
    const data = document.getElementById('gasto-data').value;
    const rec = document.getElementById('gasto-rec').checked;
    const categoria_meta = document.getElementById('gasto-cat-meta').value;
    
    if (!desc || !val) return alert("Preencha descrição e valor.");

    showLoading();
    await runEel('salvar_transacao', 'gasto', { desc, val, data, rec, categoria_meta });
    await loadMovimentacoes(); 
    hideLoading();
    await loadDashboard();
}

// --- METAS E ORÇAMENTO ---
async function loadMetas() {
    const hoje = new Date();
    const dados = await runEel('get_metas_orcamento', hoje.getMonth() + 1, hoje.getFullYear());
    
    const div = document.getElementById('lista-metas');
    div.innerHTML = '';
    
    let somaPct = 0;
    let labelsGrafico = [];
    let dadosGrafico = [];
    let coresGrafico = ['#006FEE', '#17C964', '#F31260', '#F5A524', '#7828C8', '#06B6D4', '#A1A1AA'];

    dados.metas.forEach(m => {
        somaPct += m.percentual;
        labelsGrafico.push(m.categoria);
        dadosGrafico.push(m.percentual);

        let pctGasto = m.limite_reais > 0 ? (m.gasto / m.limite_reais) * 100 : 0;
        let barColor = pctGasto > 90 ? 'var(--danger)' : pctGasto > 75 ? 'var(--warning)' : 'var(--primary)';
        
        div.innerHTML += `
            <div style="padding-bottom: 10px; border-bottom: 1px solid var(--border);">
                <div style="display:flex; justify-content:space-between; margin-bottom: 5px;">
                    <strong style="color: var(--text-primary); font-size: 1.05rem;">${m.categoria}</strong>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <span style="color: var(--text-secondary); font-size: 0.85rem;">
                            Limite: ${formatBRL(m.limite_reais)} | 
                        </span>
                        <div style="display: flex; align-items: center; background: var(--bg-app); border: 1px solid var(--border); border-radius: 8px; padding-right: 8px;">
                            <input type="number" value="${m.percentual}" onchange="atualizarLimiteMeta('${m.categoria}', this.value)" 
                                   style="width: 60px; padding: 6px; border: none; background: transparent; text-align: right; color: var(--text-primary);">
                            <span style="color: var(--text-secondary);">%</span>
                        </div>
                    </div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size:0.8rem; margin-bottom:8px;">
                    <span style="color: var(--text-secondary)">Gasto: ${formatBRL(m.gasto)}</span>
                    <strong style="color: ${m.disponivel < 0 ? 'var(--danger)' : 'var(--success)'}">Sobra: ${formatBRL(m.disponivel)}</strong>
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: ${Math.min(pctGasto, 100)}%; background-color: ${barColor}"></div>
                </div>
            </div>`;
    });

    const elSoma = document.getElementById('soma-pct-metas');
    elSoma.innerText = `Total Distribuído: ${somaPct}%`;
    elSoma.style.color = somaPct !== 100 ? 'var(--danger)' : 'var(--success)';

    const ctx = document.getElementById('chartMetas').getContext('2d');
    if (chartMetasInstance) chartMetasInstance.destroy();
    chartMetasInstance = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labelsGrafico,
            datasets: [{ data: dadosGrafico, backgroundColor: coresGrafico, borderColor: '#18181B', borderWidth: 2 }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'right', labels: { color: '#A1A1AA', font: { size: 11 } } } }
        }
    });

    atualizarDropdownsCategorias(labelsGrafico);
}

async function atualizarLimiteMeta(categoria, valorPct) {
    showLoading();
    await runEel('atualizar_meta', categoria, valorPct);
    await loadMetas(); 
    hideLoading();
}

async function criarNovaMeta() {
    const nome = document.getElementById('nova-meta-nome').value;
    const pct = document.getElementById('nova-meta-pct').value;
    if (!nome || !pct) return alert("Preencha o nome e a porcentagem!");
    
    showLoading();
    const sucesso = await runEel('criar_meta', nome, pct);
    if (sucesso) {
        document.getElementById('nova-meta-nome').value = '';
        document.getElementById('nova-meta-pct').value = '';
        await loadMetas();
    } else {
        alert("Erro ao criar meta. Já existe uma com este nome?");
    }
    hideLoading();
}

// --- CARTÕES ---
async function cadastrarCartao() {
    const apelido = document.getElementById('card-apelido').value;
    const limite = document.getElementById('card-limite').value;
    const fecha = document.getElementById('card-fecha').value;
    const vence = document.getElementById('card-vence').value;
    if (!apelido) return alert("Preencha o nome");
    
    showLoading();
    await runEel('salvar_transacao', 'cartao', { apelido, limite, fecha, vence });
    await loadCartoesInfo();
    hideLoading();
    
    alert("Cartão Criado!");
}

async function loadCartoesInfo() {
    const cartoes = await runEel('get_resumo_cartoes');
    const sel = document.getElementById('sel-cartoes-disponiveis');
    sel.innerHTML = '';
    const divLimites = document.getElementById('lista-limites');
    divLimites.innerHTML = '';

    if (cartoes && cartoes.length > 0) {
        cartoes.forEach(c => {
            sel.innerHTML += `<option value="${c.id}">${c.apelido}</option>`;
            let pct = (c.usado / c.limite_total) * 100;
            if (pct > 100) pct = 100;
            let barColor = pct > 90 ? 'var(--danger)' : pct > 75 ? 'var(--warning)' : 'var(--primary)';
            divLimites.innerHTML += `
                <div style="margin-bottom:20px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                        <strong style="color: var(--text-primary)">${c.apelido}</strong>
                        <span style="font-size:0.9rem; color: var(--text-secondary);">Disp: <strong style="color: var(--text-primary)">${formatBRL(c.disponivel)}</strong></span>
                    </div>
                    <div style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:8px;">
                        Limite: ${formatBRL(c.limite_total)} | Usado: ${formatBRL(c.usado)}
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width: ${pct}%; background-color: ${barColor}"></div>
                    </div>
                </div>`;
        });
    } else {
        sel.innerHTML = "<option>Nenhum cartão</option>";
        divLimites.innerHTML = "<p style='color: var(--text-secondary)'>Sem cartões cadastrados.</p>";
    }
}

async function lancarCompra() {
    const id_cartao = document.getElementById('sel-cartoes-disponiveis').value;
    const desc = document.getElementById('compra-desc').value;
    const val = document.getElementById('compra-val').value;
    const parc = document.getElementById('compra-parc').value;
    const data = document.getElementById('compra-data').value;
    const categoria_meta = document.getElementById('compra-cat-meta').value;
    
    if (!desc || !val) return alert("Preencha descrição e valor.");

    showLoading();
    await runEel('salvar_transacao', 'compra_cartao', { id_cartao, desc, val, parc, data, categoria_meta });
    await loadCartoesInfo();
    hideLoading();
    
    alert("Compra lançada!");
}

// --- INVESTIMENTOS ---
function autoCalcTotal() {
    const qtd = parseFloat(document.getElementById('inv-qtd').value) || 0;
    const pmStr = document.getElementById('inv-pm').value || "0";
    const pm = parseFloat(pmStr.replace(',', '.')) || 0;
    const inputTotal = document.getElementById('inv-total');
    if (qtd > 0 && pm > 0 && !inputTotal.value.includes(',')) {
        inputTotal.value = (qtd * pm).toFixed(2).replace('.', ',');
    }
}

async function addInvestimento() {
    const ticker = document.getElementById('inv-ticker').value;
    const qtd = document.getElementById('inv-qtd').value;
    const pm = document.getElementById('inv-pm').value; 
    const total_pago = document.getElementById('inv-total').value; 
    const tipo = document.getElementById('inv-tipo').value;
    
    if (!ticker || !qtd || !pm) return alert("Preencha os campos corretamente.");

    showLoading();
    await runEel('salvar_transacao', 'investimento', { ticker, qtd, pm, total_pago, tipo });
    await loadInvestimentos();
    hideLoading();
    
    alert("Investimento Salvo!");
}

async function loadInvestimentos() {
    const tbody = document.getElementById('tabela-inv-body');
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color: var(--text-secondary);">Atualizando cotações...</td></tr>';
    const dados = await runEel('get_investimentos_live');
    tbody.innerHTML = '';
    if (dados && dados.length > 0) {
        dados.forEach(i => {
            let lucroClass = i.lucro >= 0 ? 'text-success' : 'text-danger';
            tbody.innerHTML += `
                <tr>
                    <td><strong style="color: var(--text-primary)">${i.ticker}</strong></td>
                    <td>${i.qtd}</td>
                    <td>${formatBRL(i.pm)}</td>
                    <td>${formatBRL(i.total_pago)}</td>
                    <td><strong style="color: var(--text-primary)">${formatBRL(i.total_atual)}</strong></td>
                    <td class="${lucroClass}" style="font-weight: 600;">${formatBRL(i.lucro)}</td>
                    <td style="text-align: right;"><button class="btn-danger-flat" onclick="removerItem('investimentos', ${i.id})">Remover</button></td>
                </tr>`;
        });
    } else {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color: var(--text-secondary);">Sua carteira está vazia.</td></tr>';
    }
}