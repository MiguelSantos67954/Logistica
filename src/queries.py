# src/queries.py
#
# IMPORTANTE: as duas queries de ORDEM DE PRODUCAO abaixo (fios e painel) sao um
# ponto de partida baseado nas tabelas padrao do Protheus (SC2010 = Ordem de
# Producao, SC6010/SC5010 = Pedido de Venda, SB1010 = Produto, SA1010 = Cliente).
# Eu NAO tive acesso ao codigo M da consulta Power Query "Funil" original (fica
# comprimido/binario dentro do .xlsm), entao nao consigo garantir que os nomes de
# campo abaixo sao EXATAMENTE os que a sua base usa (isso varia com customizacao).
# Rode a query direto no SSMS primeiro e ajuste os nomes de campo se necessario -
# o resto do sistema (cache local, formularios, calculo de peso) nao muda.

# Query "Funil" da planilha: cruza OP (Ordem de Producao) com o pedido de venda,
# o produto e o codigo do cliente. Usada para preencher OC/Pedido/Codigo/Descricao
# automaticamente a partir da OP digitada, no modulo FIOS.
ORDENS_QUERY_FIOS = """
SELECT
    (CASE
        WHEN LEFT(LTRIM(RTRIM(SC2.C2_NUM)), 1) = '0'
            THEN SUBSTRING(LTRIM(RTRIM(SC2.C2_NUM)), 2, LEN(LTRIM(RTRIM(SC2.C2_NUM))))
        ELSE LTRIM(RTRIM(SC2.C2_NUM))
     END + LTRIM(RTRIM(SC2.C2_ITEM))) AS OP,
    SC6.C6_NUMPCOM    AS OC,
    SC6.C6_NUM        AS PEDIDO,
    SC2.C2_PRODUTO    AS CODIGO_PRODUTO,
    SB1.B1_DESC       AS DESCRICAO,
    SC6.C6_CLI        AS CODIGO_CLIENTE,
    CASE
        WHEN SC5.C5_MENNOTA LIKE '%PMC%' THEN 'PMC'
        WHEN SC5.C5_MENNOTA LIKE '%PKT%' THEN 'PKT'
        ELSE ''
    END AS ISOLACAO
FROM SC2010 AS SC2
LEFT JOIN SC6010 AS SC6
    ON SC6.C6_NUM = SC2.C2_PEDIDO AND SC6.C6_ITEM = SC2.C2_ITEMPV AND SC6.D_E_L_E_T_ = ''
LEFT JOIN SC5010 AS SC5
    ON SC5.C5_NUM = SC6.C6_NUM AND SC5.C5_FILIAL = SC6.C6_FILIAL AND SC5.D_E_L_E_T_ = ''
LEFT JOIN SB1010 AS SB1
    ON SB1.B1_COD = SC2.C2_PRODUTO AND SB1.B1_FILIAL = SC2.C2_FILIAL AND SB1.D_E_L_E_T_ = ''
WHERE
    SC2.D_E_L_E_T_ = ''
    -- Inclui OPs em aberto e finalizadas (C2_DATRF preenchida).
    AND SC2.C2_SEQUEN = '001'  -- produto principal; evita componentes repetirem a mesma OP/item
ORDER BY SC2.C2_NUM DESC;
"""

# Mesma ideia, para o modulo PAINEL_KITS (paineis corrugados / kits). Aqui nao
# existe o conceito de ISOLACAO (PMC/PKT) - troque por outro campo se seu painel
# tiver alguma classificacao equivalente (ex: largura, tipo de kit).
ORDENS_QUERY_PAINEL = """
SELECT
    (CASE
        WHEN LEFT(LTRIM(RTRIM(SC2.C2_NUM)), 1) = '0'
            THEN SUBSTRING(LTRIM(RTRIM(SC2.C2_NUM)), 2, LEN(LTRIM(RTRIM(SC2.C2_NUM))))
        ELSE LTRIM(RTRIM(SC2.C2_NUM))
     END + LTRIM(RTRIM(SC2.C2_ITEM))) AS OP,
    SC6.C6_NUMPCOM    AS OC,
    SC6.C6_NUM        AS PEDIDO,
    SC2.C2_PRODUTO    AS CODIGO_PRODUTO,
    SB1.B1_DESC       AS DESCRICAO,
    SC6.C6_CLI        AS CODIGO_CLIENTE,
    '' AS ISOLACAO
FROM SC2010 AS SC2
LEFT JOIN SC6010 AS SC6
    ON SC6.C6_NUM = SC2.C2_PEDIDO AND SC6.C6_ITEM = SC2.C2_ITEMPV AND SC6.D_E_L_E_T_ = ''
LEFT JOIN SB1010 AS SB1
    ON SB1.B1_COD = SC2.C2_PRODUTO AND SB1.B1_FILIAL = SC2.C2_FILIAL AND SB1.D_E_L_E_T_ = ''
WHERE
    SC2.D_E_L_E_T_ = ''
    -- Inclui OPs em aberto e finalizadas (C2_DATRF preenchida).
    AND SC2.C2_SEQUEN = '001'
ORDER BY SC2.C2_NUM DESC;
"""

# Esta ja e' a mesma consulta usada com sucesso no sistema Funil (aba "Cliente"
# do .xlsm e' literalmente a SA1010 crua) - deve funcionar sem ajustes.
CLIENTE_QUERY = """
SELECT
    A1_COD    AS CODIGO,
    A1_NREDUZ AS NOME,
    A1_END    AS ENDERECO,
    A1_BAIRRO AS BAIRRO,
    A1_MUN    AS CIDADE,
    A1_EST    AS UF
FROM SA1010
WHERE D_E_L_E_T_ = ' ';
"""


def query_dados_pedido(numero_pedido):
    """Consulta itens de um pedido para completar OPs cujo vínculo veio vazio."""
    pedido = str(numero_pedido or '').strip().replace("'", "''")
    return f"""
SELECT
    LTRIM(RTRIM(SC6.C6_NUM)) AS PEDIDO,
    LTRIM(RTRIM(SC6.C6_ITEM)) AS ITEM,
    LTRIM(RTRIM(SC6.C6_NUMPCOM)) AS OC,
    LTRIM(RTRIM(SC6.C6_PRODUTO)) AS CODIGO_PRODUTO,
    SB1.B1_DESC AS DESCRICAO,
    LTRIM(RTRIM(SC6.C6_CLI)) AS CODIGO_CLIENTE,
    CASE WHEN SC5.C5_MENNOTA LIKE '%PMC%' THEN 'PMC'
         WHEN SC5.C5_MENNOTA LIKE '%PKT%' THEN 'PKT' ELSE '' END AS ISOLACAO
FROM SC6010 AS SC6
LEFT JOIN SC5010 AS SC5
    ON SC5.C5_NUM = SC6.C6_NUM AND SC5.C5_FILIAL = SC6.C6_FILIAL AND SC5.D_E_L_E_T_ = ''
LEFT JOIN SB1010 AS SB1
    ON SB1.B1_COD = SC6.C6_PRODUTO AND SB1.B1_FILIAL = SC6.C6_FILIAL AND SB1.D_E_L_E_T_ = ''
WHERE SC6.D_E_L_E_T_ = ''
  AND LTRIM(RTRIM(SC6.C6_NUM)) IN ('{pedido}', RIGHT('000000' + '{pedido}', 6))
ORDER BY SC6.C6_ITEM;
"""
