#!/usr/bin/env python3
"""
LANZADOR EN PARALELO: ataca muchos retos a la vez.

En una competición de 1 hora con 30+ retos, esto es clave: cada reto lo resuelve
un agente independiente, y varios corren en paralelo. Tú solo miras el marcador.

Dos formas de darle los retos:

1) Un JSON (recomendado). Crea un archivo retos.json así:
   [
     {"nombre": "cripto1", "enunciado": "Descifra: Uryyb", "rapido": true},
     {"nombre": "web1", "enunciado": "SQLi en el login", "url": "http://IP/login"},
     {"nombre": "rev1", "enunciado": "Flag en el binario", "file": "./bin/reto1"}
   ]
   Y lanza:  python lanzador.py retos.json

2) Una carpeta de .txt (rápido de montar): cada archivo es un reto, el nombre
   del archivo es el nombre del reto y su contenido es el enunciado.
   Lanza:  python lanzador.py ./mis_retos/

Opciones:
   --paralelo N   cuántos retos a la vez (por defecto 4)
   --rapido       fuerza el modelo rápido en todos
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# La consola de Windows usa cp1252 y peta con emojis: forzamos UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import config
from agente import resolver


def cargar_retos(ruta):
    retos = []
    if os.path.isdir(ruta):
        for nombre in sorted(os.listdir(ruta)):
            if nombre.lower().endswith((".txt", ".md")):
                with open(os.path.join(ruta, nombre), encoding="utf-8") as f:
                    retos.append({"nombre": os.path.splitext(nombre)[0], "enunciado": f.read().strip()})
    elif ruta.lower().endswith(".json"):
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if not isinstance(datos, list):
            print("El JSON debe ser una LISTA de retos."); sys.exit(1)
        retos = datos
    else:
        print("Pásame un archivo .json o una carpeta con .txt"); sys.exit(1)

    if not retos:
        print("No encontré retos en esa ruta."); sys.exit(1)
    return retos


def resolver_uno(reto, forzar_rapido):
    nombre = reto.get("nombre", "reto")
    modelo = config.MODELO_RAPIDO if (forzar_rapido or reto.get("rapido")) else config.MODELO_POR_DEFECTO
    try:
        flag = resolver(
            enunciado=reto["enunciado"],
            archivo=reto.get("file"),
            url=reto.get("url"),
            modelo=modelo,
            nombre_reto=nombre,
            silencioso=True,   # en paralelo, cada agente escribe en su log
        )
        return nombre, flag
    except Exception as e:  # noqa: BLE001
        return nombre, f"[ERROR: {e}]"


def main():
    p = argparse.ArgumentParser(description="Lanzador paralelo de retos CTF")
    p.add_argument("ruta", help="retos.json o carpeta con .txt")
    p.add_argument("--paralelo", type=int, default=4, help="retos simultáneos (def. 4)")
    p.add_argument("--rapido", action="store_true", help="modelo rápido en todos")
    args = p.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print('⚠️  Falta ANTHROPIC_API_KEY.  $env:ANTHROPIC_API_KEY = "tu-clave"')
        sys.exit(1)

    retos = cargar_retos(args.ruta)
    print(f"🚀 Lanzando {len(retos)} retos, {args.paralelo} a la vez. Logs en ./logs/\n")

    resultados = {}
    with ThreadPoolExecutor(max_workers=args.paralelo) as pool:
        futuros = {pool.submit(resolver_uno, r, args.rapido): r.get("nombre", "reto") for r in retos}
        for fut in as_completed(futuros):
            nombre, flag = fut.result()
            resultados[nombre] = flag
            estado = f"✅ {flag}" if flag and not str(flag).startswith("[") else f"❌ {flag or 'sin flag'}"
            print(f"  [{len(resultados)}/{len(retos)}] {nombre:20s} {estado}")

    # Resumen final
    logradas = {n: f for n, f in resultados.items() if f and not str(f).startswith("[")}
    print("\n" + "=" * 55)
    print(f"RESUMEN: {len(logradas)}/{len(retos)} flags conseguidas")
    print("=" * 55)
    for nombre, flag in sorted(logradas.items()):
        print(f"  {nombre:20s} -> {flag}")

    with open("resultados.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print("\n📄 Guardado en resultados.json")


if __name__ == "__main__":
    main()
