import os
from datetime import datetime
from uuid import uuid4

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from paths import pdf_dir


def gerar_pdf_relacao_carga(carga, pallets, itens_manuais=None):
    numero = int(carga['numero'])
    nome = f"RELACAO-CARGA-{numero:05d}-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}.pdf"
    caminho = os.path.join(pdf_dir(), nome)
    doc = SimpleDocTemplate(caminho, pagesize=landscape(A4), rightMargin=10*mm,
                            leftMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)
    estilos = getSampleStyleSheet()
    elementos = [Paragraph(f"<b>RELAÇÃO DE CARGA Nº {numero:05d}</b>", estilos['Title']), Spacer(1, 4*mm)]
    data = datetime.fromisoformat(carga['data_hora']).strftime('%d/%m/%Y %H:%M')
    cabecalho = [
        ['Data', data, 'Cliente', carga.get('cliente') or '—'],
        ['Transportadora', carga.get('transportadora') or '—', 'Veículo', carga.get('veiculo') or '—'],
        ['Motorista', carga.get('motorista') or '—', 'Prioridade', carga.get('prioridade') or '—'],
    ]
    tabela_cab = Table(cabecalho, colWidths=[30*mm, 65*mm, 30*mm, 135*mm])
    tabela_cab.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.HexColor('#aab7cc')),
        ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#e9eff8')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#e9eff8')),
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
        ('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('PADDING',(0,0),(-1,-1),5)]))
    elementos += [tabela_cab, Spacer(1, 5*mm)]

    # A operação precisa enxergar a carga pelo produto, e não pallet por pallet.
    # O número do packing permanece somente na coluna de rastreabilidade.
    resumo_codigos = {}
    total_volumes = 0
    total_liquido = 0.0
    total_bruto = 0.0
    for pallet in pallets:
        itens = pallet.get('itens') or []
        volumes = int(pallet.get('carreteis') or 0)
        liquido = float(pallet.get('peso_liquido') or 0)
        bruto = float(pallet.get('peso_bruto') or 0)
        total_volumes += volumes; total_liquido += liquido; total_bruto += bruto
        for item in itens:
            codigo = str(item.get('codigo_produto') or 'SEM CÓDIGO')
            grupo = resumo_codigos.setdefault(codigo, {'descricao': item.get('descricao') or '—', 'qtde': 0.0,
                                                        'ops': set(), 'packings': set()})
            grupo['qtde'] += float(item.get('qtde') or 0)
            if item.get('op'): grupo['ops'].add(str(item['op']))
            grupo['packings'].add(f"{int(pallet['numero']):05d}")

    for item in itens_manuais or []:
        codigo = str(item.get('codigo_produto') or 'SEM CÓDIGO')
        grupo = resumo_codigos.setdefault(codigo, {'descricao': item.get('descricao') or '—', 'qtde': 0.0,
                                                    'ops': set(), 'packings': set()})
        grupo['qtde'] += float(item.get('quantidade') or 0)
        grupo['packings'].add('MANUAL')

    linhas = [['Código', 'Descrição', 'OPs', 'Qtde total', 'Packing lists']]
    for codigo, grupo in sorted(resumo_codigos.items()):
        linhas.append([codigo, Paragraph(str(grupo['descricao']), estilos['BodyText']),
                       ', '.join(sorted(grupo['ops'])) or '—',
                       f"{grupo['qtde']:,.2f}".replace(',', 'X').replace('.', ',').replace('X','.'),
                       ', '.join(sorted(grupo['packings']))])
    linhas.append(['TOTAL DA CARGA', f'{len(resumo_codigos)} código(s)', '',
                   f"{total_liquido:,.2f}".replace(',', 'X').replace('.', ',').replace('X','.'),
                   f'{len(pallets)} pallet(s) / {total_volumes} volume(s)'])
    tabela = Table(linhas, repeatRows=1, colWidths=[35*mm, 105*mm, 48*mm, 32*mm, 55*mm])
    tabela.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.HexColor('#b8c4d6')),
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#173b7a')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#e9eff8')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ALIGN',(0,1),(0,-1),'CENTER'),('ALIGN',(3,1),(3,-1),'RIGHT'),('FONTSIZE',(0,0),(-1,-1),8),
        ('PADDING',(0,0),(-1,-1),4)]))
    elementos += [Paragraph('<b>RESUMO POR CÓDIGO</b>', estilos['Heading2']), tabela,
                  Spacer(1, 3*mm), Paragraph(
                      f"Peso líquido: <b>{total_liquido:,.2f} kg</b> &nbsp;&nbsp; Peso bruto: <b>{total_bruto:,.2f} kg</b>".replace(',', 'X').replace('.', ',').replace('X','.'),
                      estilos['BodyText'])]
    if carga.get('observacao'):
        elementos += [Spacer(1, 4*mm), Paragraph(f"<b>Observações:</b> {carga['observacao']}", estilos['BodyText'])]
    doc.build(elementos)
    return caminho
