// ==========================================
// ESTADO GERAL / NAVEGACAO
// ==========================================
const views = {
  home: document.getElementById('view-home'),
  identificacao: document.getElementById('view-identificacao'),
  relacaoCarga: document.getElementById('view-relacao-carga'),
  romaneio: document.getElementById('view-romaneio'),
  modulo: document.getElementById('view-modulo'),
  historico: document.getElementById('view-historico'),
  config: document.getElementById('view-config'),
  dadosErp: document.getElementById('view-dados-erp'),
};

let moduloAtual = 'fios'; // 'fios' | 'painel'
let paletesCache = [];
let linhaSeq = 0;

function mostrarView(nome) {
  Object.values(views).forEach(v => (v.style.display = 'none'));
  views[nome].style.display = 'block';
}

document.querySelectorAll('[data-abrir]').forEach(btn => {
  btn.addEventListener('click', () => {
    const alvo = btn.dataset.abrir;
    if (alvo === 'identificacao-pallets') mostrarView('identificacao');
    else if (alvo === 'relacao-carga') abrirRelacaoCarga();
    else if (alvo === 'romaneio') abrirRomaneio();
    else if (alvo === 'fios' || alvo === 'painel') abrirModulo(alvo);
    else if (alvo === 'historico') abrirHistorico();
    else if (alvo === 'config') abrirConfig();
    else if (alvo === 'dados-erp') abrirDadosErp();
  });
});

document.getElementById('btnVoltarIdentificacao').addEventListener('click', () => { mostrarView('home'); carregarStatus(); });
document.getElementById('btnVoltarRelacaoCarga').addEventListener('click', () => mostrarView('home'));
document.getElementById('btnVoltarRomaneio').addEventListener('click', () => mostrarView('home'));
document.getElementById('btnVoltarModulo').addEventListener('click', () => mostrarView('identificacao'));
document.getElementById('btnVoltarHistorico').addEventListener('click', () => mostrarView('identificacao'));
document.getElementById('btnVoltarConfig').addEventListener('click', () => mostrarView('identificacao'));
document.getElementById('btnVoltarDadosErp').addEventListener('click', () => mostrarView('identificacao'));

// ==========================================
// STATUS / ATUALIZACAO DO ERP
// ==========================================
async function carregarStatus() {
  try {
    const s = await fetch('/api/status').then(r => r.json());
    const txt = s.ultimaAtualizacao
      ? `Atualizado em ${new Date(s.ultimaAtualizacao).toLocaleString('pt-BR')} — ${s.ordensEmCache} ordens em cache — ${s.paletesGravados} pallets gravados`
      : 'Ainda não sincronizado com o ERP';
    document.getElementById('statusTexto').textContent = txt;
  } catch (e) {
    document.getElementById('statusTexto').textContent = 'Erro ao consultar status.';
  }
}

