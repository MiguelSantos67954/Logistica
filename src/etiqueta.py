import os
from datetime import datetime
from html import escape
from uuid import uuid4

from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from paths import pdf_dir


PRETO = colors.black
CINZA_TITULO = colors.HexColor('#a6a6a6')
CINZA_CLARO = colors.HexColor('#dddddd')


def _texto(valor):
    return escape(str(valor or ''))


def _numero(valor, casas=2):
    return f"{float(valor or 0):,.{casas}f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def _data_br(valor):
    try:
        return datetime.fromisoformat(valor).strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return str(valor or '')[:10]


def _estilo(nome, tamanho=7, negrito=False, alinhamento=TA_LEFT, entrelinha=None):
    return ParagraphStyle(
        nome, fontName='Helvetica-Bold' if negrito else 'Helvetica', fontSize=tamanho,
        leading=entrelinha or tamanho + 1, alignment=alinhamento, spaceAfter=0, spaceBefore=0,
    )


def _par(valor, estilo):
    return Paragraph(_texto(valor), estilo)


def _logo():
    logo = Table([
        ['', Paragraph('<b><i>AMT</i></b>', _estilo('logo', 23, alinhamento=TA_CENTER))],
        ['', Paragraph('PRODUTOS ELÉTRICOS', _estilo('logo_sub', 4.5, negrito=True, alinhamento=TA_CENTER))],
    ], colWidths=[1.25 * cm, 2.5 * cm], rowHeights=[0.65 * cm, 0.2 * cm])
    logo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#333333')), ('SPAN', (0, 0), (0, 1)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return logo


def _cabecalho(registro):
    titulo = Paragraph(
        f"<b>PACKING LIST - Nº {int(registro['numero']):05d}</b>",
        _estilo('titulo', 24, negrito=True, alinhamento=TA_CENTER),
    )
    tabela = Table([[_logo(), titulo]], colWidths=[5 * cm, 20.5 * cm], rowHeights=[1.35 * cm])
    tabela.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, PRETO), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 0.45 * cm), ('RIGHTPADDING', (0, 0), (-1, -1), 0.2 * cm),
    ]))
    return tabela


def _bloco_entrega(registro):
    pequeno = _estilo('entrega', 7)
    dados = [
        [Paragraph('<b>Dados da Entrega</b>', _estilo('secao_entrega', 7, negrito=True, alinhamento=TA_CENTER)), ''],
        [Paragraph('<b>Cliente:</b>', pequeno), _par(registro.get('cliente_nome'), pequeno)],
        [Paragraph('<b>Endereço:</b>', pequeno), _par(registro.get('cliente_endereco'), pequeno)],
        [Paragraph('<b>Bairro:</b>', pequeno), _par(registro.get('cliente_bairro'), pequeno)],
        [Paragraph('<b>Cidade:</b>', pequeno), _par(registro.get('cliente_cidade'), pequeno)],
        [Paragraph('<b>UF:</b>', pequeno), _par(registro.get('cliente_uf'), pequeno)],
    ]
    tabela = Table(dados, colWidths=[2.2 * cm, 15.4 * cm], rowHeights=[0.43 * cm] + [0.36 * cm] * 5)
    tabela.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)), ('BACKGROUND', (0, 0), (1, 0), CINZA_TITULO),
        ('BACKGROUND', (0, 1), (1, -1), CINZA_CLARO), ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'RIGHT'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return tabela


def _bloco_palete(registro):
    painel = registro.get('modulo') == 'painel'
    rotulo_volumes = 'Peças' if painel else 'Carretéis'
    pequeno = _estilo('palete', 7)
    dados = [
        [Paragraph('<b>Dados do Palete</b>', _estilo('secao_palete', 7, negrito=True, alinhamento=TA_CENTER)), ''],
        [Paragraph('<b>Data:</b>', pequeno), Paragraph(_data_br(registro.get('data_hora')), pequeno)],
        [Paragraph('<b>Peso Líquido:</b>', pequeno), Paragraph(_numero(registro.get('peso_liquido')), pequeno)],
        [Paragraph('<b>Peso Bruto:</b>', pequeno), Paragraph(_numero(registro.get('peso_bruto')), pequeno)],
        [Paragraph(f'<b>{rotulo_volumes}:</b>', pequeno), Paragraph(_numero(registro.get('carreteis'), 0), pequeno)],
        [Paragraph('<b>Medida do PLT:</b>', pequeno), _par(registro.get('medida_palete'), pequeno)],
    ]
    tabela = Table(dados, colWidths=[3.2 * cm, 2.6 * cm], rowHeights=[0.43 * cm] + [0.36 * cm] * 5)
    tabela.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)), ('BACKGROUND', (0, 0), (1, 0), CINZA_TITULO),
        ('GRID', (0, 0), (-1, -1), 0.45, PRETO), ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'RIGHT'), ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return tabela


