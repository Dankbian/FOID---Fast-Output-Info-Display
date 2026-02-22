# FOID — Fast Output Info Display

> Monitor de sistema en tiempo real para la terminal. Más bonito que `htop`, más información que `btop`.

---

##  Características

- **Barras de progreso animadas** para CPU (core por core), RAM, Swap y Disco
- **Sparklines en tiempo real** — historial visual de los últimos 40 valores: `▁▂▃▄▅▆▇█`
- **Velocidad de red en tiempo real** — KB/s y MB/s calculados por delta entre lecturas
- **Temperatura de sensores** — CPU, GPU y cualquier sensor que exponga el sistema
- **Top de procesos** con CPU%, MEM% y estado, coloreados por carga
- **Conexiones de red activas** con IP local y remota
- **Archivos modificados recientemente** en el directorio home
- **Directorios con mayor uso de CPU** — útil para saber qué carpeta está quemando el procesador
- **Header informativo** — hostname, kernel, fecha/hora, uptime y carga del sistema (1/5/15 min)
- **UI completamente en español**
- Colores adaptativos: 🟢 normal · 🟡 moderado · 🔴 crítico

---

##  Instalación

### Requisitos

- Python 3.8 o superior
- Linux (también funciona en macOS con algunas limitaciones en temperaturas ;v)

### Dependencias

```bash
pip install rich psutil
```

### Clonar y ejecutar

```bash
git clone https://github.com/Dankbian/FOID---Fast-Output-Info-Display.git
cd foid
python foid.py
```

O directamente si solo tienes el archivo:

```bash
python foid.py
```

---

## Uso

```bash
python foid.py
```

Sal del programa con `Ctrl+C`. FOID mostrará un mensaje de despedida y cerrará limpiamente.

---

## 🖥 Paneles del dashboard

| Panel | Descripción |
|---|---|
| **CPU** | Barra por core + sparkline del historial de uso total |
| **Memoria** | RAM y Swap con barras de progreso + historial |
| **Procesos Top** | Los 8 procesos con mayor CPU en ese momento |
| **Red** | Velocidad de descarga/subida en tiempo real con sparklines |
| **Temperatura** | Sensores del sistema (requiere soporte del kernel) |
| **Disco** | Uso del disco raíz `/` + bytes totales leídos/escritos |
| **Archivos Recientes** | Últimos archivos modificados en el home |
| **Dirs con más CPU** | Directorios de trabajo de los procesos más pesados |

---

## ⚙️ Configuración

Al inicio de `monitor.py` puedes ajustar estas variables:

```python
WATCH_DIR = os.path.expanduser("~")  # Directorio para "Archivos Recientes"
HISTORIAL_MAX = 40                   # Puntos del historial para sparklines
```

---

## 🔍 Diferencias con htop / btop

| Característica | htop | btop | **FOID** |
|---|:---:|:---:|:---:|
| Vista por core de CPU | ✅ | ✅ | ✅ |
| Sparklines de historial | ❌ | ✅ | ✅ |
| Velocidad de red en tiempo real | ❌ | ✅ | ✅ |
| Temperatura de sensores | ❌ | ✅ | ✅ |
| Archivos recientes | ❌ | ❌ | ✅ |
| Directorios con más CPU | ❌ | ❌ | ✅ |
| UI en español | ❌ | ❌ | ✅ |
| Sin dependencias nativas (puro Python) | ❌ | ❌ | ✅ |

---

##  Limitaciones conocidas

- Las **temperaturas** solo están disponibles en Linux con los módulos del kernel correspondientes (`lm-sensors`). En macOS no se muestran.
- Las **conexiones de red** requieren permisos de root en algunos sistemas para mostrar todas las conexiones.
- El panel de **directorios** puede mostrar entradas vacías si los procesos no tienen directorio de trabajo accesible.

---

##  Requisitos del sistema

| Componente | Versión mínima |
|---|---|
| Python | 3.8+ |
| rich | 13.0+ |
| psutil | 5.9+ |
| Sistema operativo | Linux / macOS |

---

## Licencia

MIT — úsalo, modifícalo, compártelo.

---

<p align="center"> <b>FOID v1.0</b></p>
