import sqlite3
import os
import json
from paths import base_dir

DB_DIR = os.path.join(base_dir(), 'db')
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, 'packing_list.sqlite')


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.executescript("""
        -- Cache local das ordens de producao / pedidos vindos do TOTVS.
        -- Alimentada pelo refresh (src/refresh.py). Equivale a aba oculta "Funil" da planilha.
        CREATE TABLE IF NOT EXISTS cache_ordens (
            op              TEXT NOT NULL,
            modulo          TEXT NOT NULL,   -- 'fios' ou 'painel'
            oc              TEXT,
            pedido          TEXT,
            codigo_produto  TEXT,
            descricao       TEXT,
            codigo_cliente  TEXT,
            isolacao        TEXT,            -- PMC / PKT / vazio (so' usado no modulo fios)
            PRIMARY KEY (op, modulo)
        );

        -- Cache local de clientes (equivale a aba "Cliente" = SA1010 do TOTVS)
        CREATE TABLE IF NOT EXISTS cache_clientes (
            codigo    TEXT PRIMARY KEY,
            nome      TEXT,
            endereco  TEXT,
            bairro    TEXT,
            cidade    TEXT,
            uf        TEXT
        );

        -- Abreviacao usada no nome do arquivo/pasta do PDF (equivale as colunas IP:IQ
        -- da aba Cliente na planilha). Mantida manualmente, nao vem do ERP.
        CREATE TABLE IF NOT EXISTS clientes_abrev (
            codigo       TEXT PRIMARY KEY,
            abreviacao   TEXT NOT NULL
        );

        -- Peso de tara por medida de palete (equivale a aba "PALETES")
        CREATE TABLE IF NOT EXISTS paletes (
            medida      TEXT PRIMARY KEY,
            peso_tara   REAL NOT NULL
        );

        -- Historico de paletes gravados (equivale a aba oculta "Base")
        CREATE TABLE IF NOT EXISTS pallets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            numero          INTEGER NOT NULL,
            modulo          TEXT NOT NULL,     -- 'fios' ou 'painel'
            data_hora       TEXT NOT NULL,
            cliente_codigo  TEXT,
            cliente_nome    TEXT,
            cliente_abrev   TEXT,
            medida_palete   TEXT,
            peso_liquido    REAL,
            peso_bruto      REAL,
            carreteis       INTEGER,
            itens_json      TEXT NOT NULL,     -- lista das linhas (OP/OC/Pedido/Produto/Qtde/Tipo...)
            arquivo_pdf     TEXT
        );

        -- Planejamento de cargas com pallets ainda no estoque de produto acabado.
        CREATE TABLE IF NOT EXISTS cargas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            numero          INTEGER NOT NULL UNIQUE,
            data_hora       TEXT NOT NULL,
            cliente         TEXT,
            transportadora  TEXT,
            veiculo         TEXT,
            motorista       TEXT,
            prioridade      TEXT,
            observacao      TEXT,
            status          TEXT NOT NULL DEFAULT 'aberta'
        );

        CREATE TABLE IF NOT EXISTS carga_pallets (
            carga_id        INTEGER NOT NULL,
            pallet_id       INTEGER NOT NULL,
            PRIMARY KEY (carga_id, pallet_id),
            FOREIGN KEY (carga_id) REFERENCES cargas(id),
            FOREIGN KEY (pallet_id) REFERENCES pallets(id)
        );

        CREATE TABLE IF NOT EXISTS carga_itens (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            carga_id        INTEGER NOT NULL,
            codigo_produto  TEXT NOT NULL,
            descricao       TEXT,
            quantidade      REAL NOT NULL,
            observacao      TEXT,
            FOREIGN KEY (carga_id) REFERENCES cargas(id)
        );

        -- Documento definitivo de expedição. A baixa mantém o pallet no histórico.
        CREATE TABLE IF NOT EXISTS romaneios (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            numero          INTEGER NOT NULL UNIQUE,
            data_hora       TEXT NOT NULL,
            transportadora  TEXT,
            veiculo         TEXT,
            motorista       TEXT,
            observacao      TEXT,
            arquivo_pdf     TEXT
        );

        CREATE TABLE IF NOT EXISTS romaneio_pallets (
            romaneio_id     INTEGER NOT NULL,
            pallet_id       INTEGER NOT NULL UNIQUE,
            PRIMARY KEY (romaneio_id, pallet_id),
            FOREIGN KEY (romaneio_id) REFERENCES romaneios(id),
            FOREIGN KEY (pallet_id) REFERENCES pallets(id)
        );

        CREATE TABLE IF NOT EXISTS romaneio_fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            romaneio_id INTEGER NOT NULL REFERENCES romaneios(id) ON DELETE CASCADE,
            categoria TEXT NOT NULL CHECK(categoria IN ('pallets', 'carga')),
            imagem BLOB NOT NULL
        );

        -- Agenda de expedição importada do módulo Programação de Carregamento do Portal PCP.
        CREATE TABLE IF NOT EXISTS programacao_carregamentos (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            data_carregamento   TEXT NOT NULL,
            horario             TEXT NOT NULL,
            caminhao            TEXT NOT NULL,
            material            TEXT NOT NULL,
            cliente             TEXT NOT NULL,
            observacao          TEXT,
            criado_em           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            login           TEXT NOT NULL COLLATE NOCASE UNIQUE,
            nome            TEXT NOT NULL,
            senha_hash      TEXT NOT NULL,
            administrador   INTEGER NOT NULL DEFAULT 0,
            ativo           INTEGER NOT NULL DEFAULT 1,
            permissoes_json TEXT NOT NULL DEFAULT '{}',
            criado_em       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS auditoria (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id  INTEGER,
            usuario     TEXT NOT NULL,
            data_hora   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            acao        TEXT NOT NULL,
            metodo      TEXT,
            caminho     TEXT,
            detalhes    TEXT,
            status_http INTEGER,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS meta (
            chave  TEXT PRIMARY KEY,
            valor  TEXT
        );
        """)
        conn.commit()

        # Migracao compatível com bases criadas antes dos módulos de expedição.
        colunas_pallets = {r['name'] for r in cur.execute("PRAGMA table_info(pallets);").fetchall()}
        if 'status' not in colunas_pallets:
            cur.execute("ALTER TABLE pallets ADD COLUMN status TEXT NOT NULL DEFAULT 'armazenado';")
        if 'romaneio_id' not in colunas_pallets:
            cur.execute("ALTER TABLE pallets ADD COLUMN romaneio_id INTEGER;")

        colunas_romaneios = {r['name'] for r in cur.execute("PRAGMA table_info(romaneios);").fetchall()}
        novas_colunas_romaneio = {
            'data_envio': 'TEXT',
            'cliente_codigo': 'TEXT',
            'cliente_nome': 'TEXT',
            'frete': "TEXT NOT NULL DEFAULT 'CIF'",
            'peso_liquido': 'REAL',
            'peso_bruto': 'REAL',
            'quantidade_pallets': 'INTEGER',
            'carga_id': 'INTEGER',
            'aderencia_carga': 'REAL',
        }
        for coluna, definicao in novas_colunas_romaneio.items():
            if coluna not in colunas_romaneios:
                cur.execute(f"ALTER TABLE romaneios ADD COLUMN {coluna} {definicao};")

        # Seed inicial das medidas de palete, com base na planilha original
        cur.execute("SELECT COUNT(*) AS n FROM paletes;")
        if cur.fetchone()['n'] == 0:
            cur.executemany(
                "INSERT INTO paletes (medida, peso_tara) VALUES (?, ?);",
                [
                    ('0,62 X 1,20', 14),
                    ('1,34 X 0,68', 14),
                    ('1,20 X 1,20', 25),
                ]
            )

        # Seed inicial das abreviacoes de cliente vistas na planilha original
        cur.execute("SELECT COUNT(*) AS n FROM clientes_abrev;")
        if cur.fetchone()['n'] == 0:
            cur.executemany(
                "INSERT INTO clientes_abrev (codigo, abreviacao) VALUES (?, ?);",
                [
                    ('1', 'ITAIPU'),
                    ('2', 'ITB'),
                    ('5', 'ROMAGNOLE'),
                    ('10', 'TRAEL'),
                ]
            )

        # Administrador inicial. A senha fica salva somente como hash forte.
        cur.execute("SELECT id FROM usuarios WHERE login = ? COLLATE NOCASE;", ('Admin',))
        if not cur.fetchone():
            permissoes_admin = {
                'identificacao_pallets': True, 'relacao_carga': True, 'romaneio': True,
                'programacao_carregamento': True, 'carregamento_criar': True,
                'carregamento_editar': True, 'carregamento_excluir': True,
            }
            cur.execute('''INSERT INTO usuarios
                (login, nome, senha_hash, administrador, ativo, permissoes_json)
                VALUES (?, ?, ?, 1, 1, ?)''', (
                    'Admin', 'Administrador',
                    'scrypt:32768:8:1$bJ2UNxgEDgxmWmAW$935c6249c387df2d4f7fb77918cf5af1bc2ff21cbabdf4c2bef770862d04d6811cccaee391cd71b174a691cea5ef12e72c842a4f4ffb6a03e43158dbd49d84ac',
                    json.dumps(permissoes_admin, ensure_ascii=False)
                ))
        conn.commit()


init_db()
