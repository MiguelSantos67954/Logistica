import time
from datetime import datetime

from db import get_connection
from src.mssql import run_query
from src.queries import ORDENS_QUERY_FIOS, ORDENS_QUERY_PAINEL, CLIENTE_QUERY


def refresh_tudo() -> dict:
    """Atualiza o cache local (SQLite) com os dados atuais do TOTVS.
    Equivale a clicar em 'Atualizar dados do ERP' no Portal PCP / rodar o
    refresh da Power Query na planilha original."""
    inicio = time.time()

    ordens_fios = run_query(ORDENS_QUERY_FIOS)
    ordens_painel = run_query(ORDENS_QUERY_PAINEL)
    clientes = run_query(CLIENTE_QUERY)

    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM cache_ordens;")
        linhas = []
        for r in ordens_fios:
            linhas.append((str(r.get('OP', '') or '').strip(), 'fios', r.get('OC', ''), r.get('PEDIDO', ''),
                            str(r.get('CODIGO_PRODUTO', '') or '').strip(), r.get('DESCRICAO', ''),
                            str(r.get('CODIGO_CLIENTE', '') or '').strip(), r.get('ISOLACAO', '')))
        for r in ordens_painel:
            linhas.append((str(r.get('OP', '') or '').strip(), 'painel', r.get('OC', ''), r.get('PEDIDO', ''),
                            str(r.get('CODIGO_PRODUTO', '') or '').strip(), r.get('DESCRICAO', ''),
                            str(r.get('CODIGO_CLIENTE', '') or '').strip(), r.get('ISOLACAO', '')))
        cursor.executemany(
            "INSERT OR REPLACE INTO cache_ordens (op, modulo, oc, pedido, codigo_produto, descricao, "
            "codigo_cliente, isolacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            linhas
        )

        cursor.execute("DELETE FROM cache_clientes;")
        cursor.executemany(
            "INSERT OR REPLACE INTO cache_clientes (codigo, nome, endereco, bairro, cidade, uf) "
            "VALUES (?, ?, ?, ?, ?, ?);",
            [
                (str(r.get('CODIGO', '') or '').strip(), r.get('NOME', ''), r.get('ENDERECO', ''),
                 r.get('BAIRRO', ''), r.get('CIDADE', ''), r.get('UF', ''))
                for r in clientes
            ]
        )

        agora_iso = datetime.now().isoformat()
        cursor.execute("INSERT OR REPLACE INTO meta (chave, valor) VALUES (?, ?);",
                        ('ultima_atualizacao', agora_iso))
        conn.commit()

        return {
            'ok': True,
            'ordensFios': len(ordens_fios),
            'ordensPainel': len(ordens_painel),
            'clientes': len(clientes),
            'duracaoSegundos': round(time.time() - inicio, 1),
        }
    finally:
        conn.close()
