import os
import json
import secrets
from io import BytesIO
from src.fotos import ler_uploads, salvar_fotos, fotos_pdf
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory, send_file, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

from paths import base_dir
from db import get_connection
from src.refresh import refresh_tudo
from src.mssql import load_config
from src.etiqueta import gerar_pdf_etiqueta
from src.romaneio import gerar_pdf_romaneio
from src.relacao_carga import gerar_pdf_relacao_carga

app = Flask(__name__, static_folder=os.path.join(base_dir(), 'public'), static_url_path='')
CORS(app, supports_credentials=True)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

with get_connection() as _conn:
    _segredo = _conn.execute("SELECT valor FROM meta WHERE chave='chave_sessao'").fetchone()
    if not _segredo:
        _valor_segredo = secrets.token_hex(32)
        _conn.execute("INSERT INTO meta (chave, valor) VALUES ('chave_sessao', ?)", (_valor_segredo,))
    else:
        _valor_segredo = _segredo['valor']
app.secret_key = os.environ.get('PORTAL_LOGISTICA_SECRET') or _valor_segredo
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

PERMISSOES_PADRAO = {
    'identificacao_pallets': False, 'relacao_carga': False, 'romaneio': False,
    'programacao_carregamento': False, 'carregamento_criar': False,
    'carregamento_editar': False, 'carregamento_excluir': False,
}


def _permissoes_usuario(row):
    try:
        permissoes = json.loads(row['permissoes_json'] or '{}')
    except (TypeError, ValueError):
        permissoes = {}
    return {**PERMISSOES_PADRAO, **permissoes}


def _registrar_auditoria(acao, detalhes='', status_http=None, usuario=None, usuario_id=None):
    nome = usuario or session.get('usuario_login') or 'Anônimo'
    uid = usuario_id if usuario_id is not None else session.get('usuario_id')
    try:
        with get_connection() as conn:
            conn.execute('''INSERT INTO auditoria
                (usuario_id, usuario, acao, metodo, caminho, detalhes, status_http)
                VALUES (?, ?, ?, ?, ?, ?, ?)''', (
                    uid, nome, acao, request.method, request.path,
                    str(detalhes or '')[:2000], status_http
                ))
    except Exception:
        app.logger.exception('Falha ao registrar auditoria')


def _permissao_da_requisicao():
    path, metodo = request.path, request.method
    if path.startswith('/api/admin/'):
        return 'administrador'
    if path.startswith('/api/carregamentos'):
        if metodo == 'POST': return 'carregamento_criar'
        if metodo == 'PUT': return 'carregamento_editar'
        if metodo == 'DELETE': return 'carregamento_excluir'
        return 'programacao_carregamento'
    if path.startswith('/api/romaneios'):
        return 'romaneio'
    if path.startswith('/api/cargas'):
        return 'relacao_carga' if metodo != 'GET' else 'relacao_ou_romaneio'
    if path.startswith('/api/estoque-pallets') or path.startswith('/api/produtos/por-codigo'):
        return 'relacao_carga'
    if path.startswith('/api/') and path not in ('/api/auth/login', '/api/auth/me', '/api/auth/logout', '/api/auth/atividade', '/api/status'):
        return 'identificacao_pallets'
    return None


@app.before_request
def autenticar_requisicao():
    if not request.path.startswith('/api/') or request.path == '/api/auth/login':
        return None
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return jsonify({'erro': 'Faça login para continuar.', 'loginNecessario': True}), 401
    with get_connection() as conn:
        usuario = conn.execute('SELECT * FROM usuarios WHERE id=? AND ativo=1', (usuario_id,)).fetchone()
    if not usuario:
        session.clear()
        return jsonify({'erro': 'Sua sessão não é mais válida.', 'loginNecessario': True}), 401
    g.usuario = usuario
    g.permissoes = _permissoes_usuario(usuario)
    permissao = _permissao_da_requisicao()
    autorizado = (
        not permissao or bool(usuario['administrador']) or
        (permissao == 'relacao_ou_romaneio' and (g.permissoes['relacao_carga'] or g.permissoes['romaneio'])) or
        (permissao in ('carregamento_criar', 'carregamento_editar', 'carregamento_excluir')
         and g.permissoes['programacao_carregamento'] and bool(g.permissoes.get(permissao))) or
        (permissao not in ('carregamento_criar', 'carregamento_editar', 'carregamento_excluir', 'relacao_ou_romaneio')
         and bool(g.permissoes.get(permissao)))
    )
    if not autorizado:
        return jsonify({'erro': 'Você não tem permissão para realizar esta ação.'}), 403
    return None


@app.after_request
def auditar_alteracoes(response):
    if (request.path.startswith('/api/') and request.method in ('POST', 'PUT', 'DELETE')
            and request.path not in ('/api/auth/login', '/api/auth/logout', '/api/auth/atividade') and session.get('usuario_id')):
        dados = request.get_json(silent=True) if request.is_json else None
        if isinstance(dados, dict):
            dados = {k: ('***' if 'senha' in k.lower() else v) for k, v in dados.items()}
        _registrar_auditoria(request.endpoint or request.path, json.dumps(dados, ensure_ascii=False) if dados else '', response.status_code)
    return response


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    dados = request.get_json(silent=True) or {}
    login = str(dados.get('login') or '').strip()
    with get_connection() as conn:
        usuario = conn.execute('SELECT * FROM usuarios WHERE login=? COLLATE NOCASE AND ativo=1', (login,)).fetchone()
    if not usuario or not check_password_hash(usuario['senha_hash'], str(dados.get('senha') or '')):
        _registrar_auditoria('login_falhou', f'Login informado: {login}', 401, login or 'Anônimo')
        return jsonify({'erro': 'Usuário ou senha inválidos.'}), 401
    session.clear()
    session['usuario_id'] = usuario['id']
    session['usuario_login'] = usuario['login']
    _registrar_auditoria('login', 'Entrada no Portal Logística', 200)
    return jsonify({'ok': True})


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    _registrar_auditoria('logout', 'Saída do Portal Logística', 200)
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/auth/atividade', methods=['POST'])
def api_registrar_atividade():
    modulo = str((request.get_json(silent=True) or {}).get('modulo') or '').strip()
    _registrar_auditoria('acessou_modulo', modulo, 200)
    return jsonify({'ok': True})


@app.route('/api/auth/me', methods=['GET'])
def api_usuario_atual():
    return jsonify({
        'id': g.usuario['id'], 'login': g.usuario['login'], 'nome': g.usuario['nome'],
        'administrador': bool(g.usuario['administrador']), 'permissoes': g.permissoes,
    })


