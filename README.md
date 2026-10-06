# 🚩 Agente CTF — listo para competir

Un agente de IA que resuelve retos de CTF de forma **autónoma**: razona, ejecuta
herramientas (shell, Python, HTTP) en bucle, detecta la flag y la entrega. Tú no
tocas nada durante la competición: lo lanzas y mira.

Ya está **probado y funcionando** en este equipo. Solo te falta poner tu clave de API.

---

## ⚡ El día del reto: 3 pasos

**1. Pon tu clave de API** (PowerShell):
```bash
$env:ANTHROPIC_API_KEY = "tu-clave-aqui"
```

**2. Comprueba que todo está listo:**
```bash
python comprobar.py
```
Si sale todo en verde (✅), adelante.

**3. Ataca los retos.** Dos modos:

Reto suelto:
```bash
python agente.py "aquí el enunciado del reto"
python agente.py "flag en el binario" --file reto.bin
python agente.py "SQLi en el login" --url http://IP:PUERTO
```

Muchos retos a la vez (lo potente para 1 hora):
```bash
python lanzador.py retos.json --paralelo 4
```

---

## 📁 Qué hay aquí

| Archivo | Para qué |
|---|---|
| `agente.py` | El agente. Resuelve UN reto. |
| `lanzador.py` | Lanza MUCHOS retos en paralelo. |
| `config.py` | **Todo lo ajustable** (modelo, formato de flag, límites, prompt). |
| `comprobar.py` | Chequeo de setup antes de competir. |
| `retos_prueba/` | 7 retos de práctica (cripto, encoding, reversing). |
| `retos.json` | Ejemplo de lista de retos para el lanzador. |
| `logs/` | Se crea solo: un log detallado por cada reto. |
| `resultados.json` | Se crea solo: resumen de flags del lanzador. |

---

## 🎛️ Qué ajustar cuando os den la info (en `config.py`)

1. **Formato de flag** → `PATRONES_FLAG`. En cuanto sepáis si es `UPM{...}`,
   `flag{...}`, etc., **ponlo el primero de la lista**. Dispara la autodetección.
2. **Modelo** → `MODELO_POTENTE` (razona mejor, retos difíciles) y
   `MODELO_RAPIDO` (más barato y veloz, retos fáciles y a volumen).
3. **Tiempos** → `MAX_ITERACIONES` y `TIMEOUT_COMANDO` según veáis.

> **Si os obligan a otro proveedor (OpenAI, etc.):** avisa y te paso la versión.
> Solo cambia la parte de la llamada a la API; herramientas, prompt y lanzador
> son iguales.

---

## 🧪 Probar estos días (recomendado antes del jueves)

Con la clave puesta:
```bash
# un reto de práctica suelto
python agente.py "$(cat retos_prueba/01_base64.txt)"

# todos los de práctica en paralelo
python lanzador.py retos.json --paralelo 4
```
Deberían salir flags como `flag{base64_sencillo}`, `flag{rot13_funciona}`, etc.
Si alguno falla, me pegas el log de `logs/` y lo afinamos.

---

## 🏆 Estrategia para 1 hora con 30+ retos

- **Paraleliza**: el lanzador ataca varios retos a la vez. Súbelo a `--paralelo 6`
  si tu plan de API lo aguanta.
- **Reparte el equipo**: cada uno supervisa unos retos y relanza los atascados.
- **Fáciles primero**: usa `"rapido": true` en los retos sencillos del JSON
  (más flags por minuto y menos gasto).
- **Mira los logs**: si un agente se atasca, el log te dice por dónde iba y
  puedes reformular el enunciado o darle una pista.

---

## ⚠️ Notas de entorno (Windows)

- Funciona en Windows. El agente usa Python para todo lo que no tenga de sistema.
- `strings`, `binwalk`, `objdump`, `nmap` no están instalados aquí: el agente lo
  sabe y los sustituye por Python automáticamente (ya está en el prompt).
- `pwntools` (retos de *pwn*) no se instaló: da problemas en Windows y esos retos
  suelen necesitar Linux. Si tenéis una máquina Linux/WSL, ahí sí: `pip install pwntools`.
- **Seguridad**: el agente ejecuta comandos reales. En el CTF es el objetivo, pero
  no lo apuntéis a nada fuera de la competición.
