"""Punto de entrada.

    python main.py            # abre el simulador en el navegador (interfaz simple, recomendada)
    python main.py --tk       # interfaz de escritorio completa (Tkinter)
    python main.py --cli scenarios/03_paginacion_tlb_swap.json --compare repl_policy   # consola (ver cli.py)
"""
import sys

if __name__ == "__main__":
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        import cli
        sys.exit(cli.main())
    if "--tk" in sys.argv:
        sys.argv.remove("--tk")
        from gui.app import main
        main(sys.argv[1] if len(sys.argv) > 1 else None)
    else:
        from web.server import main
        main()
