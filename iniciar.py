"""
iniciar.py

Ponto de entrada recomendado (em vez de rodar server.py direto). Ele existe
só para uma coisa: se der QUALQUER erro (biblioteca faltando, config.json
errado, porta ocupada, driver ODBC ausente, etc.), a janela do terminal
mostra o erro e espera você apertar ENTER antes de fechar - em vez de
"piscar e sumir", que é o que acontece quando um .py com erro é aberto com
duplo clique no Windows.
"""
import sys
import traceback


def main():
    try:
        import server
        server.executar()
    except KeyboardInterrupt:
        print("\nSistema encerrado.")
    except Exception:
        print("\n" + "=" * 70)
        print("O SISTEMA NÃO CONSEGUIU INICIAR. Detalhes do erro abaixo:")
        print("=" * 70)
        traceback.print_exc()
        print("=" * 70)
        print("Causas mais comuns:")
        print("  - Faltam bibliotecas: rode  pip install -r requirements.txt")
        print("  - Python não é a versão certa / não está no PATH")
        print("  - config.json com erro de formatação (falta vírgula, aspas, etc.)")
        print("  - Porta já em uso por outro programa (mude 'porta_do_sistema' no config.json)")
    finally:
        input("\nPressione ENTER para fechar esta janela...")


if __name__ == '__main__':
    main()
