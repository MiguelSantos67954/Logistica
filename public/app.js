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
  programacaoCarregamento: document.getElementById('view-programacao-carregamento'),
  administracao: document.getElementById('view-administracao'),
};

let moduloAtual = 'fios'; // 'fios' | 'painel'
let paletesCache = [];
let linhaSeq = 0;
let usuarioAtual = null;

function mostrarView(nome) {
  Object.values(views).forEach(v => (v.style.display = 'none'));
  views[nome].style.display = 'block';
}

document.querySelectorAll('[data-abrir]').forEach(btn => {
  btn.addEventListener('click', () => {
    const alvo = btn.dataset.abrir;
    fetch('/api/auth/atividade', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({modulo:alvo})}).catch(() => {});
    if (alvo === 'identificacao-pallets') mostrarView('identificacao');
    else if (alvo === 'relacao-carga') abrirRelacaoCarga();
    else if (alvo === 'romaneio') abrirRomaneio();
    else if (alvo === 'programacao-carregamento') abrirProgramacaoCarregamento();
    else if (alvo === 'administracao') abrirAdministracao();
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
document.getElementById('btnVoltarProgramacao').addEventListener('click', () => { mostrarView('home'); carregarStatus(); });
document.getElementById('btnVoltarAdmin').addEventListener('click', () => mostrarView('home'));

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
    const badge = document.getElementById('carregamentosHoje');
    const totalHoje = Number(s.carregamentosHoje || 0);
    badge.textContent = `${totalHoje} carregamento${totalHoje === 1 ? '' : 's'} hoje`;
    badge.hidden = totalHoje === 0;
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
      <td><button class="btn-fotos-romaneio" data-id="${r.id}" data-numero="${escaparHtml(r.codigo || r.numero)}">Fotos</button> <button class="btn-excluir-romaneio" data-id="${r.id}" data-numero="${escaparHtml(r.codigo || r.numero)}">Excluir</button></td></tr>`).join('') || '<tr><td colspan="11">Nenhum romaneio emitido.</td></tr>';
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

// ==========================================
// PROGRAMAÇÃO DE CARREGAMENTO
// Adaptado do módulo original do Portal PCP.
// ==========================================
let mesCalendarioCarga = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let carregamentos = [];
const cargaISO = data => `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}-${String(data.getDate()).padStart(2, '0')}`;
const cargaData = iso => iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('pt-BR') : '';
const cargaHtml = valor => String(valor ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

function abrirProgramacaoCarregamento() {
  mostrarView('programacaoCarregamento');
  if (!document.getElementById('carregamentoData').value) document.getElementById('carregamentoData').value = cargaISO(new Date());
  ativarAbaCarregamento('timeline');
}

function pode(permissao) {
  return Boolean(usuarioAtual && (usuarioAtual.administrador || usuarioAtual.permissoes?.[permissao]));
}

function ativarAbaCarregamento(nome) {
  document.querySelectorAll('.carregamento-aba-btn').forEach(b => b.classList.toggle('ativo', b.dataset.carregamentoAba === nome));
  document.querySelectorAll('.carregamento-aba').forEach(a => a.style.display = a.id === `carregamento-aba-${nome}` ? 'block' : 'none');
  if (nome === 'timeline') carregarTimelineCargas();
  else if (nome === 'calendario') carregarCalendarioCargas();
  else if (nome === 'historico') carregarCarregamentosAntigos();
  else carregarListaCarregamentos();
}
document.querySelectorAll('.carregamento-aba-btn').forEach(b => b.addEventListener('click', () => ativarAbaCarregamento(b.dataset.carregamentoAba)));

async function buscarCarregamentos(inicio = '', fim = '') {
  const params = new URLSearchParams();
  if (inicio) params.set('inicio', inicio);
  if (fim) params.set('fim', fim);
  const resposta = await fetch(`/api/carregamentos?${params}`), dados = await resposta.json();
  if (!resposta.ok) throw new Error(dados.erro || 'Não foi possível carregar os carregamentos.');
  return dados;
}

async function carregarTimelineCargas() {
  const input = document.getElementById('timelineData');
  if (!input.value) input.value = cargaISO(new Date());
  const base = new Date(`${input.value}T12:00:00`), inicio = new Date(base), fim = new Date(base);
  inicio.setDate(inicio.getDate() - 1); fim.setDate(fim.getDate() + 7);
  const inicioISO = cargaISO(inicio), fimISO = cargaISO(fim), area = document.getElementById('timelineCargas');
  area.innerHTML = '<div class="empty-state">Carregando programação...</div>';
  try {
    carregamentos = (await buscarCarregamentos(inicioISO, fimISO)).sort((a,b) => `${a.data_carregamento} ${a.horario}`.localeCompare(`${b.data_carregamento} ${b.horario}`));
    const agora = new Date(), hoje = cargaISO(agora), hora = agora.toTimeString().slice(0,5);
    const proxima = carregamentos.find(c => c.data_carregamento > hoje || (c.data_carregamento === hoje && c.horario >= hora));
    document.getElementById('timelineTotal').textContent = carregamentos.length;
    document.getElementById('timelineClientes').textContent = new Set(carregamentos.map(c => c.cliente.trim().toUpperCase())).size;
    document.getElementById('timelineProxima').textContent = proxima?.horario || '—';
    document.getElementById('timelineProximaInfo').textContent = proxima ? `${proxima.caminhao} · ${proxima.cliente}` : 'Nenhuma carga pendente';
    document.getElementById('timelineTituloDia').textContent = `${cargaData(inicioISO)} a ${cargaData(fimISO)}`;
    document.getElementById('timelineRelogio').textContent = input.value === hoje ? `Agora: ${hora}` : `Referência: ${cargaData(input.value)}`;
    area.innerHTML = Array.from({length: 9}, (_, i) => { const d = new Date(inicio); d.setDate(d.getDate() + i); return d; }).map(d => {
      const iso = cargaISO(d), linhas = carregamentos.filter(c => c.data_carregamento === iso);
      const rotulo = iso === hoje ? 'Hoje' : iso === inicioISO ? 'Ontem' : d.toLocaleDateString('pt-BR', {weekday:'long'});
      const eventos = linhas.length ? linhas.map(c => {
        const passou = c.data_carregamento < hoje || (c.data_carregamento === hoje && c.horario < hora);
        const status = passou ? 'realizada' : (proxima && Number(c.id) === Number(proxima.id) ? 'proxima' : 'programada');
        return `<article class="timeline-item timeline-${status}" data-editar-carregamento="${c.id}"><div class="timeline-hora"><strong>${cargaHtml(c.horario)}</strong><span>${status === 'realizada' ? 'Horário encerrado' : status === 'proxima' ? 'Próxima carga' : 'Programada'}</span></div><div class="timeline-marker"><i></i></div><div class="timeline-card"><div class="timeline-card-top"><strong>${cargaHtml(c.caminhao)}</strong><span>${cargaHtml(c.cliente)}</span></div><h4>${cargaHtml(c.material)}</h4>${c.observacao ? `<p>${cargaHtml(c.observacao)}</p>` : ''}</div></article>`;
      }).join('') : '<div class="timeline-day-empty">Nenhuma carga programada</div>';
      return `<div class="timeline-date-divider ${iso === hoje ? 'timeline-date-today' : ''}"><strong>${cargaHtml(rotulo)}</strong><span>${cargaData(iso)}</span></div>${eventos}`;
    }).join('');
  } catch (erro) { area.innerHTML = `<div class="empty-state">${cargaHtml(erro.message)}</div>`; }
}

function cartaoCarregamento(c, editar = true) {
  return `<article class="carregamento-item"><div class="carregamento-data"><strong>${cargaData(c.data_carregamento)}</strong><span>${cargaHtml(c.horario)}</span></div><div class="carregamento-info"><strong>${cargaHtml(c.caminhao)}</strong><span>${cargaHtml(c.material)} · ${cargaHtml(c.cliente)}</span>${c.observacao ? `<small>${cargaHtml(c.observacao)}</small>` : ''}</div><div class="carregamento-acoes">${editar && pode('carregamento_editar') ? `<button type="button" class="btn-icon" data-editar-carregamento="${c.id}" title="Editar">✏️</button>` : ''}${pode('carregamento_excluir') ? `<button type="button" class="btn-icon danger" data-excluir-carregamento="${c.id}" title="Excluir">🗑️</button>` : ''}</div></article>`;
}
async function carregarListaCarregamentos() {
  const lista = document.getElementById('listaCarregamentos');
  try { carregamentos = await buscarCarregamentos(cargaISO(new Date())); lista.innerHTML = carregamentos.length ? carregamentos.map(c => cartaoCarregamento(c)).join('') : '<div class="empty-state">Nenhum carregamento programado a partir de hoje.</div>'; }
  catch (erro) { lista.innerHTML = `<div class="empty-state">${cargaHtml(erro.message)}</div>`; }
}
async function carregarCarregamentosAntigos() {
  const lista = document.getElementById('listaCarregamentosAntigos'), ontem = new Date(); ontem.setDate(ontem.getDate() - 1);
  try { carregamentos = (await buscarCarregamentos('', cargaISO(ontem))).reverse(); lista.innerHTML = carregamentos.length ? carregamentos.map(c => cartaoCarregamento(c, false)).join('') : '<div class="empty-state">Nenhum carregamento antigo encontrado.</div>'; }
  catch (erro) { lista.innerHTML = `<div class="empty-state">${cargaHtml(erro.message)}</div>`; }
}
function limparFormularioCarregamento() {
  document.getElementById('formCarregamento').reset(); document.getElementById('carregamentoId').value = ''; document.getElementById('carregamentoData').value = cargaISO(new Date());
  document.getElementById('tituloFormularioCarregamento').textContent = 'Novo carregamento'; document.getElementById('btnSalvarCarregamento').textContent = 'Salvar carregamento'; document.getElementById('btnCancelarEdicao').style.display = 'none';
}
function editarCarregamento(id) {
  if (!pode('carregamento_editar')) return alert('Você não tem permissão para editar carregamentos.');
  const c = carregamentos.find(item => Number(item.id) === Number(id)); if (!c) return;
  document.getElementById('carregamentoId').value = c.id;
  for (const [sufixo, chave] of Object.entries({Data:'data_carregamento',Horario:'horario',Caminhao:'caminhao',Material:'material',Cliente:'cliente',Observacao:'observacao'})) document.getElementById(`carregamento${sufixo}`).value = c[chave] || '';
  document.getElementById('tituloFormularioCarregamento').textContent = 'Editar carregamento'; document.getElementById('btnSalvarCarregamento').textContent = 'Salvar alterações'; document.getElementById('btnCancelarEdicao').style.display = 'inline-block'; ativarAbaCarregamento('adicionar');
}
async function excluirCarregamento(id) {
  if (!pode('carregamento_excluir')) return alert('Você não tem permissão para excluir carregamentos.');
  if (!confirm('Excluir este carregamento permanentemente?')) return;
  const resposta = await fetch(`/api/carregamentos/${id}`, {method:'DELETE'}), dados = await resposta.json();
  if (!resposta.ok) return alert(dados.erro || 'Não foi possível excluir.');
  ativarAbaCarregamento(document.querySelector('.carregamento-aba-btn.ativo').dataset.carregamentoAba); carregarStatus();
}
document.getElementById('formCarregamento').addEventListener('submit', async e => {
  e.preventDefault(); const id = document.getElementById('carregamentoId').value;
  if (!pode(id ? 'carregamento_editar' : 'carregamento_criar')) return alert('Você não tem permissão para esta ação.');
  const dados = {data_carregamento:document.getElementById('carregamentoData').value, horario:document.getElementById('carregamentoHorario').value, caminhao:document.getElementById('carregamentoCaminhao').value.trim(), material:document.getElementById('carregamentoMaterial').value.trim(), cliente:document.getElementById('carregamentoCliente').value.trim(), observacao:document.getElementById('carregamentoObservacao').value.trim()};
  try { const resposta = await fetch(id ? `/api/carregamentos/${id}` : '/api/carregamentos', {method:id?'PUT':'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(dados)}), resultado = await resposta.json(); if (!resposta.ok) throw new Error(resultado.erro || 'Não foi possível salvar.'); limparFormularioCarregamento(); await carregarListaCarregamentos(); carregarStatus(); }
  catch (erro) { alert(erro.message); }
});
document.getElementById('btnCancelarEdicao').addEventListener('click', limparFormularioCarregamento);
for (const id of ['listaCarregamentos','listaCarregamentosAntigos','timelineCargas','gradeCalendario']) document.getElementById(id).addEventListener('click', e => { const editar = e.target.closest('[data-editar-carregamento]'), excluir = e.target.closest('[data-excluir-carregamento]'); if (editar) editarCarregamento(editar.dataset.editarCarregamento); if (excluir) excluirCarregamento(excluir.dataset.excluirCarregamento); });
document.getElementById('timelineData').addEventListener('change', carregarTimelineCargas);

async function carregarCalendarioCargas() {
  const primeiro = new Date(mesCalendarioCarga.getFullYear(), mesCalendarioCarga.getMonth(), 1), ultimo = new Date(mesCalendarioCarga.getFullYear(), mesCalendarioCarga.getMonth() + 1, 0);
  document.getElementById('tituloCalendario').textContent = primeiro.toLocaleDateString('pt-BR', {month:'long', year:'numeric'});
  try { carregamentos = await buscarCarregamentos(cargaISO(primeiro), cargaISO(ultimo)); const dias = Array.from({length:primeiro.getDay()}, () => '<div class="calendar-day calendar-day-empty"></div>'); for (let dia=1; dia<=ultimo.getDate(); dia++) { const iso = cargaISO(new Date(primeiro.getFullYear(), primeiro.getMonth(), dia)), eventos = carregamentos.filter(c => c.data_carregamento === iso); dias.push(`<div class="calendar-day ${iso === cargaISO(new Date()) ? 'calendar-today' : ''}"><span class="calendar-date">${dia}</span><div class="calendar-events">${eventos.map(c => `<button class="calendar-event" data-editar-carregamento="${c.id}"><strong>${cargaHtml(c.horario)} · ${cargaHtml(c.caminhao)}</strong><span>${cargaHtml(c.material)}</span><small>${cargaHtml(c.cliente)}</small></button>`).join('')}</div></div>`); } document.getElementById('gradeCalendario').innerHTML = dias.join(''); }
  catch (erro) { document.getElementById('gradeCalendario').innerHTML = `<div class="empty-state">${cargaHtml(erro.message)}</div>`; }
}
document.getElementById('btnMesAnterior').addEventListener('click', () => { mesCalendarioCarga = new Date(mesCalendarioCarga.getFullYear(), mesCalendarioCarga.getMonth()-1, 1); carregarCalendarioCargas(); });
document.getElementById('btnMesProximo').addEventListener('click', () => { mesCalendarioCarga = new Date(mesCalendarioCarga.getFullYear(), mesCalendarioCarga.getMonth()+1, 1); carregarCalendarioCargas(); });
document.getElementById('btnHojeCalendario').addEventListener('click', () => { mesCalendarioCarga = new Date(new Date().getFullYear(), new Date().getMonth(), 1); carregarCalendarioCargas(); });

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
      method: 'POST',
      body: formularioFotos({
        numerosPallets: numeros, dataEnvio: document.getElementById('romaneioDataEnvio').value,
        frete: document.getElementById('romaneioFrete').value, transportadora: document.getElementById('romaneioTransportadora').value,
        veiculo: document.getElementById('romaneioVeiculo').value, motorista: document.getElementById('romaneioMotorista').value,
        observacao: document.getElementById('romaneioObservacao').value, cargaId,
      }),
    });
    const dados = await respostaFotos(resp);
    if (!resp.ok) throw new Error(dados.erro || 'Não foi possível gerar o romaneio.');
    alert(`Romaneio Nº ${dados.codigo} gerado. Aderência à relação: ${Number(dados.aderenciaCarga).toLocaleString('pt-BR', {minimumFractionDigits:1})}%.`);
    limparFotosSelecionadas();
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
function aplicarPermissoes() {
  const modulos = {
    'identificacao-pallets': 'identificacao_pallets',
    'relacao-carga': 'relacao_carga', romaneio: 'romaneio',
    'programacao-carregamento': 'programacao_carregamento',
  };
  for (const [modulo, permissao] of Object.entries(modulos)) {
    const card = document.querySelector(`[data-modulo="${modulo}"]`);
    if (card) card.hidden = !pode(permissao);
  }
  document.getElementById('cardAdministracao').hidden = !usuarioAtual.administrador;
  document.getElementById('btnAdmin').hidden = !usuarioAtual.administrador;
  document.querySelector('[data-carregamento-aba="adicionar"]').hidden = !(pode('carregamento_criar') || pode('carregamento_editar'));
}

function mostrarLogin() {
  usuarioAtual = null;
  Object.values(views).forEach(v => v.style.display = 'none');
  document.getElementById('barraSessao').hidden = true;
  document.getElementById('view-login').style.display = 'grid';
  document.getElementById('loginSenha').value = '';
  document.getElementById('loginUsuario').focus();
}

async function inicializarSessao() {
  try {
    const resposta = await fetch('/api/auth/me');
    if (!resposta.ok) return mostrarLogin();
    usuarioAtual = await resposta.json();
    document.getElementById('view-login').style.display = 'none';
    document.getElementById('barraSessao').hidden = false;
    document.getElementById('usuarioAtualNome').textContent = usuarioAtual.nome;
    aplicarPermissoes(); mostrarView('home'); carregarStatus();
  } catch (_) { mostrarLogin(); }
}

document.getElementById('formLogin').addEventListener('submit', async e => {
  e.preventDefault();
  const erro = document.getElementById('loginErro'); erro.hidden = true;
  const botao = e.currentTarget.querySelector('button[type="submit"]'); botao.disabled = true;
  try {
    const resposta = await fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({login:document.getElementById('loginUsuario').value.trim(), senha:document.getElementById('loginSenha').value})});
    const dados = await resposta.json(); if (!resposta.ok) throw new Error(dados.erro || 'Não foi possível entrar.'); await inicializarSessao();
  } catch (e) { erro.textContent = e.message; erro.hidden = false; }
  finally { botao.disabled = false; }
});
document.getElementById('btnSair').addEventListener('click', async () => { await fetch('/api/auth/logout', {method:'POST'}); mostrarLogin(); });
document.getElementById('btnAdmin').addEventListener('click', abrirAdministracao);

let usuariosAdmin = [];
function abrirAdministracao() {
  if (!usuarioAtual?.administrador) return alert('Acesso exclusivo para administradores.');
  mostrarView('administracao'); ativarAbaAdmin('usuarios');
}
function ativarAbaAdmin(nome) {
  document.querySelectorAll('.admin-aba-btn').forEach(b => b.classList.toggle('ativo', b.dataset.adminAba === nome));
  document.querySelectorAll('.admin-aba').forEach(a => a.style.display = a.id === `admin-aba-${nome}` ? 'block' : 'none');
  if (nome === 'usuarios') carregarUsuariosAdmin(); else carregarAuditoria();
}
document.querySelectorAll('.admin-aba-btn').forEach(b => b.addEventListener('click', () => ativarAbaAdmin(b.dataset.adminAba)));

async function carregarUsuariosAdmin() {
  const resposta = await fetch('/api/admin/usuarios'), dados = await resposta.json();
  if (!resposta.ok) return alert(dados.erro || 'Não foi possível carregar os usuários.');
  usuariosAdmin = dados;
  const rotulos = {identificacao_pallets:'Pallets', relacao_carga:'Relação', romaneio:'Romaneio', programacao_carregamento:'Programação'};
  document.querySelector('#tabelaUsuarios tbody').innerHTML = dados.map(u => `<tr><td><strong>${cargaHtml(u.login)}</strong></td><td>${cargaHtml(u.nome)}</td><td>${u.administrador ? '<span class="tag-admin">Administrador</span>' : 'Usuário'}</td><td>${u.ativo ? '<span class="tag-ativo">Ativo</span>' : '<span class="tag-inativo">Bloqueado</span>'}</td><td>${u.administrador ? 'Todos' : Object.entries(rotulos).filter(([k]) => u.permissoes[k]).map(([,v]) => v).join(', ') || 'Nenhum'}</td><td><button class="btn-clear" data-editar-usuario="${u.id}">Editar</button></td></tr>`).join('');
}
function limparFormUsuario() {
  document.getElementById('formUsuario').reset(); document.getElementById('usuarioId').value = ''; document.getElementById('usuarioAtivo').checked = true;
  document.getElementById('tituloFormUsuario').textContent = 'Novo usuário'; document.getElementById('dicaSenhaUsuario').textContent = 'obrigatória para novo usuário'; document.getElementById('btnCancelarUsuario').hidden = true;
}
document.querySelector('#tabelaUsuarios tbody').addEventListener('click', e => {
  const btn = e.target.closest('[data-editar-usuario]'); if (!btn) return;
  const u = usuariosAdmin.find(x => Number(x.id) === Number(btn.dataset.editarUsuario)); if (!u) return;
  document.getElementById('usuarioId').value = u.id; document.getElementById('usuarioLogin').value = u.login; document.getElementById('usuarioNome').value = u.nome; document.getElementById('usuarioSenha').value = '';
  document.getElementById('usuarioAtivo').checked = u.ativo; document.getElementById('usuarioAdministrador').checked = u.administrador;
  document.querySelectorAll('[data-permissao]').forEach(c => c.checked = Boolean(u.permissoes[c.dataset.permissao]));
  document.getElementById('tituloFormUsuario').textContent = `Editar ${u.nome}`; document.getElementById('dicaSenhaUsuario').textContent = 'deixe em branco para manter'; document.getElementById('btnCancelarUsuario').hidden = false; document.getElementById('formUsuario').scrollIntoView({behavior:'smooth'});
});
document.getElementById('btnCancelarUsuario').addEventListener('click', limparFormUsuario);
document.getElementById('formUsuario').addEventListener('submit', async e => {
  e.preventDefault(); const id = document.getElementById('usuarioId').value;
  const permissoes = {}; document.querySelectorAll('[data-permissao]').forEach(c => permissoes[c.dataset.permissao] = c.checked);
  const dados = {login:document.getElementById('usuarioLogin').value.trim(), nome:document.getElementById('usuarioNome').value.trim(), senha:document.getElementById('usuarioSenha').value, ativo:document.getElementById('usuarioAtivo').checked, administrador:document.getElementById('usuarioAdministrador').checked, permissoes};
  if (!id && !dados.senha) return alert('Informe a senha do novo usuário.');
  const resposta = await fetch(id ? `/api/admin/usuarios/${id}` : '/api/admin/usuarios', {method:id?'PUT':'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(dados)}), resultado = await resposta.json();
  if (!resposta.ok) return alert(resultado.erro || 'Não foi possível salvar o usuário.');
  limparFormUsuario(); await carregarUsuariosAdmin();
});

async function carregarAuditoria() {
  const filtro = document.getElementById('filtroUsuarioAuditoria').value.trim(), params = filtro ? `?usuario=${encodeURIComponent(filtro)}` : '';
  const resposta = await fetch(`/api/admin/auditoria${params}`), dados = await resposta.json();
  if (!resposta.ok) return alert(dados.erro || 'Não foi possível carregar o histórico.');
  document.querySelector('#tabelaAuditoria tbody').innerHTML = dados.length ? dados.map(a => `<tr><td>${cargaHtml(a.data_hora)}</td><td><strong>${cargaHtml(a.usuario)}</strong></td><td>${cargaHtml(a.acao)}</td><td>${cargaHtml(a.metodo || '')} ${cargaHtml(a.caminho || '')}</td><td>${a.status_http && a.status_http < 400 ? '<span class="tag-ativo">Sucesso</span>' : '<span class="tag-inativo">Falha</span>'}</td><td class="auditoria-detalhes">${cargaHtml(a.detalhes || '')}</td></tr>`).join('') : '<tr><td colspan="6">Nenhuma atividade encontrada.</td></tr>';
}
document.getElementById('btnFiltrarAuditoria').addEventListener('click', carregarAuditoria);
document.getElementById('filtroUsuarioAuditoria').addEventListener('keydown', e => { if (e.key === 'Enter') carregarAuditoria(); });

inicializarSessao();

// Fotos separadas por categoria, tanto na emissão quanto no histórico.
let fotosRomaneioId = null;
const fotosPendentes = { pallets: [], carga: [] };
const painelFotos = document.createElement('section');
painelFotos.className = 'aba';
painelFotos.innerHTML = `<h2 id="tituloFotos">Fotos do novo romaneio</h2>
  <p>JPG, PNG ou WebP. Até 10 MB por foto, 30 fotos e 50 MB por envio. As fotos serão incluídas no PDF.</p>
  <div class="fotos-categorias">${[['pallets', 'Fotos dos pallets'], ['carga', 'Fotos da carga completa']].map(([cat, titulo]) => `
    <div><h3>${titulo}</h3><label>Adicionar fotos<input type="file" data-categoria="${cat}" accept="image/jpeg,image/png,image/webp" multiple></label>
    <div class="fotos-galeria" id="fotos-${cat}"></div></div>`).join('')}</div>
  <div id="acoesFotosHistorico" hidden><button type="button" id="salvarFotos" class="btn-primary">Salvar fotos</button>
  <button type="button" id="fecharFotos">Voltar ao novo romaneio</button></div>`;
document.querySelector('#view-romaneio .bloco-historico-romaneio').before(painelFotos);
function limparFotosSelecionadas() {
  for (const cat of ['pallets', 'carga']) {
    fotosPendentes[cat].forEach(f => URL.revokeObjectURL(f.url));
    fotosPendentes[cat] = [];
  }
  painelFotos.querySelectorAll('input').forEach(i => i.value = '');
  renderFotos();
}
function formularioFotos(dados) {
  const form = new FormData();
  if (dados) form.append('dados', JSON.stringify(dados));
  // Anexos do histórico nunca são enviados para uma nova emissão.
  if (!dados || fotosRomaneioId === null) {
    for (const cat of ['pallets', 'carga']) fotosPendentes[cat].forEach(f => form.append(cat, f.arquivo));
  }
  return form;
}
let fotosSalvas = [];
function renderFotos() {
  for (const cat of ['pallets', 'carga']) {
    document.getElementById(`fotos-${cat}`).innerHTML = fotosSalvas.filter(f => f.categoria === cat).map(f => `
      <figure><a href="/api/romaneios/${fotosRomaneioId}/fotos/${f.id}" target="_blank"><img src="/api/romaneios/${fotosRomaneioId}/fotos/${f.id}" alt="${cat === 'pallets' ? 'Pallets' : 'Carga completa'}"></a>
      <button type="button" data-excluir-foto="${f.id}">Excluir foto</button></figure>`).join('') + fotosPendentes[cat].map((f, i) => `
      <figure><img src="${f.url}" alt="Prévia da foto"><figcaption>${escaparHtml(f.arquivo.name)}</figcaption>
      <button type="button" data-remover="${i}" data-cat="${cat}">Remover seleção</button></figure>`).join('');
  }
}
painelFotos.addEventListener('change', e => {
  const cat = e.target.dataset.categoria;
  if (!cat) return;
  const arquivos = [...e.target.files];
  const todos = [...fotosPendentes.pallets, ...fotosPendentes.carga].map(f => f.arquivo).concat(arquivos);
  if (todos.length > 30 || todos.some(f => f.size > 10 * 1024 * 1024) || todos.reduce((n, f) => n + f.size, 0) > 49 * 1024 * 1024) {
    e.target.value = ''; return alert('Limite: 30 fotos, 10 MB por foto e 49 MB de arquivos por envio.');
  }
  arquivos.forEach(arquivo => fotosPendentes[cat].push({arquivo, url: URL.createObjectURL(arquivo)}));
  e.target.value = '';
  renderFotos();
});
async function respostaFotos(resp) {
  if (!(resp.headers.get('content-type') || '').includes('application/json')) {
    if ([404, 405, 415].includes(resp.status) || resp.ok) {
      throw new Error('O servidor está com uma versão anterior, sem suporte ao envio de fotos. Feche a janela do servidor, execute iniciar.bat novamente e atualize a página. Suas fotos selecionadas ainda não foram salvas.');
    }
    if (resp.status === 413) throw new Error('As fotos ultrapassam o limite de envio. Selecione menos fotos e tente novamente.');
    throw new Error(`O servidor não conseguiu salvar (HTTP ${resp.status}). Confira o erro na janela do servidor. As fotos selecionadas foram mantidas para tentar novamente.`);
  }
  const dados = await resp.json();
  if (!resp.ok) throw new Error(dados.erro || 'Não foi possível atualizar as fotos.');
  return dados;
}
painelFotos.addEventListener('click', async e => {
  const btn = e.target.closest('button');
  if (!btn) return;
  if (btn.dataset.remover !== undefined) {
    const [foto] = fotosPendentes[btn.dataset.cat].splice(Number(btn.dataset.remover), 1);
    URL.revokeObjectURL(foto.url); renderFotos(); return;
  }
  btn.disabled = true;
  try {
    if (btn.dataset.excluirFoto && confirm('Excluir esta foto do romaneio?')) {
      await respostaFotos(await fetch(`/api/romaneios/${fotosRomaneioId}/fotos/${btn.dataset.excluirFoto}`, {method: 'DELETE'}));
      fotosSalvas = fotosSalvas.filter(f => String(f.id) !== btn.dataset.excluirFoto);
      renderFotos();
    }
    if (btn.id === 'salvarFotos') {
      fotosSalvas = await respostaFotos(await fetch(`/api/romaneios/${fotosRomaneioId}/fotos`, {method: 'POST', body: formularioFotos()}));
      limparFotosSelecionadas();
      alert('Fotos salvas. Ao abrir o PDF, ele incluirá as fotos atualizadas.');
    }
    if (btn.id === 'fecharFotos') {
      if ((fotosPendentes.pallets.length || fotosPendentes.carga.length) && !confirm('Descartar as fotos ainda não salvas?')) return;
      fotosRomaneioId = null; fotosSalvas = []; limparFotosSelecionadas();
      document.getElementById('tituloFotos').textContent = 'Fotos do novo romaneio';
      document.getElementById('acoesFotosHistorico').hidden = true;
    }
  } catch (erro) { alert(erro.message); }
  finally { btn.disabled = false; }
});
document.querySelector('#tabelaHistoricoRomaneios tbody').addEventListener('click', async e => {
  const btn = e.target.closest('.btn-fotos-romaneio');
  if (!btn) return;
  if ((fotosPendentes.pallets.length || fotosPendentes.carga.length) && !confirm('Descartar as fotos selecionadas para abrir outro romaneio?')) return;
  try {
    const fotos = await respostaFotos(await fetch(`/api/romaneios/${btn.dataset.id}/fotos`));
    fotosRomaneioId = Number(btn.dataset.id); fotosSalvas = fotos; limparFotosSelecionadas();
    document.getElementById('tituloFotos').textContent = `Fotos do romaneio ${btn.dataset.numero}`;
    document.getElementById('acoesFotosHistorico').hidden = false;
    painelFotos.scrollIntoView({behavior: 'smooth'});
  } catch (erro) { alert(erro.message); }
});
