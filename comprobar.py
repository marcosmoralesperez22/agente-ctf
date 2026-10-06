#!/usr/bin/env python3
"""
COMPROBADOR DE SETUP. Ejecútalo el día del reto antes de nada:

    python comprobar.py

Te dice si tienes todo listo (dependencias, clave de API, herramientas de
sistema) y qué falta, sin gastar ni un token de la API.
"""

import importlib
import os
import shutil
import subprocess
import sys

# La consola de Windows usa cp1252 y peta con emojis: forzamos UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

OK = "✅"
NO = "❌"
AV = "⚠️ "


def check(cond, texto_ok, texto_no, critico=False):
    print(f"  {OK if cond else (NO if critico else AV)} {texto_ok if cond else texto_no}")
    return cond


def main():
    print("\n=== COMPROBACIÓN DEL AGENTE CTF ===\n")
    criticos_ok = True

    # Python
    print("Python:")
    v = sys.version_info
    criticos_ok &= check(v >= (3, 9), f"Python {v.major}.{v.minor} OK",
                         f"Python {v.major}.{v.minor} (se recomienda 3.9+)", critico=True)

    # Dependencias de Python
    print("\nLibrerías de Python:")
    for mod, critico in [("anthropic", True), ("Crypto", False), ("requests", False)]:
        try:
            importlib.import_module(mod)
            check(True, f"{mod} instalado", "", critico)
        except ImportError:
            criticos_ok &= check(False, "", f"{mod} NO instalado  ->  pip install -r requirements.txt", critico)

    # Clave de API
    print("\nClave de API:")
    criticos_ok &= check(
        bool(os.getenv("ANTHROPIC_API_KEY")),
        "ANTHROPIC_API_KEY detectada",
        'ANTHROPIC_API_KEY NO está  ->  $env:ANTHROPIC_API_KEY = "tu-clave"',
        critico=True,
    )

    # Herramientas de sistema (no críticas, pero útiles según categoría)
    print("\nHerramientas de sistema (útiles, no obligatorias):")
    for tool in ["curl", "strings", "file", "xxd", "objdump", "binwalk", "nmap", "openssl"]:
        check(shutil.which(tool) is not None, f"{tool} disponible", f"{tool} no encontrado (opcional)")

    # Config
    print("\nConfiguración:")
    try:
        import config
        check(bool(config.PATRONES_FLAG), f"{len(config.PATRONES_FLAG)} patrones de flag cargados", "")
        print(f"     Modelo por defecto: {config.MODELO_POR_DEFECTO}")
        print(f"     Primer patrón de flag: {config.PATRONES_FLAG[0]}")
        print(f"     {AV}Recuerda poner el formato REAL de flag el primero en config.py")
    except Exception as e:  # noqa: BLE001
        criticos_ok &= check(False, "", f"Error al cargar config.py: {e}", critico=True)

    print("\n" + "=" * 45)
    if criticos_ok:
        print(f"{OK} TODO LISTO. Puedes lanzar el agente.")
        print('   Prueba:  python agente.py "Descifra ROT13: synt{cehron}"')
    else:
        print(f"{NO} Falta algo crítico (arriba en rojo). Arréglalo antes de competir.")
    print("=" * 45 + "\n")


if __name__ == "__main__":
    main()
