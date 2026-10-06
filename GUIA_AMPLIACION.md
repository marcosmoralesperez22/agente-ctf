# 🛠️ Guía para ampliar, mejorar y seguir el agente CTF

Esta guía es para ti (y tus compañeros) para entender el proyecto, mejorarlo y
tenerlo cada vez más fuerte. Está pensada para que puedas seguir tú solo, pero
cualquier duda la vemos juntos.

> Recomendación: lee primero `README.md` (cómo usarlo) y luego esto (cómo mejorarlo).

---

## 1. Cómo está montado (el mapa mental)

El agente es un **bucle muy simple** que se repite hasta encontrar la flag:

```
   enunciado del reto
          │
          ▼
   ┌──────────────┐     pide usar una herramienta
   │   MODELO IA  │ ─────────────────────────────┐
   │ (razona)     │ ◀──── resultado del comando ──┘
   └──────────────┘
          │  cuando ve la flag
          ▼
    enviar_flag()  →  fin
```

Las piezas (y qué toca cada una):

| Archivo | Qué hace | Cuándo lo tocas |
|---|---|---|
| `config.py` | Modelo, formato de flag, límites y **el prompt** | Casi siempre: aquí se afina el "cerebro". |
| `agente.py` | El bucle y las **herramientas** (shell, python, http) | Cuando quieras darle una capacidad nueva. |
| `lanzador.py` | Correr muchos retos en paralelo | Cuando cambies cómo recibís los retos. |
| `comprobar.py` | Chequeo de setup | Rara vez. |

**Regla de oro:** el 80% de las mejoras se hacen en `config.py` (el prompt). Solo
bajas a `agente.py` cuando necesitas una herramienta nueva.

---

## 2. Las 3 palancas de mejora (de más fácil a más técnica)

### Palanca A — El prompt (`config.py`, `SYSTEM_PROMPT`)  ⭐ la más rentable
Es donde el agente "aprende" a pensar. Mejóralo así:
- **Añade técnicas concretas** por categoría. Cuanto más específico, mejor.
  Ej: en CRIPTO, añadir "si ves un n enorme y e=65537, prueba factordb.com".
- **Añade ejemplos de flags falsas vs reales** para que no se invente.
- **Dale orden de prioridad**: "primero prueba lo rápido (strings, base64), luego
  lo caro (fuerza bruta)".
- Después de cada práctica, mira en qué se atascó (ver sección 6) y **añade esa
  lección al prompt**. Así el agente mejora reto a reto.

### Palanca B — Herramientas nuevas (`agente.py`)
Dale capacidades nuevas. Receta para añadir una herramienta (3 pasos):

1. **Decláralas** en la lista `HERRAMIENTAS` (lo que el modelo "ve"):
```python
{
    "name": "buscar_en_google",
    "description": "Busca algo en internet y devuelve resultados de texto.",
    "input_schema": {
        "type": "object",
        "properties": {"consulta": {"type": "string"}},
        "required": ["consulta"],
    },
},
```
2. **Impleméntala** (una función normal de Python):
```python
def buscar_en_google(consulta: str) -> str:
    # ...tu código...
    return "resultados"
```
3. **Conéctala** en el diccionario `DISPATCH`:
```python
"buscar_en_google": lambda i: buscar_en_google(i["consulta"]),
```
Ya está. El agente la usará solo cuando le convenga.

**Ideas de herramientas útiles para CTF:**
- `factorizar(n)` → usa `sympy.factorint` para RSA con módulos pequeños.
- `fuerza_bruta_hash(hash)` → prueba un diccionario de contraseñas típicas.
- `consultar_factordb(n)` → API de factordb.com para RSA.
- `decodificar_todo(texto)` → prueba base64/32/hex/rot13 en cadena y devuelve lo legible.
- `enviar_flag_al_servidor(flag)` → ⭐ ver sección 4.

### Palanca C — Modelo y parámetros (`config.py`)
- **`MODELO_POTENTE` vs `MODELO_RAPIDO`**: usa el rápido para fáciles (más flags
  por minuto y menos gasto), el potente para los duros.
- **`MAX_ITERACIONES`**: súbelo si los retos difíciles necesitan más pasos; bájalo
  para no "perder tiempo" en retos imposibles.
- **`TIMEOUT_COMANDO`**: súbelo si hay fuerza bruta larga.

---

## 3. Mejoras concretas recomendadas (por orden de impacto)

1. **Autoenvío de la flag al servidor del CTF** (sección 4). Lo que más tiempo
   ahorra en competición: que el agente no solo encuentre la flag, sino que la
   suba solo.
2. **Más paralelismo inteligente**: en `lanzador.py`, probar `--paralelo 6-8`.
   Ojo con los límites de tu plan de API (rate limits).
3. **Herramienta `decodificar_todo`**: resuelve sola la mitad de los retos de
   encoding sin gastar pasos del modelo.
4. **Reintento con modelo potente**: si el modelo rápido falla un reto, relanzarlo
   automáticamente con el potente. (Fácil de añadir en `lanzador.py`.)
5. **Caché de lo que funciona**: guardar qué técnica resolvió cada tipo de reto
   para reusarla.

---

## 4. ⭐ Autoenvío de flags (la mejora estrella)

En muchos CTF las flags se suben a un servidor por una API/web. Si os dan ese
endpoint, añade una herramienta para que el agente lo haga solo:

```python
# en HERRAMIENTAS
{
    "name": "subir_flag",
    "description": "Sube la flag al servidor del CTF y dice si es correcta.",
    "input_schema": {
        "type": "object",
        "properties": {
            "id_reto": {"type": "string"},
            "flag": {"type": "string"},
        },
        "required": ["id_reto", "flag"],
    },
},

# implementación (ajusta la URL y el formato cuando lo sepáis)
import requests
def subir_flag(id_reto: str, flag: str) -> str:
    r = requests.post(
        "https://SERVIDOR_DEL_CTF/api/submit",
        json={"challenge": id_reto, "flag": flag},
        headers={"Authorization": "Bearer VUESTRO_TOKEN"},
        timeout=15,
    )
    return r.text

# en DISPATCH
"subir_flag": lambda i: subir_flag(i["id_reto"], i["flag"]),
```
Y en el prompt añade: *"Cuando encuentres la flag, súbela con `subir_flag` usando
el id del reto; si el servidor dice que es incorrecta, sigue intentándolo."*

⚠️ **Hasta no tener el formato real del servidor, esto es una plantilla.** No lo
actives a ciegas. Lo rellenamos juntos cuando os den las reglas.

---

## 5. Soporte para otro proveedor (OpenAI, local, etc.)

Si el jueves os obligan a usar OpenAI u otro modelo, solo cambia **la llamada a
la API**. El resto (herramientas, prompt, lanzador, logs) es idéntico.

La parte a cambiar está en `agente.py`, función `_llamar_api` y el cliente
`Anthropic()`. El patrón de OpenAI es equivalente (tienen "tools"/"function
calling" con la misma idea: el modelo pide una herramienta, tú la ejecutas y le
devuelves el resultado).

**Esto lo montamos juntos en 10 minutos** cuando sepáis qué proveedor es, porque
el formato exacto depende de la librería. Dímelo y te dejo un `agente_openai.py`
listo.

---

## 6. Cómo depurar: los logs son tu amigo

Cada reto genera un log en `logs/` con TODO el razonamiento y cada comando.
Cuando un reto falle:

1. Abre su log en `logs/`.
2. Mira **dónde se atascó**: ¿probó algo absurdo? ¿se quedó en bucle? ¿le faltó
   una herramienta?
3. Según el caso:
   - Se atasca razonando mal → **mejora el prompt** (Palanca A).
   - Le falta una capacidad → **añade herramienta** (Palanca B).
   - Se queda corto de pasos → sube `MAX_ITERACIONES`.
   - Se inventa flags → refuerza en el prompt "no inventes, solo lo que veas".

Esto es un ciclo: **falla → lee el log → mejora → vuelve a probar.** Cada vuelta
el agente es mejor.

---

## 7. Práctica recomendada antes del jueves

- [ ] Conseguir la clave de API y `python comprobar.py` en verde.
- [ ] Resolver los 7 retos de práctica (`python lanzador.py retos.json`).
- [ ] Leer un log entero para entender cómo "piensa" el agente.
- [ ] Añadir 2-3 técnicas nuevas al prompt y volver a probar.
- [ ] (Opcional) Añadir la herramienta `decodificar_todo`.
- [ ] (Si os dan las reglas) Configurar el autoenvío de flags.
- [ ] Buscar retos reales de práctica para probarlo de verdad (ver sección 8).

---

## 8. Dónde practicar con retos CTF reales (gratis)

Para probar el agente con retos de verdad estos días:
- **picoCTF** (picoctf.org) — retos con dificultad progresiva, ideal para empezar.
- **OverTheWire** (overthewire.org) — retos clásicos por niveles.
- **CryptoHack** (cryptohack.org) — solo cripto, perfecto para afinar esa parte.
- **Writeups de CTFs pasados** — busca "CTF writeup" + categoría para ver técnicas.

Coge un reto de picoCTF, pégale el enunciado al agente y mira si lo saca. Si no,
lee el log y mejora el prompt.

---

## 9. Límites honestos (qué NO espera milagros)

- **Retos de pwn/exploiting binario**: necesitan Linux y suelen ser los más duros
  para un agente. No cuentes con sacarlos todos.
- **Retos que requieren intuición visual** (estego en imágenes, por ejemplo) son
  difíciles si el agente no "ve" la imagen. Se puede mejorar con modelos con visión.
- **Rate limits de la API**: con mucho paralelismo puedes chocar con límites.
  Si pasa, baja `--paralelo` o mete esperas.
- El agente **ejecuta comandos reales**: perfecto para el CTF, pero no lo apuntéis
  a nada fuera de la competición.

---

## 10. Checklist mental para seguir mejorándolo

> ¿Falló un reto? → lee el log → ¿fue el prompt o una herramienta que falta? → arréglalo.
> ¿Va lento? → ¿modelo rápido para fáciles? ¿más paralelo?
> ¿Encuentra la flag pero no la sube? → autoenvío (sección 4).
> ¿Cada vez más retos? → añade sus técnicas al prompt.

Mejorar este agente es, literalmente, la competición. Cada mejora que le hagas
estos días es puntuación el jueves. 🚀

---

*Dudas, lo que sea: lo vemos mañana. Está todo probado y funcionando; a partir de
aquí es afinar.*
