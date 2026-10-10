#!/usr/bin/env python3
"""Agente CTF con ORQUESTADOR de modelos.
Observa el reto, elige el mejor modelo permitido, y entra en bucle:
observar -> decidir -> ejecutar -> comprobar. Entrega la flag solo.
La plataforma proporciona el objetivo, el modelo y las credenciales al ejecutar.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import requests

CH = json.loads(pathlib.Path("/workspace/challenge.json").read_text())
CID = CH.get("challenge_id") or CH.get("id") or "unknown"
TARGET = os.environ.get("TARGET_URL", "")
GATEWAY = os.environ.get("LLM_GATEWAY_URL", "").rstrip("/")
TOKEN = os.environ.get("LLM_API_KEY") or pathlib.Path("/workspace/keys/llm_token.txt").read_text().strip()
MAX_STEPS = max(1, int(os.environ.get("AGENT_MAX_STEPS", "8")))

# ---------------------------------------------------------------------------
# FORMATO DE LA FLAG
# Si en tu CTF la flag NO empieza por "CTF" (p. ej. es "UPM{...}" o "flag{...}"),
# cambia SOLO la palabra CTF de la línea de abajo por la que sea. Nada más.
# ---------------------------------------------------------------------------
FLAG_RE = re.compile(r"CTF\{[^}\r\n]+\}")

# ---------------------------------------------------------------------------
# ORQUESTADOR DE MODELOS
# Modelos permitidos en esta arena (el primero es el más potente).
# Si tu CTF permite otros, cámbialos aquí.
# ---------------------------------------------------------------------------
MODELO_POTENTE = "helmcode/glm5.3"          # máxima capacidad de razonamiento
MODELO_RAPIDO = "helmcode/glm5.3-flash"     # rápido y barato para retos fáciles
MODELO_CODIGO = "helmcode/deepseek-v4-flash"  # alternativa rápida
ALLOWED_MODELS = [MODELO_POTENTE, MODELO_RAPIDO, MODELO_CODIGO]

# Texto completo del reto en minúsculas: sirve para detectar categoría y dificultad
# aunque no sepamos los nombres exactos de los campos del challenge.json.
BLOB = json.dumps(CH, ensure_ascii=False).lower()


def categoria():
    """Adivina la categoría del reto a partir de su texto (título, descripción, tags)."""
    if any(k in BLOB for k in ("rsa", "xor", "vigenere", "vigenère", "caesar", "cesar",
                               "cipher", "crypt", "cripto", "aes", "number-theory", "hash")):
        return "cripto"
    if any(k in BLOB for k in ("forensic", "forense", "fat12", "fat ", "disk-image",
                               "disk image", "pcap", "dangling", "object-database", ".git")):
        return "forense"
    if any(k in BLOB for k in ("reversing", "rev-", "ingenieria inversa", "ingeniería inversa",
                               "binary", "binario", "disassemb", "strings analysis")):
        return "reversing"
    if any(k in BLOB for k in ("sqli", "idor", "injection", "command-injection", "hpp",
                               "verb", "header", "robots", "web", "api", "http", "endpoint")):
        return "web"
    return "general"


def es_facil():
    return any(k in BLOB for k in ("easy", "facil", "fácil", "trivial"))


def pick_model():
    """EL ORQUESTADOR: elige el mejor modelo permitido para este reto."""
    cat = categoria()
    # Cripto, forense y reversing necesitan razonar mucho -> el más potente.
    if cat in ("cripto", "forense", "reversing"):
        return MODELO_POTENTE
    # Web/general fácil -> modelo rápido (más veloz y barato, sobra para resolverlo).
    if cat in ("web", "general") and es_facil():
        return MODELO_RAPIDO
    # El resto -> el más potente por defecto.
    return MODELO_POTENTE


# El modelo elegido por el orquestador (se puede cambiar solo si uno falla).
MODEL = pick_model()
# Modelos de reserva por si el elegido no está disponible (plan B automático).
FALLBACKS = [m for m in ALLOWED_MODELS if m != MODEL]


def pista_de_categoria():
    """Una frase de arranque para que el modelo vaya directo al grano."""
    cat = categoria()
    pistas = {
        "cripto": "PISTA: parece CRIPTOGRAFIA. Identifica el cifrado (Cesar/ROT, Vigenere, XOR, RSA) y rómpelo con python3.",
        "forense": "PISTA: parece FORENSE. Descarga/abre el fichero y recupera los datos ocultos o borrados con python3 o git.",
        "reversing": "PISTA: parece REVERSING. Extrae cadenas del binario con python3 y reproduce la lógica de validación.",
        "web": "PISTA: parece WEB/API. Empieza con 'curl -sS -i' al objetivo y prueba verb tampering, cabeceras de confianza, IDOR, HPP, SQLi o command injection segun responda.",
    }
    return pistas.get(cat, "")


INSTRUCTIONS = (
    "Eres un agente experto en CTF que compite de forma 100% autónoma contra el objetivo autorizado indicado. "
    "Tu ÚNICO objetivo es encontrar la flag (formato CTF{...}) y hacer que aparezca en la salida de una herramienta; el programa la envía solo. "
    "Lee SIEMPRE primero los 'Datos del reto (JSON)' y la descripción: ahí están las pistas, el endpoint y, si el reto es de ficheros, la ruta o URL del material. "
    "METODO: 1) OBSERVA (curl -sS -i al objetivo para ver cabeceras, cuerpo, cookies y redirecciones; o inspecciona el fichero con python3). "
    "2) Di en una frase qué tipo de reto es. 3) Ejecuta UN comando concreto. 4) Lee el resultado y ajusta; si en 2 intentos un enfoque no avanza, cambia de técnica. No repitas el mismo comando. "
    "=== WEB / API (la mayoría de los retos de esta arena) === "
    "HTTP Verb Tampering: si GET da 403 en un endpoint de admin, prueba otros métodos con curl -X: POST, PUT, DELETE, PATCH, HEAD, OPTIONS; el control de acceso suele cubrir solo GET. "
    "Header Trust / spoofing: añade cabeceras de confianza interna: -H 'X-Forwarded-For: 127.0.0.1' , -H 'X-Internal: true' , -H 'X-Real-IP: 127.0.0.1' , -H 'X-Forwarded-Host: localhost'. "
    "IDOR / Broken Access: si eres el usuario 1, enumera /api/user/2, /api/user/3... cambia el id en la ruta o en un parámetro para leer datos de otros usuarios. "
    "HTTP Parameter Pollution: duplica el parámetro, p.ej. role=user&role=admin; a veces se muestra el PRIMER valor pero se autoriza con el ÚLTIMO (o al revés): prueba ambos órdenes. "
    "Command Injection: en parámetros que ejecutan algo prueba separadores: ; id | $(id) | `id` | && id | %0aid ; si hay RCE, lista y lee ficheros (ls, cat) para sacar la flag. "
    "SQL Injection: en buscadores/parámetros no parametrizados prueba ' OR '1'='1 , UNION SELECT, y errores reveladores; vuelca tablas y columnas hasta la flag. "
    "Enumeración: revisa /robots.txt, comentarios del HTML, /sitemap.xml y rutas ocultas. La flag puede NO estar en /flag: sigue las pistas del HTML y robots.txt. "
    "Revisa también /.git/ (si existe, descarga objetos), /admin, las cookies y los JWT (decodifica en base64 las 3 partes y prueba alg=none o una clave débil). "
    "Con curl usa -b/-c para cookies, -d para POST, -H para cabeceras y -L para seguir redirecciones. "
    "=== DISEÑO INSEGURO / TOKENS / JWT / PLANTILLAS === "
    "Tokens predecibles (password-reset): pide un token de recuperación para un usuario que controlas y observa su formato y longitud; deduce cómo se deriva (md5/sha1/sha256 del usuario, usuario+timestamp, base64, o un contador) y calcula offline en python3 el token del admin para resetear su contraseña o acceder. "
    "JWT con secreto débil (HS256): extrae el token, intenta crackear el secreto con fuerza bruta/diccionario en python3 (prueba 'secret','admin','123456','password' y claves cortas); con el secreto, forja un token poniendo admin/role=admin y re-fírmalo. "
    "Second-order SQLi: el dato malicioso se guarda al registrarte y se usa sin sanear en una consulta POSTERIOR; registra un usuario cuyo nombre sea un payload SQL y luego dispara la acción que lo reutiliza. "
    "SSTI / Template Injection: en campos que se reflejan prueba {{7*7}} y ${7*7}; si devuelve 49 identifica el motor de plantillas y escala a lectura de ficheros o RCE para sacar la flag. "
    "=== CRIPTOGRAFIA === "
    "Cesar/ROT: prueba los 25 desplazamientos y busca texto legible. Vigenere: si tienes los ficheros, crackéalo localmente (longitud de clave por Kasiski/índice de coincidencia y análisis de frecuencia). "
    "XOR Key Reuse: si reutilizan la clave, el XOR de dos cifrados cancela la clave; o fuerza una clave corta y analiza con python3 (crib-dragging, frecuencia). "
    "RSA Small Primes: n es pequeño, factorízalo con python3 (sympy.factorint o fuerza bruta), calcula d = inverse(e, (p-1)*(q-1)) y descifra. Usa pycryptodome (from Crypto.Util.number import inverse, long_to_bytes) si está. "
    "=== FORENSE === "
    "Imagen de disco FAT12 con fichero borrado: parsea la imagen con python3, localiza la entrada de directorio borrada (primer byte 0xE5), lee su primer clúster y su tamaño, y reconstruye los datos del fichero. "
    "Git dangling / objetos: en un repo .git usa 'git fsck --lost-found', 'git cat-file -p <hash>' y revisa .git/objects para recuperar ficheros que ya no están referenciados. "
    "Para ficheros: descárgalos con curl si hay URL, o léelos con python3 (open(ruta,'rb').read()). Extrae cadenas imprimibles: re.findall(rb'[ -~]{4,}', data). "
    "=== REVERSING === "
    "Extrae las cadenas imprimibles del binario con python3; muchas veces la flag o una pista está ahí. Busca constantes y reproduce en python3 la lógica de validación. "
    "=== REGLAS DE ORO === "
    "No inventes flags; entrega solo lo que veas REALMENTE en una salida. Un texto cifrado o codificado todavía NO es la flag: decodifícalo primero. "
    "Sé conciso: una sola acción por paso. El programa enviará automáticamente el primer CTF{...} que aparezca en la salida de una herramienta."
)

JSON_FORMAT = 'Responde solo con un objeto JSON: {"command": "un comando de shell"}.'
REPAIR_FORMAT = "Corrige el formato anterior: responde únicamente con un bloque de código bash que contenga un comando o script de shell. No uses JSON ni añadas explicación."

class ModelError(RuntimeError):
    """El proveedor o el formato de la decisión impiden continuar."""
    def __init__(self, mensaje, status=None):
        super().__init__(mensaje)
        self.status = status

class DecisionError(ModelError):
    """Respuesta textual que necesita corregir su formato antes de ejecutar."""

def ask(prompt, repair=False):
    """Una decisión del modelo. Nunca pongas aquí una clave de proveedor."""
    try:
        response = requests.post(GATEWAY + "/v1/chat/completions",
            headers={"Authorization": "Bearer " + TOKEN},
            json={"model": MODEL, "messages": [
                {"role": "system", "content": INSTRUCTIONS + " " + (REPAIR_FORMAT if repair else JSON_FORMAT)},
                {"role": "user", "content": prompt}], "max_tokens": 2048},
            timeout=(10, 90))
    except requests.RequestException as error:
        raise ModelError("No se pudo contactar con el modelo. Revisa el estado del gateway.") from error
    if response.status_code != 200:
        hints = {401: "La autorización ha caducado o el CTF ha terminado.",
                 403: "El modelo no está permitido en este CTF.",
                 429: "Se ha alcanzado el presupuesto o el límite de peticiones.",
                 502: "El proveedor no pudo completar la petición. Consulta Estado de modelos.",
                 503: "El modelo o su contabilidad no están disponibles; prueba más tarde."}
        raise ModelError("Modelo: HTTP %s. %s" % (
            response.status_code, hints.get(response.status_code, "Consulta el estado de la ejecución.")),
            status=response.status_code)
    try:
        answer = response.json()["choices"][0]["message"]["content"]
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 16384:
            raise ValueError("respuesta vacía, no textual o demasiado larga")
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise ModelError("El proveedor devolvió una respuesta vacía o incompleta.") from error
    # Un bloque con datos o una explicación no es una acción. Se elige una
    # sola decisión válida; los demás bloques nunca se ejecutan.
    fence = chr(96) * 3
    blocks = re.findall(r"^[ \t]*" + fence + r"([\w-]*)[ \t]*\r?\n(.*?)^[ \t]*" + fence + r"[ \t]*$",
                        answer, re.MULTILINE | re.DOTALL)
    candidates = [(kind.lower(), text.strip()) for kind, text in blocks
                  if kind.lower() in ("json", "bash", "sh", "shell", "")]
    if not candidates:
        candidates = [("json", answer.strip())]
    for kind, text in candidates:
        if kind in ("bash", "sh", "shell") and text:
            return text
        try:
            decision = json.loads(text)
        except ValueError:
            continue
        if not isinstance(decision, dict):
            continue
        command = decision.get("command")
        if isinstance(command, str) and command.strip():
            return command.strip()
        flag = decision.get("flag")
        if isinstance(flag, str) and flag.strip():
            return "SUBMIT:" + flag.strip()
    raise DecisionError("El modelo no devolvió una decisión con formato válido.")

def run(command):
    """Ejecuta una herramienta y limita tiempo y salida para el siguiente paso."""
    print("$ " + command, flush=True)
    try:
        result = subprocess.run(command, shell=True, capture_output=True,
                                text=True, errors="replace", timeout=30)
        output = (result.stdout + result.stderr)[-4000:]
        print(output, flush=True)
        return "Salida (código %s):\n%s" % (result.returncode, output)
    except subprocess.TimeoutExpired:
        return "La herramienta superó 30 segundos. Prueba un comando más corto o con timeout."

def submit(flag):
    """Envía la evidencia; la plataforma comprueba si el flag es correcto."""
    path = pathlib.Path("/workspace/flags/found.txt")
    path.parent.mkdir(exist_ok=True)
    path.write_text("FLAG:%s:%s\n" % (CID, flag))
    print("Flag enviado para validación.", flush=True)

def main():
    global MODEL, FALLBACKS
    if not TARGET or not GATEWAY:
        raise RuntimeError("Falta el objetivo o el gateway. Lanza esta versión desde Jugar.")
    print("Orquestador: reto '%s' -> categoria '%s' -> modelo %s" % (
        CH.get("title", CID), categoria(), MODEL), flush=True)
    context = "Reto: %s\nDescripción: %s\nObjetivo autorizado: %s\n" % (
        CH.get("title", CID), CH.get("description", ""), TARGET)
    pista = pista_de_categoria()
    if pista:
        context += pista + "\n"
    # Volcamos todo el challenge.json (recortado) para que el modelo vea pistas,
    # rutas de ficheros, URLs de material y cualquier otro dato del reto.
    try:
        context += "Datos del reto (JSON): %s\n" % json.dumps(CH, ensure_ascii=False)[:2000]
    except Exception:  # noqa: BLE001
        pass
    tools = [name for name in ("curl", "python3", "git", "jq", "nmap", "openssl", "base64", "tr", "grep", "sed", "awk", "xxd") if shutil.which(name)]
    context += "Herramientas disponibles: %s. Usa python3 para scripts de Python.\n" % ", ".join(tools)
    history = ""
    previous_command = ""
    format_errors = 0
    for step in range(MAX_STEPS):
        print("Paso %s/%s · %s" % (step + 1, MAX_STEPS, MODEL), flush=True)
        try:
            plan = ask(context + history[-16000:] + "\nQuedan %s decisiones. Devuelve una sola acción.\n" % (MAX_STEPS - step), repair=bool(format_errors))
        except DecisionError as error:
            format_errors += 1
            if format_errors >= 2 or step + 1 >= MAX_STEPS:
                print(str(error) + " No se ejecutó esa respuesta.", flush=True)
                raise SystemExit(78) from None
            history += "\nLa última decisión no era válida y no se ejecutó. Corrige el formato con un único bloque bash.\n"
            print("Respuesta sin ejecutar: solicitando una corrección de formato.", flush=True)
            continue
        except ModelError as error:
            # Plan B del orquestador: si el modelo elegido no está disponible,
            # cambiamos automáticamente a otro modelo permitido y reintentamos.
            if error.status in (403, 404, 502, 503) and FALLBACKS:
                anterior, MODEL = MODEL, FALLBACKS.pop(0)
                print("Modelo %s no disponible (%s). Cambio a %s." % (anterior, error.status, MODEL), flush=True)
                continue
            print(str(error), flush=True)
            raise SystemExit(78) from None
        format_errors = 0
        if plan.startswith("SUBMIT:"):
            flag = FLAG_RE.search(plan)
            if flag and flag.group(0) in history:
                submit(flag.group(0))
                return
            history += "\nNo hay evidencia de ese flag. Obtén el valor real con una herramienta; devuelve un comando.\n"
            continue
        command = plan.strip()
        if not command:
            history += "\nLa última respuesta no contenía un comando. Devuelve un comando válido.\n"
            continue
        output = run(command)
        history += "\n$ %s\n%s\n" % (command, output)
        if command == previous_command:
            history += "\nHas repetido el mismo comando. No has encontrado un flag CTF{...}. Analiza la salida o sigue una pista distinta.\n"
        previous_command = command
        flag = FLAG_RE.search(output)
        if flag:
            submit(flag.group(0))
            return
    print("Fin del límite de pasos. Revisa las pistas, mejora el agente y publica otra versión.", flush=True)

if __name__ == "__main__":
    main()