document.getElementById('btnAtualizarErp').addEventListener('click', async () => {
  const btn = document.getElementById('btnAtualizarErp');
  btn.disabled = true;
  btn.textContent = '🔄 Atualizando...';
  try {
    const r = await fetch('/api/refresh', { method: 'POST' }).then(res => res.json());
    if (!r.ok) throw new Error(r.erro || 'Falha ao atualizar.');
    alert(`Atualização concluída!\nOrdens (fios): ${r.ordensFios}\nOrdens (painel): ${r.ordensPainel}\nClientes: ${r.clientes}\nTempo: ${r.duracaoSegundos}s`);
  } catch (e) {
    alert('Erro ao atualizar dados do ERP: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '🔄 Atualizar dados do ERP';
    carregarStatus();
    if (paletesCache.length === 0) carregarPaletes();
  }
});

// ==========================================
// MODULO (FIOS / PAINEL)
// ==========================================
const titulos = { fios: 'Fios', painel: 'Painel / Kits' };

async function abrirModulo(modulo) {
  moduloAtual = modulo;
  document.getElementById('moduloTitulo').textContent = titulos[modulo];
  document.getElementById('moduloSub').textContent = 'Packing List — preencha OP e Qtde';
  document.querySelector('#tabelaLinhas tbody').innerHTML = '';
  linhaSeq = 0;
  mostrarView('modulo');
  await Promise.all([carregarPaletes(), carregarProximoNumero()]);
  adicionarLinha();
  adicionarLinha();
  atualizarTotais();
}

async function carregarProximoNumero() {
  try {
    const r = await fetch('/api/proximo_numero').then(res => res.json());
    document.getElementById('moduloNumero').textContent = `Nº ${String(r.proximoNumero).padStart(5, '0')}`;
  } catch (e) {
    document.getElementById('moduloNumero').textContent = 'Nº —';
  }
}

async function carregarPaletes() {
  try {
    paletesCache = await fetch('/api/paletes').then(r => r.json());
    const select = document.getElementById('selectMedidaPalete');
    const atual = select.value;
    select.innerHTML = paletesCache
      .map(p => `<option value="${p.medida}" ${p.medida === atual ? 'selected' : ''}>${p.medida} (tara ${p.peso_tara}kg)</option>`)
      .join('');
  } catch (e) {
    console.error('Erro ao carregar paletes', e);
  }
}

function novaLinhaHTML(id) {
  return `
    <tr data-linha="${id}">
      <td class="it-linha"></td>
      <td><input class="tabela-input input-op" placeholder="OP" /></td>
      <td><input class="tabela-input readonly campo-oc" readonly /></td>
      <td><input class="tabela-input readonly campo-pedido" readonly /></td>
      <td><input class="tabela-input readonly campo-codigo" readonly /></td>
      <td><input class="tabela-input readonly campo-descricao" readonly style="min-width:220px" /></td>
      <td><span class="tag-tipo campo-tipo"></span></td>
      <td><input class="tabela-input input-qtde" type="number" step="0.01" placeholder="0,00" /></td>
      <td><button type="button" class="btn-remover-linha" title="Remover linha">✕</button></td>
    </tr>`;
}

function adicionarLinha(focarSeletor = '') {
  linhaSeq += 1;
  const tbody = document.querySelector('#tabelaLinhas tbody');
  tbody.insertAdjacentHTML('beforeend', novaLinhaHTML(linhaSeq));
  renumerarLinhas();
  const tr = tbody.querySelector(`tr[data-linha="${linhaSeq}"]`);
  ligarEventosLinha(tr);
  if (focarSeletor) tr.querySelector(focarSeletor)?.focus();
  return tr;
}

document.getElementById('btnAddLinha').addEventListener('click', () => adicionarLinha('.input-op'));

function copiarDadosOp(origem, destino) {
  destino.querySelector('.input-op').value = origem.querySelector('.input-op').value.trim();
  destino.querySelector('.campo-oc').value = origem.querySelector('.campo-oc').value;
  destino.querySelector('.campo-pedido').value = origem.querySelector('.campo-pedido').value;
  destino.querySelector('.campo-codigo').value = origem.querySelector('.campo-codigo').value;
  destino.querySelector('.campo-descricao').value = origem.querySelector('.campo-descricao').value;
  destino.querySelector('.campo-tipo').textContent = origem.querySelector('.campo-tipo').textContent;
  destino.dataset.clienteCodigo = origem.dataset.clienteCodigo || '';
  destino.dataset.clienteNome = origem.dataset.clienteNome || '';
  destino.classList.toggle('linha-erro', origem.classList.contains('linha-erro'));
}

function repetirUltimaOp(origemPreferida = null) {
  const linhas = [...document.querySelectorAll('#tabelaLinhas tbody tr')];
  const origem = origemPreferida || [...linhas].reverse().find(tr => tr.querySelector('.input-op').value.trim());
  if (!origem) {
    const primeiraOp = linhas[0]?.querySelector('.input-op');
    if (primeiraOp) primeiraOp.focus();
    return;
  }

  // Reaproveita uma linha vazia logo abaixo; se nao houver, cria uma nova.
  let destino = origem.nextElementSibling;
  if (!destino || destino.querySelector('.input-op').value.trim() || destino.querySelector('.input-qtde').value) {
    destino = adicionarLinha();
  }
  copiarDadosOp(origem, destino);
  atualizarTotais();
  destino.querySelector('.input-qtde').focus();
}

document.getElementById('btnRepetirOp').addEventListener('click', () => repetirUltimaOp());

function renumerarLinhas() {
  document.querySelectorAll('#tabelaLinhas tbody tr').forEach((tr, idx) => {
    tr.querySelector('.it-linha').textContent = idx + 1;
  });
}

function ligarEventosLinha(tr) {
  const inputOp = tr.querySelector('.input-op');
  const inputQtde = tr.querySelector('.input-qtde');
  const btnRemover = tr.querySelector('.btn-remover-linha');

  inputOp.addEventListener('change', () => buscarOp(tr));
  inputOp.addEventListener('blur', () => buscarOp(tr));
  inputOp.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      buscarOp(tr).then(() => inputQtde.focus());
    }
  });
  inputQtde.addEventListener('input', atualizarTotais);
  inputQtde.addEventListener('keydown', e => {
    if (e.key === 'Enter' && inputOp.value.trim()) {
      e.preventDefault();
      repetirUltimaOp(tr);
    }
  });

  btnRemover.addEventListener('click', () => {
    tr.remove();
    renumerarLinhas();
    atualizarTotais();
  });
}

async function buscarOp(tr) {
  const op = tr.querySelector('.input-op').value.trim();
  const campos = {
    oc: tr.querySelector('.campo-oc'),
    pedido: tr.querySelector('.campo-pedido'),
    codigo: tr.querySelector('.campo-codigo'),
    descricao: tr.querySelector('.campo-descricao'),
    tipo: tr.querySelector('.campo-tipo'),
  };
  if (!op) {
    Object.values(campos).forEach(c => (c.value !== undefined ? (c.value = '') : (c.textContent = '')));
    tr.dataset.clienteCodigo = '';
    tr.dataset.clienteNome = '';
    atualizarTotais();
    return;
  }
  try {
    const r = await fetch(`/api/lookup?op=${encodeURIComponent(op)}&modulo=${moduloAtual}`);
    const dados = await r.json();
    if (!dados.encontrado) {
      campos.oc.value = campos.pedido.value = campos.codigo.value = '';
      campos.descricao.value = dados.erro || 'OP não encontrada';
      campos.tipo.textContent = '';
      tr.dataset.clienteCodigo = '';
      tr.classList.add('linha-erro');
    } else {
      campos.oc.value = dados.oc || '';
      campos.pedido.value = dados.pedido || '';
      campos.codigo.value = dados.codigoProduto || '';
      campos.descricao.value = dados.descricao || '';
      campos.tipo.textContent = dados.tipo || '';
      tr.dataset.clienteCodigo = dados.codigoCliente || '';
      tr.dataset.clienteNome = dados.clienteNome || '';
      tr.classList.remove('linha-erro');
    }
  } catch (e) {
    campos.descricao.value = 'Erro ao consultar.';
  }
  atualizarTotais();
}

