import os
import re
import unicodedata
from datetime import datetime
from uuid import uuid4

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from paths import base_dir, pdf_dir


def _numero(valor):
    return f"{float(valor or 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def _tipo_material(item, pallet):
    def normalizar(valor):
        return ''.join(c for c in unicodedata.normalize('NFD', str(valor or '').upper())
                       if not unicodedata.combining(c)).strip()

    tipo = normalizar(item.get('tipo'))
    fios = {'PMC': 'FIO PMC', 'PKT': 'FIO PKT', 'NU': 'FIO NÚ',
            'FIO PMC': 'FIO PMC', 'FIO PKT': 'FIO PKT', 'FIO NU': 'FIO NÚ'}
    if tipo in fios:
        return fios[tipo]
    if tipo and tipo not in ('FIO', 'PAINEL/KIT'):
        return tipo
    descricao = normalizar(item.get('descricao'))
    palavras = set(re.findall(r'[A-Z]+', descricao))
    for nome in ('PAINEL', 'KIT', 'TERMINAL', 'PRESILHA', 'GANCHO'):
        if nome in palavras:
            return nome
    if 'FIO' in palavras or pallet.get('modulo') == 'fios':
        for nome in ('PMC', 'PKT', 'NU'):
            if nome in palavras:
                return fios[nome]
        return 'FIO'
    return tipo or 'NÃO INFORMADO'


