import time
from datetime import datetime

from db import get_connection
from src.mssql import run_query
from src.queries import ORDENS_QUERY_FIOS, ORDENS_QUERY_PAINEL, CLIENTE_QUERY


def _texto_ordem(ordem):
    return ' '.join(str(ordem.get(campo, '') or '').upper() for campo in
                    ('DESCRICAO', 'CODIGO_PRODUTO', 'ISOLACAO'))


def _modulo_ordem(ordem_fios, ordem_painel):
    """Escolhe um único módulo quando a mesma OP vem nas duas consultas.

    PMC/PKT identificam fios. Produtos descritos como kit ou painel pertencem ao
    módulo Outros Materiais. Sem um marcador explícito, preservamos Fios como padrão,
    que é o comportamento histórico do preenchimento.
    """
    texto = _texto_ordem(ordem_fios or ordem_painel)
    isolacao = str((ordem_fios or {}).get('ISOLACAO', '') or '').strip().upper()
    if isolacao in ('PMC', 'PKT'):
        return 'fios'
    if 'KIT' in texto or 'PAINEL' in texto:
        return 'painel'
    return 'fios'


def _ordens_sem_duplicidade(ordens_fios, ordens_painel):
    """Retorna pares (módulo, ordem), mantendo cada OP em apenas um módulo."""
    fios = {str(r.get('OP', '') or '').strip(): r for r in ordens_fios if str(r.get('OP', '') or '').strip()}
    painel = {str(r.get('OP', '') or '').strip(): r for r in ordens_painel if str(r.get('OP', '') or '').strip()}
    resultado = []
    for op in dict.fromkeys((*fios.keys(), *painel.keys())):
        if op in fios and op in painel:
            modulo = _modulo_ordem(fios[op], painel[op])
            resultado.append((modulo, fios[op] if modulo == 'fios' else painel[op]))
        elif op in fios:
            resultado.append(('fios', fios[op]))
        else:
            resultado.append(('painel', painel[op]))
    return resultado


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
        ordens_classificadas = _ordens_sem_duplicidade(ordens_fios, ordens_painel)
        linhas = [
            (str(r.get('OP', '') or '').strip(), modulo, r.get('OC', ''), r.get('PEDIDO', ''),
             str(r.get('CODIGO_PRODUTO', '') or '').strip(), r.get('DESCRICAO', ''),
             str(r.get('CODIGO_CLIENTE', '') or '').strip(), r.get('ISOLACAO', '') if modulo == 'fios' else '')
            for modulo, r in ordens_classificadas
        ]
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
            'ordensFios': sum(modulo == 'fios' for modulo, _ in ordens_classificadas),
            'ordensPainel': sum(modulo == 'painel' for modulo, _ in ordens_classificadas),
            'clientes': len(clientes),
            'duracaoSegundos': round(time.time() - inicio, 1),
        }
    finally:
        conn.close()