def _identificacao(registro):
    if registro.get('modulo') == 'painel':
        return Paragraph(f"#{int(registro['numero']):05d}#", _estilo('numero_grande', 25, alinhamento=TA_CENTER))
    return code128.Code128(
        str(int(registro['numero'])), barHeight=0.8 * cm, barWidth=0.34,
        humanReadable=True,
    )


def _dados_superiores(registro):
    direita = Table([[_bloco_palete(registro)], [_identificacao(registro)]], colWidths=[5.8 * cm], rowHeights=[2.25 * cm, 1.25 * cm])
    direita.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0,
    )]))
    geral = Table([[_bloco_entrega(registro), direita]], colWidths=[18.0 * cm, 6.0 * cm], hAlign='CENTER')
    geral.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0.35 * cm), ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return geral


def _tabela_itens(registro):
    painel = registro.get('modulo') == 'painel'
    corpo = _estilo('item', 6.2, alinhamento=TA_CENTER, entrelinha=7)
    descricao = _estilo('descricao', 6.2, alinhamento=TA_CENTER, entrelinha=7)
    if painel:
        cabecalho = ['IT', 'Ord. de Produção', 'Cód. Produto', 'OC', 'Descrição do Produto', 'Qtde']
        larguras = [0.7, 3.0, 3.0, 2.2, 14.5, 1.6]
    else:
        cabecalho = ['IT', 'OP', 'OC', 'Pedido', 'Código Interno', 'Código NCM', 'Descrição', 'TIPO', 'Qtde', 'CARRETÉIS', 'COD.CLIENTE']
        larguras = [0.7, 2.1, 1.8, 1.9, 3.2, 2.1, 5.1, 1.5, 1.6, 2.0, 2.1]
    linhas = [[Paragraph(f'<b>{c}</b>', corpo) for c in cabecalho]]
    for indice, item in enumerate(registro.get('itens', []), 1):
        if painel:
            valores = [indice, item.get('op'), item.get('codigo_produto'), item.get('oc'), item.get('descricao'), _numero(item.get('qtde'), 0)]
        else:
            valores = [indice, item.get('op'), item.get('oc'), item.get('pedido'), item.get('codigo_produto'), item.get('ncm') or '', item.get('descricao'), item.get('tipo'), _numero(item.get('qtde')), 1, registro.get('cliente_codigo')]
        linhas.append([_par(v, descricao if (painel and i == 4) or (not painel and i == 6) else corpo) for i, v in enumerate(valores)])
    tabela = Table(linhas, colWidths=[x * cm for x in larguras], repeatRows=1, hAlign='CENTER')
    tabela.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, PRETO), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#d9d9d9')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    return tabela


def _rodape():
    estilo = _estilo('rodape', 5.5, alinhamento=TA_CENTER)
    topo = Table([[Paragraph('<b>APONTAMENTO</b>', estilo), Paragraph('<b>DATA</b>', estilo)]], colWidths=[12.5 * cm, 12.5 * cm], rowHeights=[0.55 * cm])
    dados = [
        ['ELABORADO/REVISADO', 'EMITIDO', 'APROVADO', 'REVISADO - DATA', 'ENDEREÇO ELETRÔNICO'],
        ['WASHINGTON FELIX - PCP', 'PCP', 'WAGNER', '00 - 08.11.24', ''],
    ]
    tabela = Table([[Paragraph(f'<b>{x}</b>', estilo) for x in dados[0]], [Paragraph(x, estilo) for x in dados[1]]], colWidths=[3.4 * cm, 3.1 * cm, 3.1 * cm, 3.5 * cm, 11.9 * cm], rowHeights=[0.35 * cm, 0.35 * cm])
    tabela.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, PRETO), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    return KeepTogether([topo, tabela])


def gerar_pdf_etiqueta(registro: dict) -> str:
    """Gera o packing list industrial, com layout próprio para cada módulo."""
    nome_arquivo = f"{registro.get('cliente_abrev') or 'SEMCLIENTE'}-{registro['numero']}-{registro['data_hora'][:10]}-{registro.get('modulo', '')}.pdf"
    nome_arquivo = nome_arquivo.replace('/', '-').replace('\\', '-')
    caminho = os.path.join(pdf_dir(), nome_arquivo)
    if os.path.exists(caminho):
        base, extensao = os.path.splitext(nome_arquivo)
        nome_arquivo = f"{base}-{uuid4().hex[:6]}{extensao}"
        caminho = os.path.join(pdf_dir(), nome_arquivo)
    doc = SimpleDocTemplate(caminho, pagesize=landscape(A4), topMargin=0.9 * cm, bottomMargin=0.8 * cm, leftMargin=1.0 * cm, rightMargin=1.0 * cm)
    doc.build([
        _cabecalho(registro), Spacer(1, 0.35 * cm), _dados_superiores(registro),
        Spacer(1, 0.35 * cm), _tabela_itens(registro), Spacer(1, 0.45 * cm), _rodape(),
    ])
    return caminho