def gerar_pdf_romaneio(registro, pallets):
    """Gera o documento consolidado usado na expedição da carga."""
    numero = int(registro['numero'])
    # O sufixo evita tentar sobrescrever um PDF que esteja aberto no Windows
    # depois de uma tentativa anterior interrompida.
    nome = f"ROMANEIO-{numero:05d}-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}.pdf"
    caminho = os.path.join(pdf_dir(), nome)
    doc = SimpleDocTemplate(caminho, pagesize=landscape(A4), leftMargin=1 * cm,
                            rightMargin=1 * cm, topMargin=1 * cm, bottomMargin=1 * cm)
    estilos = getSampleStyleSheet()
    azul = colors.HexColor('#0b3b67')
    azul_claro = colors.HexColor('#d9eaf7')
    cinza = colors.HexColor('#edf1f4')
    borda = colors.HexColor('#22313f')
    pequeno = ParagraphStyle('Pequeno', parent=estilos['Normal'], fontSize=7.2, leading=8.5)
    data_envio = datetime.strptime(registro.get('data_envio') or registro['data_hora'][:10], '%Y-%m-%d')
    codigo_romaneio = f"{numero:04d}-{data_envio:%d%m%y}"
    logo_path = os.path.join(base_dir(), 'public', 'assets', 'logo-amt.png')
    logo = Image(logo_path, width=4.2*cm, height=1*cm) if os.path.isfile(logo_path) else Paragraph('<b>AMT</b>', estilos['Title'])
    titulo = Paragraph('<b>ROMANEIO DE EXPEDIÇÃO</b><br/><font size="8">AMT PRODUTOS ELÉTRICOS</font>',
                       ParagraphStyle('TituloRom', parent=estilos['Normal'], fontSize=15, leading=17,
                                      alignment=1, textColor=azul))
    numero_box = Paragraph(f'<b>ROMANEIO Nº</b><br/><font size="14">{codigo_romaneio}</font>',
                           ParagraphStyle('NumeroRom', parent=estilos['Normal'], alignment=1, leading=16))
    cab = Table([[logo, titulo, numero_box]], colWidths=[5.3*cm, 14.3*cm, 7*cm], rowHeights=[1.6*cm])
    cab.setStyle(TableStyle([('BOX',(0,0),(-1,-1),1,borda),('INNERGRID',(0,0),(-1,-1),.7,borda),
                             ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER'),
                             ('BACKGROUND',(2,0),(2,0),azul_claro)]))
    relacao = f"{int(registro.get('carga_numero') or 0):05d}" if registro.get('carga_numero') else '-'
    aderencia = f"{float(registro.get('aderencia_carga') or 0):.1f}%"
    info = [
        ['CLIENTE', registro.get('cliente_nome') or '-', 'DATA DE ENVIO', f'{data_envio:%d/%m/%Y}'],
        ['TRANSPORTADORA', registro.get('transportadora') or '-', 'FRETE', registro.get('frete') or '-'],
        ['MOTORISTA', registro.get('motorista') or '-', 'VEÍCULO / PLACA', registro.get('veiculo') or '-'],
        ['RELAÇÃO DE CARGA', relacao, 'ADERÊNCIA À RELAÇÃO', aderencia],
    ]
    info_table = Table(info, colWidths=[3.7*cm, 10.8*cm, 4.2*cm, 7.9*cm], rowHeights=[.72*cm]*4)
    info_table.setStyle(TableStyle([('BOX',(0,0),(-1,-1),1,borda),('INNERGRID',(0,0),(-1,-1),.5,borda),
        ('BACKGROUND',(0,0),(0,-1),cinza),('BACKGROUND',(2,0),(2,-1),cinza),
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
        ('FONTNAME',(3,3),(3,3),'Helvetica-Bold'),('TEXTCOLOR',(3,3),(3,3),azul),
        ('FONTSIZE',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),5)]))
    elementos = [cab, Spacer(1, .22*cm), info_table, Spacer(1, .35*cm),
                 Paragraph('<b>DETALHAMENTO DA CARGA</b>', ParagraphStyle('Secao', parent=estilos['Normal'], fontSize=9, textColor=azul)),
                 Spacer(1, .12*cm)]
    dados = [['Packing', Paragraph('<font color="white"><b>Tipo do material</b></font>', pequeno), 'Código', 'Descrição', 'OP', 'OC', 'NCM', 'Qtde', 'Peso líq.', 'Peso bruto']]
    for pallet in pallets:
        itens = pallet.get('itens') or []
        for indice, item in enumerate(itens):
            dados.append([
                f"{int(pallet['numero']):05d}" if indice == 0 else '',
                Paragraph(_tipo_material(item, pallet), pequeno),
                item.get('codigo_produto') or '-', Paragraph(str(item.get('descricao') or '-'), pequeno),
                item.get('op') or '-', item.get('oc') or '-', item.get('ncm') or '-',
                _numero(item.get('qtde')), _numero(item.get('qtde')),
                _numero(item.get('peso_bruto_linha') or item.get('qtde')),
            ])
    dados.append(['', 'TOTAIS', '', '', '', '', '', str(sum(p.get('carreteis') or 0 for p in pallets)),
                  _numero(registro.get('peso_liquido')), _numero(registro.get('peso_bruto'))])
    tabela = Table(dados, colWidths=[1.7*cm, 1.8*cm, 2.2*cm, 6.6*cm, 2.3*cm, 2.2*cm, 2.1*cm, 1.7*cm, 2.2*cm, 2.2*cm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), azul),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#eaf2ff')),
        ('GRID', (0, 0), (-1, -1), .45, borda), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 8), ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    obs = Table([[Paragraph(f"<b>OBSERVAÇÕES:</b> {registro.get('observacao') or '-'}", pequeno)]], colWidths=[26.6*cm])
    obs.setStyle(TableStyle([('BOX',(0,0),(-1,-1),.7,borda),('BACKGROUND',(0,0),(-1,-1),cinza),('PADDING',(0,0),(-1,-1),6)]))
    elementos.extend([tabela, Spacer(1, .25 * cm), obs])

    def iniciar_resumo(titulo_secao):
        totais = Table([['PESO BRUTO TOTAL', f"{_numero(registro.get('peso_bruto'))} kg",
                         'QUANTIDADE DE VOLUMES', str(sum(len(p.get('itens') or []) for p in pallets))]],
                       colWidths=[4.2*cm, 6.6*cm, 6*cm, 9.8*cm])
        totais.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), .5, borda),
            ('BACKGROUND', (0, 0), (-1, -1), azul_claro),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elementos.extend([PageBreak(), cab, Spacer(1, .22*cm), info_table,
                          Spacer(1, .22*cm), totais, Spacer(1, .35*cm),
                          Paragraph(f'<b>{titulo_secao}</b>', ParagraphStyle(
                              'TituloResumo', parent=estilos['Normal'], fontSize=9,
                              textColor=azul, keepWithNext=True)), Spacer(1, .12*cm)])

    resumo = {}
    for pallet in pallets:
        for item in pallet.get('itens') or []:
            codigo = str(item.get('codigo_produto') or 'SEM CÓDIGO')
            grupo = resumo.setdefault(codigo, {'descricao': item.get('descricao') or '-', 'qtde': 0.0,
                                                'peso_bruto': 0.0, 'volumes': 0, 'tipos': set()})
            grupo['qtde'] += float(item.get('qtde') or 0)
            grupo['peso_bruto'] += float(item.get('peso_bruto_linha') or item.get('qtde') or 0)
            grupo['volumes'] += 1
            grupo['tipos'].add(_tipo_material(item, pallet))
    resumo_dados = [['Código', 'Descrição', 'Tipo do material', 'Quantidade total', 'Peso líquido (kg)', 'Peso bruto (kg)', 'Volume']]
    for codigo, grupo in sorted(resumo.items()):
        resumo_dados.append([codigo, Paragraph(str(grupo['descricao']), pequeno), Paragraph(', '.join(sorted(grupo['tipos'])), pequeno),
                             _numero(grupo['qtde']), _numero(grupo['qtde']),
                             _numero(grupo['peso_bruto']), str(grupo['volumes'])])
    resumo_dados.append(['TOTAL', f'{len(resumo)} código(s)', '', _numero(sum(g['qtde'] for g in resumo.values())),
                         _numero(sum(g['qtde'] for g in resumo.values())),
                         _numero(sum(g['peso_bruto'] for g in resumo.values())),
                         str(sum(g['volumes'] for g in resumo.values()))])
    resumo_tabela = Table(resumo_dados, colWidths=[2.2*cm, 8.1*cm, 3.3*cm, 3.4*cm, 3.5*cm, 3.5*cm, 2.6*cm], repeatRows=1)
    resumo_tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), azul),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#eaf2ff')),
        ('GRID', (0, 0), (-1, -1), .45, borda), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'), ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    iniciar_resumo('RESUMO POR CÓDIGO')
    elementos.append(resumo_tabela)

    resumo_pedidos = {}
    for pallet in pallets:
        for item in pallet.get('itens') or []:
            pedido = str(item.get('pedido') or 'SEM PEDIDO').strip()
            codigo = str(item.get('codigo_produto') or 'SEM CÓDIGO')
            grupo = resumo_pedidos.setdefault((pedido, codigo), {'qtde': 0.0, 'peso_bruto': 0.0, 'volumes': 0, 'tipos': set()})
            grupo['qtde'] += float(item.get('qtde') or 0)
            grupo['peso_bruto'] += float(item.get('peso_bruto_linha') or item.get('qtde') or 0)
            grupo['volumes'] += 1
            grupo['tipos'].add(_tipo_material(item, pallet))
    pedido_dados = [['Pedido de venda', 'Código', 'Tipo do material', 'Quantidade total', 'Peso líquido (kg)', 'Peso bruto (kg)', 'Volume']]
    for (pedido, codigo), grupo in sorted(resumo_pedidos.items()):
        pedido_dados.append([pedido, codigo, Paragraph(', '.join(sorted(grupo['tipos'])), pequeno), _numero(grupo['qtde']), _numero(grupo['qtde']),
                             _numero(grupo['peso_bruto']), str(grupo['volumes'])])
    total_pedidos = len({pedido for pedido, codigo in resumo_pedidos})
    pedido_dados.append(['TOTAL', f'{total_pedidos} pedido(s)', '',
                         _numero(sum(g['qtde'] for g in resumo_pedidos.values())), _numero(sum(g['qtde'] for g in resumo_pedidos.values())),
                         _numero(sum(g['peso_bruto'] for g in resumo_pedidos.values())),
                         str(sum(g['volumes'] for g in resumo_pedidos.values()))])
    pedido_tabela = Table(pedido_dados, colWidths=[4.2*cm, 6.1*cm, 3.3*cm, 3.4*cm, 3.5*cm, 3.5*cm, 2.6*cm], repeatRows=1)
    pedido_tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), azul), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#eaf2ff')),
        ('GRID', (0, 0), (-1, -1), .45, borda), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'), ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    iniciar_resumo('RESUMO POR PEDIDO DE VENDA')
    elementos.append(pedido_tabela)

    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setStrokeColor(azul); canvas.line(1*cm, .72*cm, 28.7*cm, .72*cm)
        canvas.setFont('Helvetica', 7); canvas.setFillColor(colors.HexColor('#536273'))
        canvas.drawString(1*cm, .42*cm, 'Documento gerado pelo Portal Logística - AMT Produtos Elétricos')
        canvas.drawRightString(28.7*cm, .42*cm, f'Página {documento.page}')
        canvas.restoreState()

    doc.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    return caminho