@app.route('/api/admin/usuarios', methods=['GET', 'POST'])
def api_admin_usuarios():
    if request.method == 'GET':
        with get_connection() as conn:
            rows = conn.execute('''SELECT id, login, nome, administrador, ativo,
                permissoes_json, criado_em, atualizado_em FROM usuarios ORDER BY nome, login''').fetchall()
        return jsonify([{
            **{k: row[k] for k in ('id', 'login', 'nome', 'criado_em', 'atualizado_em')},
            'administrador': bool(row['administrador']), 'ativo': bool(row['ativo']),
            'permissoes': _permissoes_usuario(row),
        } for row in rows])

    dados = request.get_json(silent=True) or {}
    login, nome, senha = (str(dados.get(k) or '').strip() for k in ('login', 'nome', 'senha'))
    if not login or not nome or not senha:
        return jsonify({'erro': 'Informe login, nome e senha.'}), 400
    permissoes = {k: bool((dados.get('permissoes') or {}).get(k)) for k in PERMISSOES_PADRAO}
    try:
        with get_connection() as conn:
            cursor = conn.execute('''INSERT INTO usuarios
                (login, nome, senha_hash, administrador, ativo, permissoes_json)
                VALUES (?, ?, ?, ?, ?, ?)''', (
                    login, nome, generate_password_hash(senha), bool(dados.get('administrador')),
                    bool(dados.get('ativo', True)), json.dumps(permissoes, ensure_ascii=False)
                ))
        return jsonify({'ok': True, 'id': cursor.lastrowid}), 201
    except Exception as err:
        if 'UNIQUE' in str(err).upper():
            return jsonify({'erro': 'Já existe um usuário com esse login.'}), 409
        raise


@app.route('/api/admin/usuarios/<int:usuario_id>', methods=['PUT'])
def api_admin_usuario_editar(usuario_id):
    dados = request.get_json(silent=True) or {}
    login, nome = str(dados.get('login') or '').strip(), str(dados.get('nome') or '').strip()
    if not login or not nome:
        return jsonify({'erro': 'Informe login e nome.'}), 400
    with get_connection() as conn:
        atual = conn.execute('SELECT * FROM usuarios WHERE id=?', (usuario_id,)).fetchone()
        if not atual:
            return jsonify({'erro': 'Usuário não encontrado.'}), 404
        administrador, ativo = bool(dados.get('administrador')), bool(dados.get('ativo'))
        if atual['login'].lower() == 'admin' and (not administrador or not ativo):
            return jsonify({'erro': 'O administrador principal não pode ser desativado nem perder o perfil administrativo.'}), 400
        permissoes = {k: bool((dados.get('permissoes') or {}).get(k)) for k in PERMISSOES_PADRAO}
        parametros = [login, nome, administrador, ativo, json.dumps(permissoes, ensure_ascii=False)]
        senha = str(dados.get('senha') or '')
        sql = '''UPDATE usuarios SET login=?, nome=?, administrador=?, ativo=?,
            permissoes_json=?, atualizado_em=CURRENT_TIMESTAMP'''
        if senha:
            sql += ', senha_hash=?'
            parametros.append(generate_password_hash(senha))
        sql += ' WHERE id=?'
        parametros.append(usuario_id)
        try:
            conn.execute(sql, parametros)
        except Exception as err:
            if 'UNIQUE' in str(err).upper():
                return jsonify({'erro': 'Já existe um usuário com esse login.'}), 409
            raise
    if usuario_id == session.get('usuario_id'):
        session['usuario_login'] = login
    return jsonify({'ok': True})


@app.route('/api/admin/auditoria', methods=['GET'])
def api_admin_auditoria():
    usuario = request.args.get('usuario', '').strip()
    limite = min(max(int(request.args.get('limite', 300)), 1), 1000)
    params, where = [], ''
    if usuario:
        where = ' WHERE usuario LIKE ?'
        params.append(f'%{usuario}%')
    params.append(limite)
    with get_connection() as conn:
        rows = conn.execute(f'''SELECT id, usuario, data_hora, acao, metodo, caminho,
            detalhes, status_http FROM auditoria{where} ORDER BY id DESC LIMIT ?''', params).fetchall()
    return jsonify([dict(row) for row in rows])


@app.errorhandler(413)
def upload_grande(err):
    return jsonify({'erro': 'O envio deve ter no máximo 50 MB.'}), 413


@app.route('/api/romaneios/<int:romaneio_id>/fotos', methods=['GET', 'POST'])
def api_romaneio_fotos(romaneio_id):
    with get_connection() as conn:
        if not conn.execute('SELECT id FROM romaneios WHERE id=?', (romaneio_id,)).fetchone():
            return jsonify({'erro': 'Romaneio não encontrado.'}), 404
        if request.method == 'POST':
            try:
                fotos = ler_uploads(request)
                if not fotos:
                    raise ValueError('Selecione ao menos uma foto.')
                salvar_fotos(conn, romaneio_id, fotos)
            except ValueError as err:
                return jsonify({'erro': str(err)}), 400
        return jsonify([dict(r) for r in conn.execute(
            'SELECT id, categoria FROM romaneio_fotos WHERE romaneio_id=? ORDER BY id', (romaneio_id,))])


@app.route('/api/romaneios/<int:romaneio_id>/fotos/<int:foto_id>', methods=['GET', 'DELETE'])
def api_romaneio_foto(romaneio_id, foto_id):
    with get_connection() as conn:
        row = conn.execute('SELECT imagem FROM romaneio_fotos WHERE id=? AND romaneio_id=?',
                           (foto_id, romaneio_id)).fetchone()
        if not row:
            return jsonify({'erro': 'Foto não encontrada.'}), 404
        if request.method == 'DELETE':
            conn.execute('DELETE FROM romaneio_fotos WHERE id=?', (foto_id,))
            return jsonify({'ok': True})
        return send_file(BytesIO(row['imagem']), mimetype='image/jpeg')

TARA_PMC_PKT = 6.2   # kg por carretel, quando o fio e' capa (PMC/PKT) - mesma regra da planilha
TARA_NU = 19.3       # kg por carretel, quando o fio e' nu


# ---------- Estaticos (front-end) ----------
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def static_files(path):
    caminho_completo = os.path.join(app.static_folder, path)
    if os.path.exists(caminho_completo):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')


# ---------- Status / atualizacao do ERP ----------
@app.route('/api/status', methods=['GET'])
def api_status():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT valor FROM meta WHERE chave = 'ultima_atualizacao';")
        row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS n FROM cache_ordens;")
        n_ordens = cur.fetchone()['n']
        cur.execute("SELECT COUNT(*) AS n FROM pallets;")
        n_pallets = cur.fetchone()['n']
        hoje = datetime.now().strftime('%Y-%m-%d')
        cur.execute("SELECT COUNT(*) AS n FROM programacao_carregamentos WHERE data_carregamento = ?;", (hoje,))
        n_carregamentos_hoje = cur.fetchone()['n']
        return jsonify({
            'ultimaAtualizacao': row['valor'] if row else None,
            'ordensEmCache': n_ordens,
            'paletesGravados': n_pallets,
            'carregamentosHoje': n_carregamentos_hoje,
        })
    finally:
        conn.close()


# ---------- Programação de carregamentos ----------
def validar_carregamento(data):
    campos = {
        'data_carregamento': 'data', 'horario': 'horário', 'caminhao': 'caminhão',
        'material': 'material', 'cliente': 'cliente'
    }
    for campo, rotulo in campos.items():
        if not str(data.get(campo) or '').strip():
            return f'Informe {rotulo}.'
    return None