function atualizarTotais() {
  let pesoLiquido = 0;
  let carreteis = 0;
  const clientesDetectados = new Set();
  let clienteNome = '';

  document.querySelectorAll('#tabelaLinhas tbody tr').forEach(tr => {
    const qtde = parseFloat(tr.querySelector('.input-qtde').value);
    const tipo = tr.querySelector('.campo-tipo').textContent.trim();
    if (!isNaN(qtde) && qtde > 0) {
      pesoLiquido += qtde;
      carreteis += 1;
    }
    if (tr.dataset.clienteCodigo) {
      clientesDetectados.add(tr.dataset.clienteCodigo);
      clienteNome = tr.dataset.clienteNome || clienteNome;
    }
  });

  const medida = document.getElementById('selectMedidaPalete').value;
  const palete = paletesCache.find(p => p.medida === medida);
  const taraPalete = palete ? palete.peso_tara : 0;

  // Estimativa client-side do peso bruto (o calculo oficial/definitivo e' feito no
  // servidor no momento de gravar, usando a mesma regra: PMC/PKT=6.2kg, NU=19.3kg por carretel)
  let pesoBrutoEstimado = pesoLiquido + taraPalete;
  document.querySelectorAll('#tabelaLinhas tbody tr').forEach(tr => {
    const qtde = parseFloat(tr.querySelector('.input-qtde').value);
    const tipo = tr.querySelector('.campo-tipo').textContent.trim();
    if (!isNaN(qtde) && qtde > 0 && moduloAtual === 'fios') {
      if (tipo === 'PMC' || tipo === 'PKT') pesoBrutoEstimado += 6.2;
      else if (tipo === 'NU') pesoBrutoEstimado += 19.3;
    }
  });

  document.getElementById('cardCarreteis').textContent = carreteis;
  document.getElementById('cardPesoLiquido').textContent = pesoLiquido.toFixed(2);
  document.getElementById('cardPesoBruto').textContent = pesoBrutoEstimado.toFixed(2);

  const avisoEl = document.getElementById('avisoModulo');
  if (clientesDetectados.size > 1) {
    document.getElementById('cardCliente').textContent = 'VÁRIOS ⚠';
    avisoEl.style.display = 'inline-block';
    avisoEl.textContent = '⚠ As OPs digitadas pertencem a clientes diferentes. Um palete só pode ter um único cliente.';
  } else {
    document.getElementById('cardCliente').textContent = clienteNome || '—';
    avisoEl.style.display = 'none';
    avisoEl.textContent = '';
  }
}

document.getElementById('selectMedidaPalete').addEventListener('change', atualizarTotais);

// ---------- Gravar ----------
function coletarPayload() {
  const itens = [];
  document.querySelectorAll('#tabelaLinhas tbody tr').forEach(tr => {
    const op = tr.querySelector('.input-op').value.trim();
    const qtde = tr.querySelector('.input-qtde').value;
    if (op || qtde) itens.push({ op, qtde });
  });
  return {
    modulo: moduloAtual,
    medidaPalete: document.getElementById('selectMedidaPalete').value,
    itens,
  };
}

