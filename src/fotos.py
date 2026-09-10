from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


def ler_uploads(request):
    fotos = []
    if any(k not in ('pallets', 'carga') for k in request.files):
        raise ValueError('Categoria de foto inválida.')
    for categoria in ('pallets', 'carga'):
        for arquivo in request.files.getlist(categoria):
            dados = arquivo.read(10 * 1024 * 1024 + 1)
            if len(dados) > 10 * 1024 * 1024:
                raise ValueError('Cada foto deve ter no máximo 10 MB.')
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error', Image.DecompressionBombWarning)
                    with Image.open(BytesIO(dados)) as original:
                        if original.format not in ('JPEG', 'PNG', 'WEBP'):
                            raise ValueError('Use fotos JPG, PNG ou WebP.')
                        foto = ImageOps.exif_transpose(original).convert('RGB')
                        foto.thumbnail((2400, 2400))
                        saida = BytesIO()
                        foto.save(saida, format='JPEG', quality=88)
                        fotos.append((categoria, saida.getvalue()))
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                raise ValueError('Foto inválida ou com resolução excessiva.')
    if len(fotos) > 30:
        raise ValueError('Anexe no máximo 30 fotos por envio.')
    return fotos


def salvar_fotos(conn, romaneio_id, fotos):
    conn.executemany('INSERT INTO romaneio_fotos (romaneio_id, categoria, imagem) VALUES (?, ?, ?)',
                     [(romaneio_id, categoria, imagem) for categoria, imagem in fotos])


def fotos_pdf(conn, romaneio_id):
    return [dict(r) for r in conn.execute(
        'SELECT categoria, imagem FROM romaneio_fotos WHERE romaneio_id=? ORDER BY id', (romaneio_id,))]
