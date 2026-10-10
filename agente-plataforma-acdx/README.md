# 🤖 Agente Orquestador — ACDX Cyberchallenge Arena (UPM)

Agente de IA para la plataforma **ACDX / Autonomous Cyber Defence Challenge** (CTF de la UPM).
A diferencia del agente de la carpeta raíz (que usa la API de Anthropic), **este está pensado
para ejecutarse DENTRO de la plataforma**: la propia arena le da el modelo, el objetivo y las
credenciales en tiempo de ejecución a través de su *gateway*.

## 📁 Archivos

| Archivo | Para qué |
|---|---|
| `main.py` | El agente. Observa el reto → **elige el mejor modelo** → ejecuta herramientas en bucle → entrega la flag. |
| `config.json` | Ajustes: modelo por defecto y nº de pasos. |
| `requirements.txt` | Dependencias (`requests`, `pycryptodome`, `sympy`). |
| `Agente_Orquestador.agent.json` | Los 3 archivos empaquetados, listos para **importar** en *Mis agentes*. |

## 🧠 El orquestador

Nada más empezar, el agente lee el reto (título, descripción, tags), **adivina la categoría**
(cripto / forense / reversing / web) y **elige el modelo permitido más adecuado**:

- **Cripto / Forense / Reversing** → `helmcode/glm5.3` (máxima potencia de razonamiento).
- **Web fácil** → `helmcode/glm5.3-flash` (más rápido y barato).
- **Plan B automático:** si un modelo no está disponible, cambia solo a otro permitido.

Además le da una **pista de arranque** según la categoría para que vaya directo al grano.

## 🎯 Técnicas que conoce

- **Web/API:** HTTP Verb Tampering, Header Trust spoofing, IDOR, HTTP Parameter Pollution,
  Command Injection, SQL Injection, enumeración (robots.txt, /.git/), JWT.
- **Diseño inseguro:** tokens predecibles (password-reset), JWT con secreto débil,
  SQLi de segundo orden, SSTI / Template Injection.
- **Cripto:** César/ROT, Vigenère, XOR (key reuse), RSA (primos pequeños).
- **Forense:** imagen FAT12 con fichero borrado, objetos *dangling* de Git.
- **Reversing:** extracción de cadenas y reproducción de la lógica de validación.

## 🚀 Cómo usarlo en la plataforma

1. En **Mis agentes**, pega el contenido de `main.py`, `config.json` y `requirements.txt`
   en sus pestañas (o importa `Agente_Orquestador.agent.json`).
2. **Comprobar código** → **Guardar borrador** → **Publicar versión**.
3. **Mis CTFs** → **Inscribir equipo** → **Jugar** contra los retos.

> **Nota:** el formato de flag está en `CTF{...}`. Si tu CTF usa otro (p. ej. `UPM{...}`),
> cambia solo la palabra `CTF` de la línea `FLAG_RE` en `main.py`.
