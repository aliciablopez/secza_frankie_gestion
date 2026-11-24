"""
===============================================================================
EJECUTOR GENERAL DE PRUEBAS (tests/run_all.py)
===============================================================================
Descubre y ejecuta automáticamente todas las suites `test_*.py` dentro de
la carpeta `tests/` usando `unittest`.
===============================================================================
"""

from pathlib import Path
import sys
import unittest

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_TESTS = Path(__file__).resolve().parent

if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))


def main(verbosity: int = 2) -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(CARPETA_TESTS),
        pattern="test_*.py",
        top_level_dir=str(RAIZ_PROYECTO),
    )
    runner = unittest.TextTestRunner(verbosity=verbosity)
    resultado = runner.run(suite)
    return 0 if resultado.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())