@app.route('/api/carregamentos', methods=['GET'])
def api_carregamentos_list():
    inicio = request.args.get('inicio', '').strip()
    fim = request.args.get('fim', '').strip()
    query = 'SELECT * FROM programacao_carregamentos'
    filtros, params = [], []
    if inicio:
        filtros.append('data_carregamento >= ?')
        params.append(inicio)
    if fim:
        filtros.append('data_carregamento <= ?')
        params.append(fim)
    if filtros:
        query += ' WHERE ' + ' AND '.join(filtros)
    query += ' ORDER BY data_carregamento, horario, id'
    with get_connection() as conn:
        return jsonify([dict(row) for row in conn.execute(query, params).fetchall()])


@app.route('/api/carregamentos', methods=['POST'])
def api_carregamentos_create():
    data = request.get_json() or {}
    erro = validar_carregamento(data)
    if erro:
        return jsonify({'ok': False, 'erro': erro}), 400
    with get_connection() as conn:
        cursor = conn.execute('''INSERT INTO programacao_carregamentos
            (data_carregamento, horario, caminhao, material, cliente, observacao)
            VALUES (?, ?, ?, ?, ?, ?)''', (
                data['data_carregamento'].strip(), data['horario'].strip(), data['caminhao'].strip(),
                data['material'].strip(), data['cliente'].strip(), (data.get('observacao') or '').strip()
            ))
        return jsonify({'ok': True, 'id': cursor.lastrowid}), 201


@app.route('/api/carregamentos/<int:carregamento_id>', methods=['PUT'])
def api_carregamentos_update(carregamento_id):
    data = request.get_json() or {}
    erro = validar_carregamento(data)
    if erro:
        return jsonify({'ok': False, 'erro': erro}), 400
    with get_connection() as conn:
        cursor = conn.execute('''UPDATE programacao_carregamentos SET
            data_carregamento=?, horario=?, caminhao=?, material=?, cliente=?, observacao=? WHERE id=?''', (
                data['data_carregamento'].strip(), data['horario'].strip(), data['caminhao'].strip(),
                data['material'].strip(), data['cliente'].strip(), (data.get('observacao') or '').strip(),
                carregamento_id
            ))
        if not cursor.rowcount:
            return jsonify({'ok': False, 'erro': 'Carregamento não encontrado.'}), 404
        return jsonify({'ok': True})


@app.route('/api/carregamentos/<int:carregamento_id>', methods=['DELETE'])
def api_carregamentos_delete(carregamento_id):
    with get_connection() as conn:
        cursor = conn.execute('DELETE FROM programacao_carregamentos WHERE id = ?', (carregamento_id,))
        if not cursor.rowcount:
            return jsonify({'ok': False, 'erro': 'Carregamento não encontrado.'}), 404
        return jsonify({'ok': True})


@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    try:
        resultado = refresh_tudo()
        return jsonify(resultado)
    except Exception as err:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'erro': str(err)}), 500


# ---------- Lookup de OP (equivalente ao XLOOKUP na aba Funil) ----------
def _buscar_ordem(conn, op: str, modulo: str):
    op = (op or '').strip()
    if not op:
        return None
    cur = conn.cursor()
    # tenta igual, depois com zero a esquerda (mesma logica de "0"&OP da planilha)
    for candidato in (op, '0' + op):
        cur.execute(
            "SELECT * FROM cache_ordens WHERE modulo = ? AND op = ?;",
            (modulo, candidato)
        )
        row = cur.fetchone()
        if row:
            return dict(row)
    return None


def _classificar_tipo(descricao: str, isolacao: str) -> str:
    desc = (descricao or '').upper()
    if 'NU' in desc:
        return 'NU'
    if isolacao:
        return isolacao
    if 'CP' in desc:
        return 'PKT'
    return ''


@app.route('/api/lookup', methods=['GET'])
def api_lookup():
    op = request.args.get('op', '')
    modulo = request.args.get('modulo', 'fios')
    conn = get_connection()
    try:
        ordem = _buscar_ordem(conn, op, modulo)
        if not ordem:
            return jsonify({'encontrado': False, 'erro': 'OP não encontrada no cache. Atualize os dados do ERP ou confira o número.'}), 404

        cliente = None
        if ordem.get('codigo_cliente'):
            cur = conn.cursor()
            cur.execute("SELECT * FROM cache_clientes WHERE codigo = ?;", (ordem['codigo_cliente'],))
            row = cur.fetchone()
            if row:
                cliente = dict(row)

        tipo = _classificar_tipo(ordem.get('descricao'), ordem.get('isolacao')) if modulo == 'fios' else ''

        return jsonify({
            'encontrado': True,
            'op': ordem['op'],
            'oc': ordem.get('oc'),
            'pedido': ordem.get('pedido'),
            'codigoProduto': ordem.get('codigo_produto'),
            'descricao': ordem.get('descricao'),
            'ncm': '8544.19.10' if ordem.get('codigo_produto') else '',
            'tipo': tipo,
            'codigoCliente': ordem.get('codigo_cliente'),
            'clienteNome': cliente.get('nome') if cliente else None,
        })
    finally:
        conn.close()


# ---------- Linhas do cache do ERP (consulta e ajuste local) ----------
@app.route('/api/cache-ordens', methods=['GET'])
def api_cache_ordens_list():
    modulo = request.args.get('modulo', '').strip()
    busca = request.args.get('busca', '').strip()
    if modulo not in ('', 'fios', 'painel'):
        return jsonify({'erro': 'Módulo inválido.'}), 400

    filtros = []
    params = []
    if modulo:
        filtros.append('modulo = ?')
        params.append(modulo)
    if busca:
        termo = f'%{busca}%'
        filtros.append(
            '(op LIKE ? OR oc LIKE ? OR pedido LIKE ? OR codigo_produto LIKE ? '
            'OR descricao LIKE ? OR codigo_cliente LIKE ? OR isolacao LIKE ?)'
        )
        params.extend([termo] * 7)

    where = f" WHERE {' AND '.join(filtros)}" if filtros else ''
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f'SELECT COUNT(*) AS n FROM cache_ordens{where};', params)
        total = cur.fetchone()['n']
        cur.execute(
            f'SELECT * FROM cache_ordens{where} ORDER BY op DESC, modulo LIMIT 1000;',
            params,
        )
        return jsonify({'total': total, 'limite': 1000, 'linhas': [dict(r) for r in cur.fetchall()]})
    finally:
        conn.close()


