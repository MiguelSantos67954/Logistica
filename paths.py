import os
import sys


PDF_OUTPUT_DIR = r"C:\Users\miguel.santos\Documents\pdf_packing_list"


def base_dir() -> str:
    """Diretorio base da aplicacao (funciona rodando .py normal ou empacotado)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def pdf_dir() -> str:
    """Diretorio onde os packing lists gerados sao armazenados.

    A variavel ``PACKING_LIST_PDF_DIR`` permite trocar o destino sem alterar
    o codigo (por exemplo, durante testes ou ao instalar em outro computador).
    """
    caminho = os.environ.get('PACKING_LIST_PDF_DIR', PDF_OUTPUT_DIR)
    caminho = os.path.abspath(os.path.expanduser(caminho))
    os.makedirs(caminho, exist_ok=True)
    return caminho
