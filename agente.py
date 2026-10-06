#!/usr/bin/env python3
"""
Agente autónomo para CTF (Capture The Flag).

Recibe el enunciado de un reto (y opcionalmente un archivo o una URL),
razona con un LLM, ejecuta herramientas (shell, python, http) en bucle
y devuelve la flag cuando la encuentra. Sin intervención humana.

Uso:
    python agente.py "Descifra este mensaje: Uryyb Jbeyq"
    python agente.py "Encuentra la flag en el binario" --file reto.bin
    python agente.py "Hay una SQLi en el login" --url http://10.0.0.5/login
    python agente.py "reto rápido" --rapido      # usa el modelo rápido/barato

Requiere la variable de entorno ANTHROPIC_API_KEY.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime

# La consola de Windows usa cp1252 y peta con emojis: forzamos UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from anthropic import Anthropic, APIError, APIStatusError

import config


# -------------------------------------------------------------------------
# HERRAMIENTAS que el modelo puede invocar
# -------------------------------------------------------------------------
HERRAMIENTAS = [
    {
        "name": "ejecutar_shell",
        "description": "Ejecuta un comando de shell y devuelve stdout+stderr. "
                       "Para file, strings, curl, xxd, objdump, binwalk, nmap, etc.",
        "input_schema": {
            "type": "object",
            "properties": {"comando": {"type": "string", "description": "El comando a ejecutar"}},
            "required": ["comando"],
        },
    },
    {
        "name": "ejecutar_python",
        "description": "Ejecuta código Python3 y devuelve lo que imprima (print). "
                       "Para cripto (pycryptodome), decodificaciones, fuerza bruta, etc. "
                       "Acuérdate de imprimir el resultado con print().",
        "input_schema": {
            "type": "object",
            "properties": {"codigo": {"type": "string", "description": "Código Python a ejecutar"}},
            "required": ["codigo"],
        },
    },
    {
        "name": "descargar",
        "description": "Petición HTTP (por defecto GET) a una URL. Devuelve headers y cuerpo. "
                       "Puedes pasar metodo, datos (POST) y cabeceras.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "metodo": {"type": "string", "description": "GET, POST, etc. Por defecto GET"},
                "datos": {"type": "string", "description": "Cuerpo para POST, ej. 'user=admin&pass=x'"},
                "cabeceras": {"type": "string", "description": "Cabecera extra, ej. 'Cookie: sesion=abc'"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "enviar_flag",
        "description": "Llama a esto EN CUANTO encuentres la flag. Termina el reto.",
        "input_schema": {
            "type": "object",
            "properties": {"flag": {"type": "string", "description": "La flag, p.ej. UPM{...}"}},
            "required": ["flag"],
        },
    },
]


# -------------------------------------------------------------------------
# IMPLEMENTACIÓN DE HERRAMIENTAS
# -------------------------------------------------------------------------
def _recortar(texto: str) -> str:
    if len(texto) > config.LIMITE_SALIDA:
        return texto[:config.LIMITE_SALIDA] + \
            f"\n...[salida recortada, {len(texto)} caracteres en total]"
    return texto


def ejecutar_shell(comando: str) -> str:
    try:
        r = subprocess.run(
            comando, shell=True, capture_output=True, text=True,
            timeout=config.TIMEOUT_COMANDO, errors="replace",
        )
        return _recortar((r.stdout or "") + (r.stderr or "")) or "[sin salida]"
    except subprocess.TimeoutExpired:
        return f"[el comando superó {config.TIMEOUT_COMANDO}s y se canceló]"
    except Exception as e:  # noqa: BLE001
        return f"[error ejecutando el comando: {e}]"


def ejecutar_python(codigo: str) -> str:
    ruta = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(codigo)
            ruta = f.name
        r = subprocess.run(
            [sys.executable, ruta], capture_output=True, text=True,
            timeout=config.TIMEOUT_COMANDO, errors="replace",
        )
        return _recortar((r.stdout or "") + (r.stderr or "")) or "[sin salida]"
    except subprocess.TimeoutExpired:
        return f"[el script superó {config.TIMEOUT_COMANDO}s y se canceló]"
    except Exception as e:  # noqa: BLE001
        return f"[error ejecutando python: {e}]"
    finally:
        if ruta and os.path.exists(ruta):
            try:
                os.unlink(ruta)
            except OSError:
                pass


def descargar(url: str, metodo: str = "GET", datos: str = "", cabeceras: str = "") -> str:
    partes = ["curl", "-sS", "-L", "-i", "--max-time", "30", "-X", (metodo or "GET").upper()]
    if datos:
        partes += ["-d", datos]
    if cabeceras:
        partes += ["-H", cabeceras]
    partes.append(url)
    return ejecutar_shell(subprocess.list2cmdline(partes))


def buscar_flag(texto: str):
    for patron in config.PATRONES_FLAG:
        m = re.search(patron, texto)
        if m:
            return m.group(0)
    return None


DISPATCH = {
    "ejecutar_shell": lambda i: ejecutar_shell(i["comando"]),
    "ejecutar_python": lambda i: ejecutar_python(i["codigo"]),
    "descargar": lambda i: descargar(
        i["url"], i.get("metodo", "GET"), i.get("datos", ""), i.get("cabeceras", "")
    ),
}


# -------------------------------------------------------------------------
# LLAMADA A LA API CON REINTENTOS
# -------------------------------------------------------------------------
def _llamar_api(cliente, modelo, messages):
    for intento in range(1, config.MAX_REINTENTOS_API + 1):
        try:
            return cliente.messages.create(
                model=modelo,
                max_tokens=config.MAX_TOKENS_RESP,
                system=config.SYSTEM_PROMPT,
                tools=HERRAMIENTAS,
                messages=messages,
            )
        except (APIStatusError, APIError) as e:
            espera = 2 ** intento
            print(f"   ⏳ Error de API ({e}). Reintento {intento}/{config.MAX_REINTENTOS_API} en {espera}s...")
            time.sleep(espera)
    raise RuntimeError("La API falló tras varios reintentos.")


# -------------------------------------------------------------------------
# BUCLE PRINCIPAL DEL AGENTE
# -------------------------------------------------------------------------
def resolver(enunciado, archivo=None, url=None, modelo=None, nombre_reto="reto", silencioso=False):
    modelo = modelo or config.MODELO_POR_DEFECTO
    cliente = Anthropic()  # lee ANTHROPIC_API_KEY del entorno

    # Log por reto
    os.makedirs("logs", exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join("logs", f"{nombre_reto}_{stamp}.log")
    log = open(log_path, "w", encoding="utf-8")

    def out(txt):
        if not silencioso:
            print(txt)
        log.write(txt + "\n")
        log.flush()

    out(f"=== RETO: {nombre_reto} | modelo: {modelo} ===")
    contexto = [f"ENUNCIADO DEL RETO:\n{enunciado}"]
    if archivo:
        contexto.append(f"\nArchivo local disponible en la ruta: {archivo}")
    if url:
        contexto.append(f"\nServicio/URL relevante: {url}")
    messages = [{"role": "user", "content": "\n".join(contexto)}]

    flag_final = None
    try:
        for paso in range(1, config.MAX_ITERACIONES + 1):
            resp = _llamar_api(cliente, modelo, messages)

            for bloque in resp.content:
                if bloque.type == "text" and bloque.text.strip():
                    out(f"\n[paso {paso}] 🤖 {bloque.text.strip()}")

            messages.append({"role": "assistant", "content": resp.content})
            usos = [b for b in resp.content if b.type == "tool_use"]

            if not usos:
                out("\n[fin] El agente no pidió más herramientas y no envió flag.")
                break

            resultados = []
            for uso in usos:
                if uso.name == "enviar_flag":
                    flag_final = uso.input["flag"]
                    out(f"\n✅ FLAG ENCONTRADA: {flag_final}")
                    return flag_final

                out(f"   🔧 {uso.name}({uso.input})")
                try:
                    salida = DISPATCH[uso.name](uso.input)
                except Exception as e:  # noqa: BLE001
                    salida = f"[error: {e}]"

                encontrada = buscar_flag(salida)
                if encontrada:
                    salida = f"⚠️ POSIBLE FLAG DETECTADA EN LA SALIDA: {encontrada}\n\n{salida}"

                out(f"   ↳ {salida[:400]}{'...' if len(salida) > 400 else ''}")
                resultados.append({
                    "type": "tool_result", "tool_use_id": uso.id, "content": salida,
                })

            messages.append({"role": "user", "content": resultados})
        else:
            out(f"\n[fin] Máximo de {config.MAX_ITERACIONES} pasos alcanzado sin flag.")
    finally:
        log.write(f"\n=== RESULTADO: {flag_final or 'SIN FLAG'} ===\n")
        log.close()

    return flag_final


def main():
    p = argparse.ArgumentParser(description="Agente autónomo para CTF")
    p.add_argument("enunciado", help="El texto del reto")
    p.add_argument("--file", help="Ruta a un archivo del reto")
    p.add_argument("--url", help="URL/servicio del reto")
    p.add_argument("--rapido", action="store_true", help="Usa el modelo rápido/barato")
    p.add_argument("--nombre", default="reto", help="Nombre para el archivo de log")
    args = p.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  Falta la variable ANTHROPIC_API_KEY. Ponla con:")
        print('     $env:ANTHROPIC_API_KEY = "tu-clave"     (PowerShell)')
        sys.exit(1)

    modelo = config.MODELO_RAPIDO if args.rapido else config.MODELO_POR_DEFECTO
    flag = resolver(args.enunciado, args.file, args.url, modelo, args.nombre)
    print("\n" + "=" * 50)
    print(f"RESULTADO: {flag if flag else 'No se encontró flag'}")
    print("=" * 50)


if __name__ == "__main__":
    main()