@app.route('/api/cache-ordens/<modulo>/<path:op_original>', methods=['PUT'])
def api_cache_ordens_editar(modulo, op_original):
    if modulo not in ('fios', 'painel'):
        return jsonify({'ok': False, 'erro': 'Módulo inválido.'}), 400
    d = request.get_json() or {}
    op_nova = str(d.get('op') or '').strip()
    if not op_nova:
        return jsonify({'ok': False, 'erro': 'OP é obrigatória.'}), 400

    campos = {
        'oc': str(d.get('oc') or '').strip(),
        'pedido': str(d.get('pedido') or '').strip(),
        'codigo_produto': str(d.get('codigo_produto') or '').strip(),
        'descricao': str(d.get('descricao') or '').strip(),
        'codigo_cliente': str(d.get('codigo_cliente') or '').strip(),
        'isolacao': str(d.get('isolacao') or '').strip().upper(),
    }
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'UPDATE cache_ordens SET op = ?, oc = ?, pedido = ?, codigo_produto = ?, '
            'descricao = ?, codigo_cliente = ?, isolacao = ? WHERE modulo = ? AND op = ?;',
            (op_nova, campos['oc'], campos['pedido'], campos['codigo_produto'],
             campos['descricao'], campos['codigo_cliente'], campos['isolacao'],
             modulo, op_original),
        )
        if cur.rowcount == 0:
            return jsonify({'ok': False, 'erro': 'Linha não encontrada no cache.'}), 404
        conn.commit()
        return jsonify({'ok': True, 'op': op_nova})
    except Exception as err:
        if 'UNIQUE constraint failed' in str(err):
            return jsonify({'ok': False, 'erro': 'Já existe uma linha com essa OP no módulo.'}), 409
        raise
    finally:
        conn.close()


