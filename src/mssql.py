"""
src/mssql.py

Conexao com o SQL Server do TOTVS usando autenticacao SQL (usuario "pcp"),
conforme definido em config.json. Mesma logica ja validada no sistema Funil.
"""

import os
import json
import subprocess

from paths import base_dir

# IMPORTANTE: pyodbc só é importado dentro das funções que realmente precisam
# dele (mais abaixo), e não aqui no topo do arquivo. Se o pacote pyodbc ou o
# driver ODBC do SQL Server não estiverem instalados na máquina, isso NÃO pode
# derrubar o sistema inteiro na inicialização — só deve dar erro na hora de
# tentar atualizar os dados do ERP (botão "Atualizar dados do ERP").


def _caminho_config():
    return os.path.join(base_dir(), 'config.json')


def load_config():
    caminho = _caminho_config()
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"config.json nao encontrado em: {caminho}")
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)


def _importar_pyodbc():
    try:
        import pyodbc  # pyrefly: ignore [missing-import]
        return pyodbc
    except ImportError as err:
        raise RuntimeError(
            "O pacote 'pyodbc' não está instalado nesta máquina. Rode:\n"
            "    pip install -r requirements.txt\n"
            "(ou 'pip install pyodbc --break-system-packages' se estiver fora de um venv). "
            f"Erro original: {err}"
        ) from err


def _driver_odbc_disponivel():
    pyodbc = _importar_pyodbc()
    preferidos = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]
    instalados = pyodbc.drivers()
    for nome in preferidos:
        if nome in instalados:
            return nome
    raise RuntimeError(
        "Nenhum driver ODBC de SQL Server foi encontrado nesta maquina. "
        "Instale o 'ODBC Driver 17 for SQL Server' (ou 18) da Microsoft. "
        f"Drivers instalados: {instalados}"
    )


def montar_connection_string(cfg=None):
    if cfg is None:
        cfg = load_config()

    driver = _driver_odbc_disponivel()

    server = cfg.get('server')
    if not server:
        raise ValueError("config.json: campo 'server' esta vazio.")

    instance = (cfg.get('instanceName') or '').strip()
    port = cfg.get('port')

    endereco = server
    if instance:
        endereco += f"\\{instance}"
    if port:
        endereco += f",{port}"

    database = cfg.get('database') or ''
    encrypt = 'yes' if cfg.get('encrypt') else 'no'
    trust_cert = 'yes' if cfg.get('trustServerCertificate') else 'no'

    partes = [
        f"DRIVER={{{driver}}}",
        f"SERVER={endereco}",
        f"DATABASE={database}",
        f"Encrypt={encrypt}",
        f"TrustServerCertificate={trust_cert}",
    ]

    usuario = cfg.get('user') or ''
    senha = cfg.get('password') or ''
    if not usuario or not senha:
        raise ValueError("config.json: 'user' e 'password' precisam estar preenchidos (auth SQL).")
    partes.append(f"UID={usuario}")
    partes.append(f"PWD={senha}")

    return ";".join(partes) + ";"


def get_erp_connection():
    pyodbc = _importar_pyodbc()
    cfg = load_config()
    conn_str = montar_connection_string(cfg)
    try:
        return pyodbc.connect(conn_str, timeout=10)
    except pyodbc.Error as err:
        sqlstate = err.args[0] if err.args else ''
        if sqlstate == '28000' or '18456' in str(err):
            raise RuntimeError(
                "Login recusado pelo SQL Server (erro 18456). Causas mais comuns:\n"
                "  1) Usuario ou senha errados no config.json.\n"
                "  2) O SQL Server esta configurado so' para 'Windows Authentication mode' - "
                "peca ao TI para habilitar 'SQL Server and Windows Authentication mode' "
                "(modo misto) e reiniciar o servico do SQL Server. Esse e' o problema ja "
                "identificado anteriormente com o usuario 'pcp'.\n"
                "  3) O login existe mas esta desabilitado ou sem permissao no banco "
                f"'{cfg.get('database')}'.\n"
                f"Erro original: {err}"
            ) from err
        raise


def _run_query_dotnet(sql: str, params=None):
    """Executa a consulta pelo cliente SQL nativo do Windows.

    Este fallback evita a dependencia do ODBC moderno em maquinas que possuem
    apenas o driver legado "SQL Server".
    """
    if params:
        raise ValueError("O fallback .NET ainda nao aceita parametros de consulta.")

    script = os.path.join(base_dir(), 'src', 'query_sql_dotnet.ps1')
    if not os.path.exists(script):
        raise FileNotFoundError(f"Script de conexao .NET nao encontrado: {script}")

    processo = subprocess.run(
        [
            'powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive',
            '-ExecutionPolicy', 'Bypass', '-File', script,
        ],
        input=sql,
        text=True,
        encoding='utf-8',
        capture_output=True,
        timeout=120,
        check=False,
    )
    if processo.returncode != 0:
        detalhe = (processo.stderr or processo.stdout or '').strip()
        raise RuntimeError(f"Falha na conexao SQL pelo cliente nativo do Windows: {detalhe}")

    saida = processo.stdout.strip()
    return json.loads(saida) if saida else []


def run_query(sql: str, params=None):
    """Executa uma query no TOTVS e retorna uma lista de dicts (uma linha por dict)."""
    # O driver generico "SQL Server" e legado e falha com TLS nas versoes
    # atuais do Windows. Nessa situacao, evita esperar o timeout do ODBC em
    # cada consulta e vai direto para o cliente .NET, que usa a pilha nativa.
    try:
        if _driver_odbc_disponivel() == 'SQL Server':
            return _run_query_dotnet(sql, params)
    except Exception:
        return _run_query_dotnet(sql, params)

    try:
        conn = get_erp_connection()
    except Exception:
        return _run_query_dotnet(sql, params)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params or [])
        colunas = [c[0] for c in cursor.description]
        return [dict(zip(colunas, row)) for row in cursor.fetchall()]
    finally:
        conn.close()