async function gravar(imprimir) {
  const payload = coletarPayload();
  const btn = imprimir ? document.getElementById('btnGravarImprimir') : document.getElementById('btnGravar');
  btn.disabled = true;
  try {
    const resp = await fetch('/api/pallets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const dados = await resp.json();
    if (!dados.ok) {
      alert('Não foi possível gravar:\n\n' + (dados.erros || [dados.erro]).join('\n'));
      return;
    }
    alert(
      `Palete Nº ${String(dados.numero).padStart(5, '0')} gravado com sucesso!\n` +
      `Carretéis: ${dados.carreteis}\nPeso líquido: ${dados.pesoLiquido} kg\nPeso bruto: ${dados.pesoBruto} kg`
    );
    if (imprimir) {
      window.open(`/api/pallets/${dados.id}/pdf`, '_blank');
    }
    abrirModalLimpar();
  } catch (e) {
    alert('Erro ao gravar: ' + e.message);
  } finally {
    btn.disabled = false;
  }
}

document.getElementById('btnGravar').addEventListener('click', () => gravar(false));
document.getElementById('btnGravarImprimir').addEventListener('click', () => gravar(true));

// ---------- Limpar (equivalente ao FORM_LIMPAR da planilha) ----------
function abrirModalLimpar() {
  const bg = document.createElement('div');
  bg.className = 'modal-bg';
  bg.innerHTML = `
    <div class="modal-box">
      <h3>Limpar formulário</h3>
      <p>Deseja limpar os campos de OP e Qtde, ou manter a OP e limpar só a quantidade (para gerar outro pallet da mesma OP)?</p>
      <div class="modal-acoes">
        <button class="btn-sec" data-acao="cancelar">Cancelar</button>
        <button class="btn-ok" data-acao="manter-op">Manter OP</button>
        <button class="btn-danger" data-acao="limpar-tudo">Limpar tudo</button>
      </div>
    </div>`;
  document.body.appendChild(bg);
  bg.addEventListener('click', e => {
    const acao = e.target.dataset.acao;
    if (!acao) return;
    if (acao === 'limpar-tudo') limparFormulario(true);
    if (acao === 'manter-op') limparFormulario(false);
    bg.remove();
  });
}

document.getElementById('btnLimpar').addEventListener('click', () => abrirModalLimpar());

function limparFormulario(limparOpTambem) {
  document.querySelectorAll('#tabelaLinhas tbody tr').forEach(tr => {
    tr.querySelector('.input-qtde').value = '';
    if (limparOpTambem) {
      tr.querySelector('.input-op').value = '';
      tr.querySelectorAll('.readonly').forEach(el => (el.value = ''));
      tr.querySelector('.campo-tipo').textContent = '';
      tr.dataset.clienteCodigo = '';
      tr.dataset.clienteNome = '';
    }
  });
  carregarProximoNumero();
  atualizarTotais();
}

// ==========================================
// RELACAO DE CARGA / ESTOQUE DE PRODUTO ACABADO
// ==========================================
let estoquePallets = [];

async function abrirRelacaoCarga() {
  mostrarView('relacaoCarga');
  await Promise.all([carregarEstoquePallets(), carregarHistoricoCargas()]);
}

async function carregarHistoricoCargas() {
  const tbody = document.querySelector('#tabelaHistoricoCargas tbody');
  tbody.innerHTML = '<tr><td colspan="9">Carregando...</td></tr>';
  try {
    const resp = await fetch('/api/cargas');
    const cargas = await resp.json();
    if (!resp.ok) throw new Error(cargas.erro || 'Não foi possível consultar as relações.');
    tbody.innerHTML = cargas.map(c => `<tr>
      <td><strong>${String(c.numero).padStart(5, '0')}</strong></td>
      <td>${new Date(c.data_hora).toLocaleString('pt-BR')}</td>
      <td>${escaparHtml(c.cliente || '—')}</td><td>${escaparHtml(c.transportadora || '—')}</td>
      <td>${escaparHtml(c.veiculo || '—')}</td><td>${c.quantidade_pallets || 0}</td>
      <td>${Number(c.peso_bruto || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })} kg</td>
      <td><a class="btn-clear" href="/api/cargas/${c.id}/pdf" target="_blank">🖨️ Abrir PDF</a></td>
      <td><button class="btn-excluir-carga" data-id="${c.id}" data-numero="${c.numero}">Excluir</button></td>
    </tr>`).join('') || '<tr><td colspan="9">Nenhuma relação de carga salva.</td></tr>';
  } catch (e) { tbody.innerHTML = `<tr><td colspan="9">${escaparHtml(e.message)}</td></tr>`; }
}

document.querySelector('#tabelaHistoricoCargas tbody').addEventListener('click', async e => {
  const btn = e.target.closest('.btn-excluir-carga');
  if (!btn || !confirm(`Excluir definitivamente a Relação de Carga Nº ${String(btn.dataset.numero).padStart(5, '0')}?`)) return;
  const resp = await fetch(`/api/cargas/${btn.dataset.id}`, {method: 'DELETE'});
  const dados = await resp.json();
  if (!resp.ok) return alert(dados.erro || 'Não foi possível excluir a relação.');
  await carregarHistoricoCargas();
});

function resumoItensPallet(pallet) {
  return (pallet.itens || []).map(i => `${i.codigo_produto || '—'} / OP ${i.op || '—'}`).join('; ');
}

async function carregarEstoquePallets() {
  const busca = document.getElementById('buscaEstoque').value.trim();
  const tbody = document.querySelector('#tabelaEstoque tbody');
  tbody.innerHTML = '<tr><td colspan="9">Carregando estoque...</td></tr>';
  try {
    const resp = await fetch(`/api/estoque-pallets?busca=${encodeURIComponent(busca)}`);
    estoquePallets = await resp.json();
    tbody.innerHTML = estoquePallets.map(p => `
      <tr>
        <td><input class="check-pallet-estoque" type="checkbox" value="${p.id}" /></td>
        <td><strong>${String(p.numero).padStart(5, '0')}</strong></td>
        <td>${new Date(p.data_hora).toLocaleDateString('pt-BR')}</td>
        <td>${escaparHtml(p.cliente_nome || '')}</td>
        <td>${titulos[p.modulo] || p.modulo}</td>
        <td class="celula-descricao">${escaparHtml(resumoItensPallet(p))}</td>
        <td>${p.carreteis || 0}</td>
        <td>${Number(p.peso_liquido || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
        <td>${Number(p.peso_bruto || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
      </tr>`).join('') || '<tr><td colspan="9">Nenhum pallet disponível no estoque.</td></tr>';
    document.getElementById('estoqueQuantidade').textContent = estoquePallets.length;
    document.getElementById('selecionarTodosEstoque').checked = false;
    atualizarResumoCarga();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="9">${escaparHtml(e.message)}</td></tr>`;
  }
}

function palletsSelecionados() {
  return [...document.querySelectorAll('.check-pallet-estoque:checked')].map(c => Number(c.value));
}

function atualizarResumoCarga() {
  const ids = new Set(palletsSelecionados());
  const selecionados = estoquePallets.filter(p => ids.has(p.id));
  document.getElementById('cargaSelecionados').textContent = selecionados.length;
  const peso = selecionados.reduce((total, p) => total + Number(p.peso_bruto || 0), 0);
  document.getElementById('cargaPesoBruto').textContent = `${peso.toLocaleString('pt-BR', { minimumFractionDigits: 2 })} kg`;
}

function adicionarItemManualCarga() {
  const tbody = document.querySelector('#tabelaItensManuaisCarga tbody');
  tbody.querySelector('.linha-vazia')?.remove();
  const tr = document.createElement('tr');
  tr.className = 'item-manual-carga';
  tr.innerHTML = `<td><input class="manual-codigo" placeholder="Código" /></td>
    <td><input class="manual-descricao" placeholder="Descrição do produto" /></td>
    <td><input class="manual-quantidade" type="number" min="0.01" step="0.01" placeholder="0,00" /></td>
    <td><input class="manual-observacao" placeholder="Opcional" /></td>
    <td><button type="button" class="btn-clear btn-remover-manual">✕</button></td>`;
  tbody.appendChild(tr);
}

function itensManuaisCarga() {
  return [...document.querySelectorAll('.item-manual-carga')].map(tr => ({
    codigo: tr.querySelector('.manual-codigo').value.trim(),
    descricao: tr.querySelector('.manual-descricao').value.trim(),
    quantidade: tr.querySelector('.manual-quantidade').value,
    observacao: tr.querySelector('.manual-observacao').value.trim(),
  })).filter(i => i.codigo || i.descricao || i.quantidade);
}

document.getElementById('btnAdicionarItemCarga').addEventListener('click', adicionarItemManualCarga);
document.querySelector('#tabelaItensManuaisCarga tbody').addEventListener('click', e => {
  if (!e.target.closest('.btn-remover-manual')) return;
  e.target.closest('tr').remove();
  const tbody = document.querySelector('#tabelaItensManuaisCarga tbody');
  if (!tbody.children.length) tbody.innerHTML = '<tr class="linha-vazia"><td colspan="5">Nenhum item manual adicionado.</td></tr>';
});
document.querySelector('#tabelaItensManuaisCarga tbody').addEventListener('focusout', async e => {
  if (!e.target.classList.contains('manual-codigo')) return;
  const codigo = e.target.value.trim();
  if (!codigo) return;
  const tr = e.target.closest('tr');
  const descricao = tr.querySelector('.manual-descricao');
  e.target.classList.add('carregando');
  try {
    const resp = await fetch(`/api/produtos/por-codigo?codigo=${encodeURIComponent(codigo)}`);
    const dados = await resp.json();
    if (resp.ok) {
      descricao.value = dados.descricao || '';
      descricao.title = 'Descrição preenchida pelos dados do ERP';
    } else if (!descricao.value) {
      descricao.placeholder = dados.erro || 'Descrição não encontrada; preencha manualmente';
    }
  } catch (_) {
    if (!descricao.value) descricao.placeholder = 'Sem conexão; preencha manualmente';
  } finally { e.target.classList.remove('carregando'); }
});

document.getElementById('buscaEstoque').addEventListener('input', debounce(carregarEstoquePallets, 300));
document.querySelector('#tabelaEstoque tbody').addEventListener('change', atualizarResumoCarga);
document.getElementById('selecionarTodosEstoque').addEventListener('change', e => {
  document.querySelectorAll('.check-pallet-estoque').forEach(c => (c.checked = e.target.checked));
  atualizarResumoCarga();
});

document.getElementById('btnSalvarRelacao').addEventListener('click', async () => {
  const btn = document.getElementById('btnSalvarRelacao');
  btn.disabled = true;
  try {
    const resp = await fetch('/api/cargas', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        palletIds: palletsSelecionados(), cliente: document.getElementById('cargaCliente').value,
        transportadora: document.getElementById('cargaTransportadora').value,
        veiculo: document.getElementById('cargaVeiculo').value, motorista: document.getElementById('cargaMotorista').value,
        prioridade: document.getElementById('cargaPrioridade').value, itensManuais: itensManuaisCarga(),
      }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || 'Não foi possível salvar a relação.');
    alert(`Relação de Carga Nº ${String(dados.numero).padStart(5, '0')} salva com ${dados.quantidadePallets} pallet(s) e ${dados.quantidadeItensManuais} item(ns) manual(is).`);
    await carregarHistoricoCargas();
  } catch (e) { alert(e.message); }
  finally { btn.disabled = false; }
});

// ==========================================
// ROMANEIO / BAIXA DE PALLETS
// ==========================================
let previewRomaneioValido = false;

function textoAderencia(valor) {
  const n = Number(valor || 0);
  const nivel = n >= 99.95 ? 'Igual' : n >= 90 ? 'Muito próximo' : n >= 60 ? 'Parcial' : 'Diferente';
  return `${n.toLocaleString('pt-BR', { minimumFractionDigits: 1 })}% — ${nivel}`;
}

function numerosRomaneioDigitados() {
  return document.getElementById('romaneioNumeros').value.split(/[^0-9]+/).filter(Boolean);
}

async function abrirRomaneio() {
  mostrarView('romaneio');
  if (!document.getElementById('romaneioDataEnvio').value) {
    document.getElementById('romaneioDataEnvio').value = new Date().toISOString().slice(0, 10);
  }
  await Promise.all([carregarHistoricoRomaneios(), carregarRelacoesRomaneio()]);
}

async function carregarRelacoesRomaneio() {
  const select = document.getElementById('romaneioCarga');
  const atual = select.value;
  const cargas = await fetch('/api/cargas').then(r => r.json());
  select.innerHTML = '<option value="">Selecione uma relação</option>' + cargas
    .filter(c => c.status !== 'finalizada')
    .map(c => `<option value="${c.id}">Nº ${String(c.numero).padStart(5, '0')} — ${escaparHtml(c.cliente || 'Sem cliente')} (${c.quantidade_pallets || 0} pallets)</option>`).join('');
  select.value = cargas.some(c => String(c.id) === atual && c.status !== 'finalizada') ? atual : '';
}

function limparPreviewRomaneio() {
  previewRomaneioValido = false;
  document.getElementById('romaneioCliente').textContent = '—';
  document.getElementById('romaneioQtdPallets').textContent = '0';
  document.getElementById('romaneioVolumes').textContent = '0';
  document.getElementById('romaneioPesoLiquido').textContent = '0,00 kg';
  document.getElementById('romaneioPesoBruto').textContent = '0,00 kg';
  document.getElementById('romaneioAderencia').textContent = '—';
}

async function conferirRomaneio() {
  const numeros = numerosRomaneioDigitados();
  const aviso = document.getElementById('romaneioAviso');
  const tbody = document.querySelector('#tabelaPreviewRomaneio tbody');
  limparPreviewRomaneio();
  aviso.style.display = 'none';
  const cargaId = document.getElementById('romaneioCarga').value;
  if (!cargaId) {
    tbody.innerHTML = '<tr><td colspan="8">Selecione uma relação de carga.</td></tr>';
    return false;
  }
  if (!numeros.length) {
    tbody.innerHTML = '<tr><td colspan="8">Informe ao menos um número de packing list.</td></tr>';
    return false;
  }
  tbody.innerHTML = '<tr><td colspan="8">Conferindo...</td></tr>';
  try {
    const resp = await fetch('/api/romaneios/preview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ numerosPallets: numeros, cargaId }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || 'Não foi possível conferir os packing lists.');
    const linhas = [];
    dados.pallets.forEach(p => (p.itens || []).forEach((i, indice) => linhas.push(`
      <tr><td>${indice === 0 ? String(p.numero).padStart(5, '0') : ''}</td><td>${escaparHtml(i.tipo || (p.modulo === 'fios' ? 'FIO' : 'PAINEL/KIT'))}</td>
      <td>${escaparHtml(i.codigo_produto || '')}</td><td class="celula-descricao">${escaparHtml(i.descricao || '')}</td>
      <td>${escaparHtml(i.op || '')}</td><td>${escaparHtml(i.oc || '')}</td><td>${escaparHtml(i.ncm || '')}</td>
      <td>${Number(i.qtde || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td></tr>`)));
    tbody.innerHTML = linhas.join('') || '<tr><td colspan="8">Os pallets não possuem itens.</td></tr>';
    document.getElementById('romaneioCliente').textContent = dados.clienteNome || dados.clienteCodigo || '—';
    document.getElementById('romaneioQtdPallets').textContent = dados.pallets.length;
    document.getElementById('romaneioVolumes').textContent = dados.volumes;
    document.getElementById('romaneioPesoLiquido').textContent = `${Number(dados.pesoLiquido).toLocaleString('pt-BR', { minimumFractionDigits: 2 })} kg`;
    document.getElementById('romaneioPesoBruto').textContent = `${Number(dados.pesoBruto).toLocaleString('pt-BR', { minimumFractionDigits: 2 })} kg`;
    document.getElementById('romaneioAderencia').textContent = textoAderencia(dados.comparacaoCarga.percentual);
    previewRomaneioValido = true;
    return true;
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="8">Corrija os dados informados para continuar.</td></tr>';
    aviso.textContent = e.message;
    aviso.style.display = 'inline-block';
    return false;
  }
}

async function carregarHistoricoRomaneios() {
  const tbody = document.querySelector('#tabelaHistoricoRomaneios tbody');
  try {
    const linhas = await fetch('/api/romaneios').then(r => r.json());
    tbody.innerHTML = linhas.map(r => `<tr><td><strong>${escaparHtml(r.codigo || r.numero)}</strong></td>
      <td>${r.carga_numero ? String(r.carga_numero).padStart(5, '0') : '—'}</td>
      <td><strong>${r.aderencia_carga == null ? '—' : textoAderencia(r.aderencia_carga)}</strong></td>
      <td>${r.data_envio ? new Date(`${r.data_envio}T00:00:00`).toLocaleDateString('pt-BR') : ''}</td>
      <td>${escaparHtml(r.cliente_nome || '')}</td><td>${escaparHtml(r.frete || '')}</td>
      <td>${escaparHtml(r.transportadora || '')}</td><td>${r.quantidade_pallets || 0}</td>
      <td>${Number(r.peso_bruto || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })} kg</td>
      <td>${r.arquivo_pdf ? `<a href="/api/romaneios/${r.id}/pdf" target="_blank">abrir</a>` : ''}</td>
      <td><button class="btn-excluir-romaneio" data-id="${r.id}" data-numero="${escaparHtml(r.codigo || r.numero)}">Excluir</button></td></tr>`).join('') || '<tr><td colspan="11">Nenhum romaneio emitido.</td></tr>';
  } catch (e) { tbody.innerHTML = '<tr><td colspan="11">Erro ao carregar o histórico.</td></tr>'; }
}

document.querySelector('#tabelaHistoricoRomaneios tbody').addEventListener('click', async e => {
  const btn = e.target.closest('.btn-excluir-romaneio');
  if (!btn || !confirm(`Excluir definitivamente o Romaneio Nº ${btn.dataset.numero}?\n\nOs pallets voltarão ao estoque e a relação será reaberta.`)) return;
  const resp = await fetch(`/api/romaneios/${btn.dataset.id}`, {method: 'DELETE'});
  const dados = await resp.json();
  if (!resp.ok) return alert(dados.erro || 'Não foi possível excluir o Romaneio.');
  alert(`Romaneio excluído. ${dados.palletsRestaurados} pallet(s) retornaram ao estoque.`);
  await Promise.all([carregarHistoricoRomaneios(), carregarRelacoesRomaneio()]);
});

document.getElementById('romaneioNumeros').addEventListener('input', limparPreviewRomaneio);
document.getElementById('romaneioCarga').addEventListener('change', limparPreviewRomaneio);
document.getElementById('btnConferirRomaneio').addEventListener('click', conferirRomaneio);

document.getElementById('btnGerarRomaneio').addEventListener('click', async () => {
  const numeros = numerosRomaneioDigitados();
  const cargaId = document.getElementById('romaneioCarga').value;
  if (!cargaId) return alert('Selecione uma relação de carga.');
  if (!numeros.length) return alert('Informe ao menos um número de packing list.');
  if (!previewRomaneioValido && !(await conferirRomaneio())) return;
  if (!confirm(`Gerar o romaneio e dar baixa em ${numeros.length} pallet(s) do estoque?`)) return;
  const btn = document.getElementById('btnGerarRomaneio');
  btn.disabled = true;
  try {
    const resp = await fetch('/api/romaneios', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        numerosPallets: numeros, dataEnvio: document.getElementById('romaneioDataEnvio').value,
        frete: document.getElementById('romaneioFrete').value, transportadora: document.getElementById('romaneioTransportadora').value,
        veiculo: document.getElementById('romaneioVeiculo').value, motorista: document.getElementById('romaneioMotorista').value,
        observacao: document.getElementById('romaneioObservacao').value, cargaId,
      }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || 'Não foi possível gerar o romaneio.');
    alert(`Romaneio Nº ${dados.codigo} gerado. Aderência à relação: ${Number(dados.aderenciaCarga).toLocaleString('pt-BR', {minimumFractionDigits:1})}%.`);
    document.getElementById('romaneioNumeros').value = '';
    limparPreviewRomaneio();
    await carregarHistoricoRomaneios();
    await carregarRelacoesRomaneio();
    window.open(`/api/romaneios/${dados.id}/pdf`, '_blank');
  } catch (e) { alert(e.message); }
  finally { btn.disabled = false; }
});

// ==========================================
// HISTORICO
// ==========================================
async function abrirHistorico() {
  mostrarView('historico');
  await carregarHistorico();
}

async function carregarHistorico() {
  const busca = document.getElementById('buscaHistorico').value;
  const modulo = document.getElementById('filtroModuloHistorico').value;
  const params = new URLSearchParams({ busca, modulo });
  const linhas = await fetch(`/api/pallets?${params}`).then(r => r.json());
  document.getElementById('contadorHistorico').textContent = `${linhas.length} registro(s)`;
  document.querySelector('#tabelaHistorico tbody').innerHTML = linhas
    .map(
      l => `
      <tr>
        <td><strong>${String(l.numero).padStart(5, '0')}</strong></td>
        <td>${titulos[l.modulo] || l.modulo}</td>
        <td>${new Date(l.data_hora).toLocaleString('pt-BR')}</td>
        <td>${l.cliente_nome || ''}</td>
        <td>${l.carreteis ?? ''}</td>
        <td>${(l.peso_liquido ?? 0).toFixed ? l.peso_liquido.toFixed(2) : l.peso_liquido}</td>
        <td>${(l.peso_bruto ?? 0).toFixed ? l.peso_bruto.toFixed(2) : l.peso_bruto}</td>
        <td>${l.arquivo_pdf ? `<a href="/api/pallets/${l.id}/pdf" target="_blank">abrir</a>` : ''}</td>
        <td><button class="btn-excluir-packing" data-id="${l.id}" data-numero="${l.numero}" ${l.status === 'expedido' ? 'disabled title="Packing list já expedido"' : ''}>Excluir</button></td>
      </tr>`
    )
    .join('');
}

document.getElementById('buscaHistorico').addEventListener('input', debounce(carregarHistorico, 300));
document.getElementById('filtroModuloHistorico').addEventListener('change', carregarHistorico);

document.querySelector('#tabelaHistorico tbody').addEventListener('click', async e => {
  const btn = e.target.closest('.btn-excluir-packing');
  if (!btn || btn.disabled) return;
  const numero = String(btn.dataset.numero).padStart(5, '0');
  if (!confirm(`Excluir definitivamente o Packing List Nº ${numero}?\n\nEle também será removido do estoque e das relações de carga.`)) return;
  btn.disabled = true;
  try {
    const resp = await fetch(`/api/pallets/${btn.dataset.id}`, { method: 'DELETE' });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || 'Não foi possível excluir.');
    await carregarHistorico();
    carregarStatus();
    alert(`Packing List Nº ${numero} excluído.`);
  } catch (erro) {
    alert(erro.message);
    btn.disabled = false;
  }
});

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// ==========================================
// DADOS DO ERP (CACHE LOCAL EDITAVEL)
// ==========================================
function escaparHtml(valor) {
  return String(valor ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function abrirDadosErp() {
  mostrarView('dadosErp');
  await carregarDadosErp();
}

async function carregarDadosErp() {
  const busca = document.getElementById('buscaDadosErp').value.trim();
  const modulo = document.getElementById('filtroModuloDadosErp').value;
  const params = new URLSearchParams({ busca, modulo });
  const tbody = document.querySelector('#tabelaDadosErp tbody');
  tbody.innerHTML = '<tr><td colspan="9">Carregando...</td></tr>';
  try {
    const resp = await fetch(`/api/cache-ordens?${params}`);
    const tipoResposta = resp.headers.get('content-type') || '';
    if (!tipoResposta.includes('application/json')) {
      throw new Error('Servidor desatualizado. Feche o servidor, execute iniciar.bat novamente e recarregue esta página.');
    }
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || 'Falha ao carregar as linhas.');
    const complemento = dados.total > dados.limite ? ` (mostrando as primeiras ${dados.limite})` : '';
    document.getElementById('contadorDadosErp').textContent = `${dados.total} linha(s)${complemento}`;
    tbody.innerHTML = dados.linhas.map(l => `
      <tr data-modulo="${escaparHtml(l.modulo)}" data-op-original="${escaparHtml(l.op)}">
        <td>${l.modulo === 'fios' ? 'Fios' : 'Painel/Kits'}</td>
        <td><input class="tabela-input campo-op-erp" value="${escaparHtml(l.op)}" /></td>
        <td><input class="tabela-input campo-oc-erp" value="${escaparHtml(l.oc)}" /></td>
        <td><input class="tabela-input campo-pedido-erp" value="${escaparHtml(l.pedido)}" /></td>
        <td><input class="tabela-input campo-produto-erp" value="${escaparHtml(l.codigo_produto)}" /></td>
        <td><input class="tabela-input campo-descricao-erp" value="${escaparHtml(l.descricao)}" /></td>
        <td><input class="tabela-input campo-cliente-erp" value="${escaparHtml(l.codigo_cliente)}" /></td>
        <td><input class="tabela-input campo-isolacao-erp" value="${escaparHtml(l.isolacao)}" /></td>
        <td><button type="button" class="btn-primary btn-salvar-linha-erp">Salvar</button></td>
      </tr>`).join('') || '<tr><td colspan="9">Nenhuma linha encontrada.</td></tr>';
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="9">${escaparHtml(e.message)}</td></tr>`;
  }
}

document.getElementById('buscaDadosErp').addEventListener('input', debounce(carregarDadosErp, 300));
document.getElementById('filtroModuloDadosErp').addEventListener('change', carregarDadosErp);

document.querySelector('#tabelaDadosErp tbody').addEventListener('click', async e => {
  const btn = e.target.closest('.btn-salvar-linha-erp');
  if (!btn) return;
  const tr = btn.closest('tr');
  const payload = {
    op: tr.querySelector('.campo-op-erp').value,
    oc: tr.querySelector('.campo-oc-erp').value,
    pedido: tr.querySelector('.campo-pedido-erp').value,
    codigo_produto: tr.querySelector('.campo-produto-erp').value,
    descricao: tr.querySelector('.campo-descricao-erp').value,
    codigo_cliente: tr.querySelector('.campo-cliente-erp').value,
    isolacao: tr.querySelector('.campo-isolacao-erp').value,
  };
  btn.disabled = true;
  btn.textContent = 'Salvando...';
  try {
    const url = `/api/cache-ordens/${encodeURIComponent(tr.dataset.modulo)}/${encodeURIComponent(tr.dataset.opOriginal)}`;
    const resp = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const tipoResposta = resp.headers.get('content-type') || '';
    if (!tipoResposta.includes('application/json')) {
      throw new Error('Servidor desatualizado. Reinicie o iniciar.bat e tente novamente.');
    }
    const dados = await resp.json();
    if (!resp.ok || !dados.ok) throw new Error(dados.erro || 'Não foi possível salvar.');
    tr.dataset.opOriginal = dados.op;
    tr.classList.add('linha-salva');
    btn.textContent = 'Salvo ✓';
    setTimeout(() => {
      tr.classList.remove('linha-salva');
      btn.textContent = 'Salvar';
    }, 1600);
  } catch (erro) {
    alert('Erro ao salvar linha: ' + erro.message);
    btn.textContent = 'Salvar';
  } finally {
    btn.disabled = false;
  }
});

// ==========================================
// CONFIGURACOES
// ==========================================
async function abrirConfig() {
  mostrarView('config');
  await Promise.all([carregarPaletesConfig(), carregarAbrevConfig()]);
}

async function carregarPaletesConfig() {
  const linhas = await fetch('/api/paletes').then(r => r.json());
  document.querySelector('#tabelaPaletesConfig tbody').innerHTML = linhas
    .map(p => `<tr><td>${p.medida}</td><td>${p.peso_tara} kg</td></tr>`)
    .join('');
}

document.getElementById('btnAddPalete').addEventListener('click', async () => {
  const medida = document.getElementById('novaMedida').value.trim();
  const pesoTara = document.getElementById('novoPesoTara').value;
  if (!medida || !pesoTara) return alert('Preencha medida e peso.');
  await fetch('/api/paletes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ medida, pesoTara }),
  });
  document.getElementById('novaMedida').value = '';
  document.getElementById('novoPesoTara').value = '';
  carregarPaletesConfig();
});

async function carregarAbrevConfig() {
  const linhas = await fetch('/api/clientes/abrev').then(r => r.json());
  document.querySelector('#tabelaAbrevConfig tbody').innerHTML = linhas
    .map(c => `<tr><td>${c.codigo}</td><td>${c.abreviacao}</td></tr>`)
    .join('');
}

document.getElementById('btnAddAbrev').addEventListener('click', async () => {
  const codigo = document.getElementById('novoCodigoCliente').value.trim();
  const abreviacao = document.getElementById('novaAbrev').value.trim();
  if (!codigo || !abreviacao) return alert('Preencha código e abreviação.');
  await fetch('/api/clientes/abrev', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codigo, abreviacao }),
  });
  document.getElementById('novoCodigoCliente').value = '';
  document.getElementById('novaAbrev').value = '';
  carregarAbrevConfig();
});

document.getElementById('btnGerarPdfTesteFios').addEventListener('click', () => {
  window.open('/api/pdf/teste?modulo=fios', '_blank');
});

document.getElementById('btnGerarPdfTestePainel').addEventListener('click', () => {
  window.open('/api/pdf/teste?modulo=painel', '_blank');
});

// ==========================================
// INICIALIZACAO
// ==========================================
carregarStatus();