# ---------- Paletes (tara) ----------
@app.route('/api/paletes', methods=['GET'])
def api_paletes_list():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM paletes ORDER BY medida;")
        return jsonify([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()


@app.route('/api/paletes', methods=['POST'])
def api_paletes_upsert():
    d = request.get_json() or {}
    medida = (d.get('medida') or '').strip()
    if not medida:
        return jsonify({'ok': False, 'erro': 'Medida é obrigatória.'}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO paletes (medida, peso_tara) VALUES (?, ?) "
            "ON CONFLICT(medida) DO UPDATE SET peso_tara = excluded.peso_tara;",
            (medida, float(d.get('pesoTara') or 0))
        )
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ---------- Abreviacao de clientes ----------
@app.route('/api/clientes/abrev', methods=['GET'])
def api_clientes_abrev_list():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM clientes_abrev ORDER BY codigo;")
        return jsonify([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()


@app.route('/api/clientes/abrev', methods=['POST'])
def api_clientes_abrev_upsert():
    d = request.get_json() or {}
    codigo = str(d.get('codigo') or '').strip()
    abrev = (d.get('abreviacao') or '').strip()
    if not codigo or not abrev:
        return jsonify({'ok': False, 'erro': 'Código e abreviação são obrigatórios.'}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO clientes_abrev (codigo, abreviacao) VALUES (?, ?) "
            "ON CONFLICT(codigo) DO UPDATE SET abreviacao = excluded.abreviacao;",
            (codigo, abrev)
        )
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ---------- Proximo numero (preview, nao reserva) ----------
def _ultimo_numero_pallet(conn):
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(numero), 0) AS ultimo FROM pallets;")
    ultimo_banco = cur.fetchone()['ultimo'] or 0
    cur.execute("SELECT valor FROM meta WHERE chave = 'ultimo_numero_pallet';")
    row = cur.fetchone()
    try:
        ultimo_meta = int(row['valor']) if row else 0
    except (TypeError, ValueError):
        ultimo_meta = 0

    # Recupera a sequência mesmo se o histórico tiver sido apagado, usando os
    # PDFs existentes como última referência conhecida.
    ultimo_pdf = 0
    try:
        import re
        from paths import pdf_dir
        padrao = re.compile(r'-(\d+)-\d{4}-\d{2}-\d{2}-(?:fios|painel)(?:-[a-f0-9]+)?\.pdf$', re.I)
        for nome in os.listdir(pdf_dir()):
            match = padrao.search(nome)
            if match:
                ultimo_pdf = max(ultimo_pdf, int(match.group(1)))
    except OSError:
        pass
    return max(ultimo_banco, ultimo_meta, ultimo_pdf)


@app.route('/api/proximo_numero', methods=['GET'])
def api_proximo_numero():
    conn = get_connection()
    try:
        return jsonify({'proximoNumero': _ultimo_numero_pallet(conn) + 1})
    finally:
        conn.close()


# ---------- Gravar palete (equivalente a GRAVAR_BASE / GRAVAR_PRINT_BASE) ----------
@app.route('/api/pallets', methods=['POST'])
def api_pallets_gravar():
    d = request.get_json() or {}
    modulo = d.get('modulo') or 'fios'
    medida_palete = (d.get('medidaPalete') or '').strip()
    itens_entrada = [i for i in (d.get('itens') or []) if (i.get('op') or '').strip() or (i.get('qtde') not in (None, ''))]

    erros = []
    if modulo not in ('fios', 'painel'):
        erros.append("Módulo inválido.")
    if not medida_palete:
        erros.append("Medida do palete não informada.")
    if not itens_entrada:
        erros.append("Nenhuma linha preenchida (OP/Qtde).")

    conn = get_connection()
    try:
        itens_resolvidos = []
        codigos_cliente = set()

        for i in itens_entrada:
            op = (i.get('op') or '').strip()
            qtde_raw = i.get('qtde')
            if not op:
                erros.append("Existe uma linha com Qtde preenchida e OP em branco.")
                continue
            try:
                qtde = float(qtde_raw)
            except (TypeError, ValueError):
                erros.append(f"OP {op}: quantidade inválida.")
                continue

            ordem = _buscar_ordem(conn, op, modulo)
            if not ordem:
                erros.append(f"OP {op} não encontrada no cache do ERP.")
                continue

            if ordem.get('codigo_cliente'):
                codigos_cliente.add(ordem['codigo_cliente'])

            tipo = _classificar_tipo(ordem.get('descricao'), ordem.get('isolacao')) if modulo == 'fios' else ''
            if modulo == 'fios':
                tara = TARA_PMC_PKT if tipo in ('PMC', 'PKT') else (TARA_NU if tipo == 'NU' else 0)
            else:
                tara = 0  # ajuste aqui a regra de peso de embalagem por item para paineis/kits, se houver

            itens_resolvidos.append({
                'op': op,
                'oc': ordem.get('oc'),
                'pedido': ordem.get('pedido'),
                'codigo_produto': ordem.get('codigo_produto'),
                'descricao': ordem.get('descricao'),
                'ncm': '8544.19.10' if modulo == 'fios' and ordem.get('codigo_produto') else '',
                'tipo': tipo,
                'qtde': qtde,
                'peso_bruto_linha': qtde + tara,
            })

        if len(codigos_cliente) > 1:
            erros.append(
                "As OPs informadas pertencem a clientes diferentes "
                f"({', '.join(sorted(codigos_cliente))}). Um palete só pode ter um cliente."
            )

        if erros:
            return jsonify({'ok': False, 'erros': erros}), 400

        cur = conn.cursor()
        cur.execute("SELECT peso_tara FROM paletes WHERE medida = ?;", (medida_palete,))
        row = cur.fetchone()
        peso_embalagem = row['peso_tara'] if row else 0

        codigo_cliente = next(iter(codigos_cliente), None)
        cliente_nome = None
        cliente_abrev = None
        cliente_endereco = None
        cliente_bairro = None
        cliente_cidade = None
        cliente_uf = None
        if codigo_cliente:
            cur.execute("SELECT * FROM cache_clientes WHERE codigo = ?;", (codigo_cliente,))
            row = cur.fetchone()
            if row:
                cliente_nome = row['nome']
                cliente_endereco = row['endereco']
                cliente_bairro = row['bairro']
                cliente_cidade = row['cidade']
                cliente_uf = row['uf']
            cur.execute("SELECT abreviacao FROM clientes_abrev WHERE codigo = ?;", (codigo_cliente,))
            row = cur.fetchone()
            cliente_abrev = row['abreviacao'] if row else (cliente_nome or codigo_cliente)

        peso_liquido = round(sum(i['qtde'] for i in itens_resolvidos), 2)
        peso_bruto = round(sum(i['peso_bruto_linha'] for i in itens_resolvidos) + peso_embalagem, 2)
        carreteis = len(itens_resolvidos)

        numero = _ultimo_numero_pallet(conn) + 1
        data_hora = datetime.now().isoformat()

        registro = {
            'numero': numero,
            'modulo': modulo,
            'data_hora': data_hora,
            'cliente_codigo': codigo_cliente,
            'cliente_nome': cliente_nome,
            'cliente_abrev': cliente_abrev,
            'cliente_endereco': cliente_endereco,
            'cliente_bairro': cliente_bairro,
            'cliente_cidade': cliente_cidade,
            'cliente_uf': cliente_uf,
            'medida_palete': medida_palete,
            'peso_liquido': peso_liquido,
            'peso_bruto': peso_bruto,
            'carreteis': carreteis,
            'itens': itens_resolvidos,
        }

        caminho_pdf = gerar_pdf_etiqueta(registro)
        nome_pdf = os.path.basename(caminho_pdf)

        cur.execute(
            "INSERT INTO pallets (numero, modulo, data_hora, cliente_codigo, cliente_nome, cliente_abrev, "
            "medida_palete, peso_liquido, peso_bruto, carreteis, itens_json, arquivo_pdf) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (numero, modulo, data_hora, codigo_cliente, cliente_nome, cliente_abrev, medida_palete,
             peso_liquido, peso_bruto, carreteis, json.dumps(itens_resolvidos, ensure_ascii=False), nome_pdf)
        )
        cur.execute("INSERT OR REPLACE INTO meta (chave, valor) VALUES ('ultimo_numero_pallet', ?);", (str(numero),))
        conn.commit()
        novo_id = cur.lastrowid

        return jsonify({'ok': True, 'id': novo_id, 'numero': numero, 'arquivoPdf': nome_pdf,
                         'pesoLiquido': peso_liquido, 'pesoBruto': peso_bruto, 'carreteis': carreteis})
    finally:
        conn.close()


# ---------- Historico (aba "Base") ----------
@app.route('/api/pallets', methods=['GET'])
def api_pallets_list():
    modulo = request.args.get('modulo', '')
    busca = request.args.get('busca', '').strip().upper()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM pallets ORDER BY numero DESC;")
        linhas = [dict(r) for r in cur.fetchall()]
        if modulo:
            linhas = [l for l in linhas if l['modulo'] == modulo]
        if busca:
            def bate(l):
                alvo = f"{l['numero']} {l.get('cliente_nome') or ''} {l.get('itens_json') or ''}".upper()
                return busca in alvo
            linhas = [l for l in linhas if bate(l)]
        return jsonify(linhas)
    finally:
        conn.close()


@app.route('/api/pallets/<int:pallet_id>/pdf', methods=['GET'])
def api_pallets_pdf(pallet_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT arquivo_pdf FROM pallets WHERE id = ?;", (pallet_id,))
        row = cur.fetchone()
        if not row or not row['arquivo_pdf']:
            return jsonify({'erro': 'PDF não encontrado.'}), 404
        from paths import pdf_dir
        return send_file(os.path.join(pdf_dir(), row['arquivo_pdf']), as_attachment=False)
    finally:
        conn.close()


@app.route('/api/pallets/<int:pallet_id>', methods=['DELETE'])
def api_pallets_excluir(pallet_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT numero, status, romaneio_id, arquivo_pdf FROM pallets WHERE id = ?;", (pallet_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'ok': False, 'erro': 'Packing list não encontrado.'}), 404
        if row['status'] == 'expedido' or row['romaneio_id']:
            return jsonify({
                'ok': False,
                'erro': 'Este packing list já foi expedido e não pode ser excluído, pois pertence a um romaneio.'
            }), 409

        # Remove primeiro os vínculos de planejamentos de carga ainda abertos.
        cur.execute("DELETE FROM carga_pallets WHERE pallet_id = ?;", (pallet_id,))
        cur.execute("DELETE FROM pallets WHERE id = ?;", (pallet_id,))
        conn.commit()

        arquivo = os.path.basename(row['arquivo_pdf'] or '')
        if arquivo:
            from paths import pdf_dir
            caminho_pdf = os.path.join(pdf_dir(), arquivo)
            if os.path.isfile(caminho_pdf):
                os.remove(caminho_pdf)
        return jsonify({'ok': True, 'numero': row['numero']})
    finally:
        conn.close()


def _pallet_com_itens(row):
    pallet = dict(row)
    try:
        pallet['itens'] = json.loads(pallet.get('itens_json') or '[]')
    except (TypeError, json.JSONDecodeError):
        pallet['itens'] = []
    for item in pallet['itens']:
        if not item.get('ncm') and pallet.get('modulo') == 'fios' and item.get('codigo_produto'):
            item['ncm'] = '8544.19.10'
    return pallet


# ---------- Estoque de produto acabado / relação de carga ----------
@app.route('/api/produtos/por-codigo', methods=['GET'])
def api_produto_por_codigo():
    codigo = request.args.get('codigo', '').strip()
    if not codigo:
        return jsonify({'erro': 'Informe o código do produto.'}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT codigo_produto, descricao FROM cache_ordens
                       WHERE UPPER(TRIM(codigo_produto)) = UPPER(?) AND TRIM(COALESCE(descricao, '')) <> ''
                       ORDER BY rowid DESC LIMIT 1;""", (codigo,))
        row = cur.fetchone()
        if not row:
            return jsonify({'erro': 'Código não encontrado nos dados do ERP.'}), 404
        return jsonify(dict(row))
    finally:
        conn.close()


@app.route('/api/estoque-pallets', methods=['GET'])
def api_estoque_pallets():
    busca = request.args.get('busca', '').strip().upper()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM pallets WHERE status = 'armazenado' ORDER BY numero DESC;")
        linhas = [_pallet_com_itens(r) for r in cur.fetchall()]
        if busca:
            linhas = [p for p in linhas if busca in (
                f"{p['numero']} {p.get('cliente_nome') or ''} {p.get('itens_json') or ''}"
            ).upper()]
        return jsonify(linhas)
    finally:
        conn.close()


@app.route('/api/cargas', methods=['POST'])
def api_cargas_criar():
    d = request.get_json() or {}
    ids = list(dict.fromkeys(int(i) for i in (d.get('palletIds') or []) if str(i).isdigit()))
    itens_manuais = []
    for item in d.get('itensManuais') or []:
        codigo = str(item.get('codigo') or '').strip()
        descricao = str(item.get('descricao') or '').strip()
        try:
            quantidade = float(str(item.get('quantidade') or '').replace(',', '.'))
        except ValueError:
            return jsonify({'ok': False, 'erro': f'Quantidade inválida no item {codigo or descricao or "manual"}.'}), 400
        if not codigo:
            return jsonify({'ok': False, 'erro': 'Informe o código de todos os itens manuais.'}), 400
        if quantidade <= 0:
            return jsonify({'ok': False, 'erro': f'A quantidade do código {codigo} deve ser maior que zero.'}), 400
        itens_manuais.append((codigo, descricao, quantidade, str(item.get('observacao') or '').strip()))
    if not ids and not itens_manuais:
        return jsonify({'ok': False, 'erro': 'Selecione um pallet ou adicione pelo menos um item manual.'}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        marcadores = ','.join('?' for _ in ids)
        cur.execute(f"SELECT id FROM pallets WHERE id IN ({marcadores}) AND status = 'armazenado';", ids)
        disponiveis = {r['id'] for r in cur.fetchall()}
        if disponiveis != set(ids):
            return jsonify({'ok': False, 'erro': 'Um ou mais pallets não estão disponíveis no estoque.'}), 409
        cur.execute("SELECT COALESCE(MAX(numero), 0) + 1 AS proximo FROM cargas;")
        numero = cur.fetchone()['proximo']
        cur.execute(
            "INSERT INTO cargas (numero, data_hora, cliente, transportadora, veiculo, motorista, prioridade, observacao) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            (numero, datetime.now().isoformat(), str(d.get('cliente') or '').strip(),
             str(d.get('transportadora') or '').strip(), str(d.get('veiculo') or '').strip(),
             str(d.get('motorista') or '').strip(), str(d.get('prioridade') or '').strip(),
             str(d.get('observacao') or '').strip()),
        )
        carga_id = cur.lastrowid
        cur.executemany("INSERT INTO carga_pallets (carga_id, pallet_id) VALUES (?, ?);",
                        [(carga_id, pallet_id) for pallet_id in ids])
        cur.executemany("INSERT INTO carga_itens (carga_id, codigo_produto, descricao, quantidade, observacao) VALUES (?, ?, ?, ?, ?);",
                        [(carga_id, *item) for item in itens_manuais])
        conn.commit()
        return jsonify({'ok': True, 'id': carga_id, 'numero': numero, 'quantidadePallets': len(ids),
                        'quantidadeItensManuais': len(itens_manuais)})
    finally:
        conn.close()


@app.route('/api/cargas', methods=['GET'])
def api_cargas_listar():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT c.*, COUNT(cp.pallet_id) AS quantidade_pallets,
                       COALESCE(SUM(p.peso_bruto), 0) AS peso_bruto
                       FROM cargas c
                       LEFT JOIN carga_pallets cp ON cp.carga_id = c.id
                       LEFT JOIN pallets p ON p.id = cp.pallet_id
                       GROUP BY c.id ORDER BY c.numero DESC;""")
        return jsonify([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()


@app.route('/api/cargas/<int:carga_id>/pdf', methods=['GET'])
def api_carga_pdf(carga_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cargas WHERE id = ?;", (carga_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'erro': 'Relação de carga não encontrada.'}), 404
        carga = dict(row)
        cur.execute("""SELECT p.* FROM pallets p JOIN carga_pallets cp ON cp.pallet_id = p.id
                       WHERE cp.carga_id = ? ORDER BY p.numero;""", (carga_id,))
        pallets = [_pallet_com_itens(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM carga_itens WHERE carga_id = ? ORDER BY id;", (carga_id,))
        itens_manuais = [dict(r) for r in cur.fetchall()]
        caminho = gerar_pdf_relacao_carga(carga, pallets, itens_manuais)
        return send_file(caminho, as_attachment=False)
    finally:
        conn.close()


@app.route('/api/cargas/<int:carga_id>', methods=['DELETE'])
def api_carga_excluir(carga_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT numero FROM cargas WHERE id=?;", (carga_id,))
        carga = cur.fetchone()
        if not carga:
            return jsonify({'ok': False, 'erro': 'Relação de carga não encontrada.'}), 404
        cur.execute("SELECT COUNT(*) AS n FROM romaneios WHERE carga_id=?;", (carga_id,))
        if cur.fetchone()['n']:
            return jsonify({'ok': False, 'erro': 'Esta relação possui um Romaneio vinculado. Exclua primeiro o Romaneio.'}), 409
        cur.execute("DELETE FROM carga_itens WHERE carga_id=?;", (carga_id,))
        cur.execute("DELETE FROM carga_pallets WHERE carga_id=?;", (carga_id,))
        cur.execute("DELETE FROM cargas WHERE id=?;", (carga_id,))
        conn.commit()
        return jsonify({'ok': True, 'numero': carga['numero']})
    except Exception as err:
        conn.rollback()
        return jsonify({'ok': False, 'erro': f'Não foi possível excluir a relação: {err}'}), 500
    finally:
        conn.close()


# ---------- Romaneio e baixa do estoque ----------
def _numeros_pallets_entrada(valores):
    numeros = []
    for valor in valores or []:
        try:
            numero = int(str(valor).strip())
            if numero not in numeros:
                numeros.append(numero)
        except (TypeError, ValueError):
            pass
    return numeros


def _validar_pallets_romaneio(conn, numeros):
    if not numeros:
        return None, ('Informe ao menos um número de packing list.', 400)
    marcadores = ','.join('?' for _ in numeros)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM pallets WHERE numero IN ({marcadores});", numeros)
    encontrados_lista = [_pallet_com_itens(r) for r in cur.fetchall()]
    encontrados = {p['numero']: p for p in encontrados_lista}
    faltantes = [n for n in numeros if n not in encontrados]
    expedidos = [n for n in numeros if n in encontrados and encontrados[n].get('status') != 'armazenado']
    if faltantes:
        return None, ('Packing list não encontrado: ' + ', '.join(map(str, faltantes)), 404)
    if expedidos:
        return None, ('Pallet já expedido: ' + ', '.join(map(str, expedidos)), 409)
    pallets = [encontrados[n] for n in numeros]
    clientes = {str(p.get('cliente_codigo') or '').strip() for p in pallets if p.get('cliente_codigo')}
    if len(clientes) > 1:
        nomes = sorted({p.get('cliente_nome') or p.get('cliente_codigo') for p in pallets})
        return None, ('Os packing lists pertencem a clientes diferentes: ' + ', '.join(nomes), 409)
    return pallets, None


def _comparar_carga_romaneio(conn, carga_id, pallets):
    cur = conn.cursor()
    cur.execute("SELECT * FROM cargas WHERE id = ?;", (carga_id,))
    carga = cur.fetchone()
    if not carga:
        return None, None
    planejado = {}
    cur.execute("""SELECT p.* FROM pallets p JOIN carga_pallets cp ON cp.pallet_id=p.id
                   WHERE cp.carga_id=?;""", (carga_id,))
    for row in cur.fetchall():
        for item in _pallet_com_itens(row).get('itens') or []:
            codigo = str(item.get('codigo_produto') or 'SEM CÓDIGO').strip().upper()
            planejado[codigo] = planejado.get(codigo, 0) + float(item.get('qtde') or 0)
    cur.execute("SELECT codigo_produto, quantidade FROM carga_itens WHERE carga_id=?;", (carga_id,))
    for item in cur.fetchall():
        codigo = str(item['codigo_produto'] or 'SEM CÓDIGO').strip().upper()
        planejado[codigo] = planejado.get(codigo, 0) + float(item['quantidade'] or 0)
    realizado = {}
    for pallet in pallets:
        for item in pallet.get('itens') or []:
            codigo = str(item.get('codigo_produto') or 'SEM CÓDIGO').strip().upper()
            realizado[codigo] = realizado.get(codigo, 0) + float(item.get('qtde') or 0)
    codigos = set(planejado) | set(realizado)
    base = sum(max(planejado.get(c, 0), realizado.get(c, 0)) for c in codigos)
    coincidencia = sum(min(planejado.get(c, 0), realizado.get(c, 0)) for c in codigos)
    percentual = round((coincidencia / base * 100) if base else 100, 1)
    diferencas = [{'codigo': c, 'planejado': planejado.get(c, 0), 'realizado': realizado.get(c, 0)}
                 for c in sorted(codigos) if abs(planejado.get(c, 0) - realizado.get(c, 0)) > 0.0001]
    return {'percentual': percentual, 'diferencas': diferencas, 'numeroCarga': carga['numero']}, dict(carga)


@app.route('/api/romaneios/preview', methods=['POST'])
def api_romaneios_preview():
    d = request.get_json() or {}
    try:
        carga_id = int(d.get('cargaId'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'erro': 'Selecione uma relação de carga.'}), 400
    numeros = _numeros_pallets_entrada(d.get('numerosPallets'))
    conn = get_connection()
    try:
        pallets, erro = _validar_pallets_romaneio(conn, numeros)
        if erro:
            return jsonify({'ok': False, 'erro': erro[0]}), erro[1]
        comparacao, _ = _comparar_carga_romaneio(conn, carga_id, pallets)
        if not comparacao:
            return jsonify({'ok': False, 'erro': 'Relação de carga não encontrada.'}), 404
        return jsonify({
            'ok': True, 'pallets': pallets,
            'clienteCodigo': pallets[0].get('cliente_codigo') if pallets else '',
            'clienteNome': pallets[0].get('cliente_nome') if pallets else '',
            'pesoLiquido': round(sum(p.get('peso_liquido') or 0 for p in pallets), 2),
            'pesoBruto': round(sum(p.get('peso_bruto') or 0 for p in pallets), 2),
            'volumes': sum(p.get('carreteis') or 0 for p in pallets),
            'comparacaoCarga': comparacao,
        })
    finally:
        conn.close()


@app.route('/api/romaneios', methods=['POST'])
def api_romaneios_criar():
    try:
        d = json.loads(request.form.get('dados', '{}')) if request.mimetype == 'multipart/form-data' else request.get_json() or {}
        fotos = ler_uploads(request)
    except (ValueError, TypeError) as err:
        return jsonify({'erro': str(err)}), 400
    try:
        carga_id = int(d.get('cargaId'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'erro': 'Selecione uma relação de carga.'}), 400
    numeros = _numeros_pallets_entrada(d.get('numerosPallets'))
    frete = str(d.get('frete') or 'CIF').strip().upper()
    if frete not in ('CIF', 'FOB', 'SEM FRETE'):
        return jsonify({'ok': False, 'erro': 'Tipo de frete inválido.'}), 400
    data_envio = str(d.get('dataEnvio') or datetime.now().date().isoformat()).strip()
    try:
        datetime.strptime(data_envio, '%Y-%m-%d')
    except ValueError:
        return jsonify({'ok': False, 'erro': 'Data de envio inválida.'}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        pallets, erro = _validar_pallets_romaneio(conn, numeros)
        if erro:
            return jsonify({'ok': False, 'erro': erro[0]}), erro[1]
        comparacao, carga = _comparar_carga_romaneio(conn, carga_id, pallets)
        if not comparacao:
            return jsonify({'ok': False, 'erro': 'Relação de carga não encontrada.'}), 404

        cur.execute("SELECT COALESCE(MAX(numero), 0) + 1 AS proximo FROM romaneios;")
        numero_romaneio = cur.fetchone()['proximo']
        cliente_codigo = pallets[0].get('cliente_codigo') if pallets else ''
        cliente_nome = pallets[0].get('cliente_nome') if pallets else ''
        peso_liquido = round(sum(p.get('peso_liquido') or 0 for p in pallets), 2)
        peso_bruto = round(sum(p.get('peso_bruto') or 0 for p in pallets), 2)
        registro = {
            'numero': numero_romaneio, 'data_hora': datetime.now().isoformat(),
            'data_envio': data_envio, 'cliente_codigo': cliente_codigo, 'cliente_nome': cliente_nome,
            'frete': frete, 'peso_liquido': peso_liquido, 'peso_bruto': peso_bruto,
            'transportadora': str(d.get('transportadora') or '').strip(),
            'veiculo': str(d.get('veiculo') or '').strip(),
            'motorista': str(d.get('motorista') or '').strip(),
            'observacao': str(d.get('observacao') or '').strip(),
            'carga_numero': carga['numero'], 'aderencia_carga': comparacao['percentual'],
        }
        cur.execute(
            "INSERT INTO romaneios (numero, data_hora, data_envio, cliente_codigo, cliente_nome, frete, "
            "transportadora, veiculo, motorista, observacao, peso_liquido, peso_bruto, quantidade_pallets, carga_id, aderencia_carga) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (registro['numero'], registro['data_hora'], registro['data_envio'], cliente_codigo, cliente_nome,
             frete, registro['transportadora'], registro['veiculo'], registro['motorista'], registro['observacao'],
             peso_liquido, peso_bruto, len(pallets), carga_id, comparacao['percentual']),
        )
        romaneio_id = cur.lastrowid
        salvar_fotos(conn, romaneio_id, fotos)
        registro['fotos'] = fotos_pdf(conn, romaneio_id)
        caminho_pdf = gerar_pdf_romaneio(registro, pallets)
        nome_pdf = os.path.basename(caminho_pdf)
        ids = [p['id'] for p in pallets]
        cur.executemany("INSERT INTO romaneio_pallets (romaneio_id, pallet_id) VALUES (?, ?);",
                        [(romaneio_id, pallet_id) for pallet_id in ids])
        cur.executemany("UPDATE pallets SET status = 'expedido', romaneio_id = ? WHERE id = ?;",
                        [(romaneio_id, pallet_id) for pallet_id in ids])
        cur.execute("UPDATE romaneios SET arquivo_pdf = ? WHERE id = ?;", (nome_pdf, romaneio_id))
        cur.execute("UPDATE cargas SET status = 'finalizada' WHERE id = ?;", (carga_id,))
        conn.commit()
        codigo = f"{numero_romaneio:04d}-{datetime.strptime(data_envio, '%Y-%m-%d'):%d%m%y}"
        return jsonify({'ok': True, 'id': romaneio_id, 'numero': numero_romaneio, 'codigo': codigo,
                        'quantidadePallets': len(pallets), 'arquivoPdf': nome_pdf,
                        'aderenciaCarga': comparacao['percentual']})
    except Exception as err:
        conn.rollback()
        return jsonify({'ok': False, 'erro': f'Não foi possível gerar o romaneio: {err}'}), 500
    finally:
        conn.close()


@app.route('/api/romaneios', methods=['GET'])
def api_romaneios_listar():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT r.*, c.numero AS carga_numero FROM romaneios r
                       LEFT JOIN cargas c ON c.id=r.carga_id ORDER BY r.numero DESC LIMIT 200;""")
        linhas = []
        for r in cur.fetchall():
            item = dict(r)
            data = item.get('data_envio') or str(item.get('data_hora') or '')[:10]
            try:
                item['codigo'] = f"{int(item['numero']):04d}-{datetime.strptime(data, '%Y-%m-%d'):%d%m%y}"
            except (ValueError, TypeError):
                item['codigo'] = str(item.get('numero') or '')
            linhas.append(item)
        return jsonify(linhas)
    finally:
        conn.close()


@app.route('/api/romaneios/<int:romaneio_id>/pdf', methods=['GET'])
def api_romaneio_pdf(romaneio_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT r.*, c.numero AS carga_numero FROM romaneios r
                       LEFT JOIN cargas c ON c.id=r.carga_id WHERE r.id = ?;""", (romaneio_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'erro': 'Romaneio não encontrado.'}), 404
        registro = dict(row)
        cur.execute("""SELECT p.* FROM pallets p JOIN romaneio_pallets rp ON rp.pallet_id=p.id
                       WHERE rp.romaneio_id=? ORDER BY p.numero;""", (romaneio_id,))
        pallets = [_pallet_com_itens(p) for p in cur.fetchall()]
        registro['fotos'] = fotos_pdf(conn, romaneio_id)
        caminho = gerar_pdf_romaneio(registro, pallets)
        nome_pdf = os.path.basename(caminho)
        cur.execute("UPDATE romaneios SET arquivo_pdf=? WHERE id=?;", (nome_pdf, romaneio_id))
        conn.commit()
        return send_file(caminho, as_attachment=False)
    finally:
        conn.close()


@app.route('/api/romaneios/<int:romaneio_id>', methods=['DELETE'])
def api_romaneio_excluir(romaneio_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT numero, carga_id, arquivo_pdf FROM romaneios WHERE id=?;", (romaneio_id,))
        romaneio = cur.fetchone()
        if not romaneio:
            return jsonify({'ok': False, 'erro': 'Romaneio não encontrado.'}), 404
        cur.execute("SELECT pallet_id FROM romaneio_pallets WHERE romaneio_id=?;", (romaneio_id,))
        pallet_ids = [r['pallet_id'] for r in cur.fetchall()]
        cur.executemany("UPDATE pallets SET status='armazenado', romaneio_id=NULL WHERE id=? AND romaneio_id=?;",
                        [(pallet_id, romaneio_id) for pallet_id in pallet_ids])
        cur.execute("DELETE FROM romaneio_pallets WHERE romaneio_id=?;", (romaneio_id,))
        cur.execute("DELETE FROM romaneios WHERE id=?;", (romaneio_id,))
        if romaneio['carga_id']:
            cur.execute("UPDATE cargas SET status='aberta' WHERE id=?;", (romaneio['carga_id'],))
        conn.commit()
        arquivo = os.path.basename(romaneio['arquivo_pdf'] or '')
        if arquivo:
            from paths import pdf_dir
            caminho = os.path.join(pdf_dir(), arquivo)
            if os.path.isfile(caminho):
                try:
                    os.remove(caminho)
                except OSError:
                    pass
        return jsonify({'ok': True, 'numero': romaneio['numero'], 'palletsRestaurados': len(pallet_ids)})
    except Exception as err:
        conn.rollback()
        return jsonify({'ok': False, 'erro': f'Não foi possível excluir o Romaneio: {err}'}), 500
    finally:
        conn.close()


# ---------- PDF padrao para teste de saida ----------
@app.route('/api/pdf/teste', methods=['GET'])
def api_pdf_teste():
    """Gera um packing list de exemplo sem gravar dados no historico."""
    agora = datetime.now()
    modulo_teste = request.args.get('modulo', 'fios')
    if modulo_teste not in ('fios', 'painel'):
        modulo_teste = 'fios'
    registro_teste = {
        'numero': 0,
        'modulo': modulo_teste,
        'data_hora': agora.isoformat(timespec='seconds'),
        'cliente_codigo': '000000',
        'cliente_nome': 'CLIENTE DE TESTE',
        'cliente_abrev': 'TESTE-SAIDA',
        'cliente_endereco': 'RUA EXEMPLO, 100',
        'cliente_bairro': 'DISTRITO INDUSTRIAL',
        'cliente_cidade': 'CIDADE DE TESTE',
        'cliente_uf': 'PR',
        'medida_palete': '1,00 X 1,20',
        'peso_liquido': 250.00,
        'peso_bruto': 288.60,
        'carreteis': 2,
        'itens': [
            {
                'op': '000001',
                'oc': 'OC-TESTE',
                'pedido': 'PED-001',
                'codigo_produto': 'PROD-001',
                'descricao': 'PRODUTO PADRAO PARA TESTE DE SAIDA',
                'tipo': 'NU',
                'qtde': 125.00,
            },
            {
                'op': '000002',
                'oc': 'OC-TESTE',
                'pedido': 'PED-002',
                'codigo_produto': 'PROD-002',
                'descricao': 'PRODUTO PADRAO PARA TESTE DE SAIDA',
                'tipo': 'PMC',
                'qtde': 125.00,
            },
        ],
    }
    try:
        caminho_pdf = gerar_pdf_etiqueta(registro_teste)
        return send_file(caminho_pdf, as_attachment=False)
    except Exception as err:
        return jsonify({'ok': False, 'erro': f'Erro ao gerar PDF de teste: {err}'}), 500


def executar():
    """Sobe o servidor Flask. Chamada tanto por 'python server.py' direto
    quanto pelo iniciar.py (que captura e mostra qualquer erro na tela)."""
    try:
        cfg = load_config()
        port = int(os.environ.get('PORT') or cfg.get('porta_do_sistema') or 3010)
    except Exception:
        port = int(os.environ.get('PORT') or 3010)

    print("==========================================")
    print(f"Portal Logística rodando em: http://localhost:{port}")
    print("Deixe esta janela aberta enquanto usa o sistema.")
    print("==========================================")

    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    executar()
