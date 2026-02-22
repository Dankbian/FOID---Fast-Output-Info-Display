import psutil
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.progress import BarColumn, Progress, TextColumn
from rich.text import Text
from rich.columns import Columns
from rich import box

console = Console()
WATCH_DIR = os.path.expanduser("~")
HISTORIAL_MAX = 40  # puntos de historial para sparklines

# Cachés y estado
cwd_cache = {}
historial_cpu = deque(maxlen=HISTORIAL_MAX)
historial_ram = deque(maxlen=HISTORIAL_MAX)
historial_net_sent = deque(maxlen=HISTORIAL_MAX)
historial_net_recv = deque(maxlen=HISTORIAL_MAX)

# Para calcular velocidad de red (delta)
_net_prev = None
_net_prev_time = None


# ─────────────────────────────────────────────
# SPARKLINE
# ─────────────────────────────────────────────

SPARK_CHARS = "▁▂▃▄▅▆▇█"

def sparkline(valores, ancho=20, vmin=0, vmax=100):
    if not valores:
        return " " * ancho
    datos = list(valores)[-ancho:]
    rango = vmax - vmin or 1
    chars = []
    for v in datos:
        idx = int((v - vmin) / rango * (len(SPARK_CHARS) - 1))
        idx = max(0, min(idx, len(SPARK_CHARS) - 1))
        chars.append(SPARK_CHARS[idx])
    # Rellenar con espacio si hay menos datos que ancho
    return " " * (ancho - len(chars)) + "".join(chars)


# ─────────────────────────────────────────────
# DATOS DEL SISTEMA
# ─────────────────────────────────────────────

def get_cpu_ram():
    cpu_percents = psutil.cpu_percent(percpu=True)
    cpu_total = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    swap = psutil.swap_memory()
    historial_cpu.append(cpu_total)
    historial_ram.append(ram.percent)
    return cpu_percents, cpu_total, ram, swap


def get_top_processes(n=8):
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
        try:
            procs.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x['cpu_percent'], reverse=True)
    return procs[:n]


def get_recent_files(path, n=6):
    entries = []
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    entries.append((entry.path, entry.stat().st_mtime))
            except (PermissionError, OSError):
                continue
    except PermissionError:
        pass
    entries.sort(key=lambda x: x[1], reverse=True)
    return entries[:n]


def get_network_speed():
    global _net_prev, _net_prev_time
    now = time.time()
    counters = psutil.net_io_counters()
    if _net_prev is None:
        _net_prev = counters
        _net_prev_time = now
        return 0.0, 0.0

    elapsed = now - _net_prev_time or 1
    sent_ps = (counters.bytes_sent - _net_prev.bytes_sent) / elapsed
    recv_ps = (counters.bytes_recv - _net_prev.bytes_recv) / elapsed

    _net_prev = counters
    _net_prev_time = now

    historial_net_sent.append(sent_ps / 1024)  # KB/s
    historial_net_recv.append(recv_ps / 1024)
    return sent_ps, recv_ps


def get_network_connections():
    try:
        conns = psutil.net_connections(kind='inet')
        active = [c for c in conns if c.status == 'ESTABLISHED' and c.raddr]
        return active[:8]
    except psutil.AccessDenied:
        return []


def get_temperatures():
    try:
        temps = psutil.sensors_temperatures()
        result = {}
        for name, entries in temps.items():
            for entry in entries:
                label = entry.label or name
                result[f"{name}/{label}"] = entry.current
        return result
    except (AttributeError, Exception):
        return {}


def get_disk_io():
    try:
        io = psutil.disk_io_counters()
        return io
    except Exception:
        return None


def get_heavy_dirs(n=5):
    dir_usage = defaultdict(lambda: {'cpu': 0.0, 'mem': 0.0})
    current_pids = set()
    for proc in psutil.process_iter(['pid', 'cpu_percent', 'memory_percent']):
        try:
            pid = proc.pid
            current_pids.add(pid)
            cwd = cwd_cache[pid] if pid in cwd_cache else proc.cwd()
            cwd_cache[pid] = cwd
            dir_usage[cwd]['cpu'] += proc.info['cpu_percent']
            dir_usage[cwd]['mem'] += proc.info['memory_percent']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    for pid in set(cwd_cache.keys()) - current_pids:
        del cwd_cache[pid]
    return sorted(dir_usage.items(), key=lambda x: x[1]['cpu'], reverse=True)[:n]


# ─────────────────────────────────────────────
# HELPERS DE COLOR
# ─────────────────────────────────────────────

def color_pct(val):
    try:
        f = float(val)
        c = "red" if f > 80 else "yellow" if f > 50 else "green"
        return f"[{c}]{val}[/{c}]"
    except (ValueError, TypeError):
        return str(val)


def color_temp(val):
    try:
        f = float(val)
        c = "red" if f > 80 else "yellow" if f > 60 else "cyan"
        return f"[{c}]{f:.0f}°C[/{c}]"
    except (ValueError, TypeError):
        return str(val)


def fmt_bytes(b):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024:
            return f"{b:.1f} {unit}/s"
        b /= 1024
    return f"{b:.1f} PB/s"


# ─────────────────────────────────────────────
# PANELES
# ─────────────────────────────────────────────

def panel_header():
    hostname = os.uname().nodename
    os_info = f"{os.uname().sysname} {os.uname().release}"
    uptime_s = time.time() - psutil.boot_time()
    uptime_str = str(timedelta(seconds=int(uptime_s)))
    load1, load5, load15 = os.getloadavg()
    ahora = datetime.now().strftime("%A %d/%m/%Y  %H:%M:%S")

    t = Table.grid(expand=True)
    t.add_column(justify="left")
    t.add_column(justify="center")
    t.add_column(justify="right")
    t.add_row(
        f"[bold cyan]🖥  {hostname}[/bold cyan]  [dim]{os_info}[/dim]",
        f"[bold white]{ahora}[/bold white]",
        f"[dim]Carga: [/dim][yellow]{load1:.2f}  {load5:.2f}  {load15:.2f}[/yellow]  "
        f"[dim]Activo: [/dim][green]{uptime_str}[/green]",
    )
    return Panel(
        t,
        title="[bold bright_cyan] FOID [/bold bright_cyan][dim] - Fast Output Info Display[/dim]",
        border_style="bright_blue",
        box=box.HEAVY,
    )


def panel_cpu(cpu_percents, cpu_total):
    progress = Progress(
        TextColumn("[cyan]{task.description}[/cyan]", justify="right"),
        BarColumn(bar_width=22, complete_style="green", finished_style="red"),
        TextColumn("{task.percentage:>5.1f}%"),
        expand=False,
    )
    for i, pct in enumerate(cpu_percents):
        t = progress.add_task(f"Core {i:>2}", total=100)
        progress.update(t, completed=pct)

    spark = sparkline(historial_cpu)
    color_spark = "green" if cpu_total < 50 else "yellow" if cpu_total < 80 else "red"
    footer = Text(f"  Total: {cpu_total:.1f}%   historial: [{color_spark}]{spark}[/{color_spark}]", style="dim")

    from rich.console import Group
    contenido = Group(progress, footer)
    return Panel(contenido, title="[bold] CPU[/bold]", border_style="cyan")


def panel_ram(ram, swap):
    progress = Progress(
        TextColumn("[cyan]{task.description}[/cyan]", justify="right"),
        BarColumn(bar_width=28, complete_style="magenta", finished_style="red"),
        TextColumn("{task.percentage:>5.1f}%"),
        expand=False,
    )
    t_ram = progress.add_task("RAM  ", total=100)
    progress.update(t_ram, completed=ram.percent)
    t_swap = progress.add_task("Swap ", total=100)
    progress.update(t_swap, completed=swap.percent)

    spark = sparkline(historial_ram)
    color_spark = "green" if ram.percent < 50 else "yellow" if ram.percent < 80 else "red"

    detalles = (
        f"  Usada: [bold]{ram.used/1e9:.2f} GB[/bold] / {ram.total/1e9:.2f} GB"
        f"   Swap: [bold]{swap.used/1e9:.2f} GB[/bold] / {swap.total/1e9:.2f} GB\n"
        f"  Historial RAM: [{color_spark}]{spark}[/{color_spark}]"
    )

    from rich.console import Group
    contenido = Group(progress, Text.from_markup(detalles, style="dim"))
    return Panel(contenido, title="[bold] Memoria[/bold]", border_style="magenta")


def panel_procesos(procs):
    table = Table(show_header=True, header_style="bold yellow", box=box.SIMPLE_HEAVY, expand=True)
    table.add_column("PID", style="dim", width=7)
    table.add_column("Nombre", min_width=14)
    table.add_column("CPU %", justify="right", width=7)
    table.add_column("MEM %", justify="right", width=7)
    table.add_column("Estado", width=10)

    for p in procs:
        estado_color = "green" if p['status'] == 'running' else "dim"
        table.add_row(
            str(p['pid']),
            p['name'][:20],
            color_pct(f"{p['cpu_percent']:.1f}"),
            color_pct(f"{p['memory_percent']:.1f}"),
            f"[{estado_color}]{p['status']}[/{estado_color}]",
        )
    return Panel(table, title="[bold] Procesos mas pesados[/bold]", border_style="yellow")


def panel_red(sent_ps, recv_ps):
    table = Table.grid(expand=True)
    table.add_column(justify="left")
    table.add_column(justify="right")

    spark_r = sparkline(historial_net_recv, vmin=0, vmax=max(historial_net_recv or [1]))
    spark_s = sparkline(historial_net_sent, vmin=0, vmax=max(historial_net_sent or [1]))

    table.add_row(
        f"[green]▼ Descarga[/green]",
        f"[bold green]{fmt_bytes(recv_ps)}[/bold green]  [dim green]{spark_r}[/dim green]",
    )
    table.add_row(
        f"[cyan]▲ Subida[/cyan]  ",
        f"[bold cyan]{fmt_bytes(sent_ps)}[/bold cyan]  [dim cyan]{spark_s}[/dim cyan]",
    )

    conns = get_network_connections()
    if conns:
        table.add_row("", "")
        table.add_row(f"[dim]Conexiones activas: {len(conns)}[/dim]", "")
        for c in conns[:4]:
            table.add_row(
                f"  [dim]{c.laddr.ip}:{c.laddr.port}[/dim]",
                f"[dim]→ {c.raddr.ip}:{c.raddr.port}[/dim]",
            )

    return Panel(table, title="[bold] Red[/bold]", border_style="green")


def panel_temperaturas(temps):
    if not temps:
        return Panel(
            Text("No disponible en este sistema", style="dim italic", justify="center"),
            title="[bold]🌡  Temperatura[/bold]",
            border_style="red",
        )
    table = Table(show_header=False, box=box.SIMPLE, expand=True)
    table.add_column("Sensor")
    table.add_column("Temp", justify="right")
    for nombre, val in list(temps.items())[:10]:
        # Acortar nombre
        corto = nombre.split("/")[-1][:22]
        table.add_row(f"[dim]{corto}[/dim]", color_temp(val))
    return Panel(table, title="[bold]🌡  Temperatura[/bold]", border_style="red")


def panel_disco():
    io = get_disk_io()
    uso = psutil.disk_usage('/')

    progress = Progress(
        TextColumn("[cyan]{task.description}[/cyan]", justify="right"),
        BarColumn(bar_width=28, complete_style="blue", finished_style="red"),
        TextColumn("{task.percentage:>5.1f}%"),
        expand=False,
    )
    t = progress.add_task("Disco /", total=100)
    progress.update(t, completed=uso.percent)

    detalles = (
        f"  Usado: [bold]{uso.used/1e9:.1f} GB[/bold] / {uso.total/1e9:.1f} GB\n"
    )
    if io:
        detalles += (
            f"  Lecturas: [green]{io.read_bytes/1e9:.2f} GB[/green]   "
            f"Escrituras: [yellow]{io.write_bytes/1e9:.2f} GB[/yellow]"
        )

    from rich.console import Group
    contenido = Group(progress, Text.from_markup(detalles, style="dim"))
    return Panel(contenido, title="[bold] Disco[/bold]", border_style="blue")


def panel_archivos_recientes():
    archivos = get_recent_files(WATCH_DIR)
    table = Table(show_header=True, header_style="bold white", box=box.SIMPLE, expand=True)
    table.add_column("Archivo", min_width=16)
    table.add_column("Modificado", justify="right")
    for f, ts in archivos:
        table.add_row(
            os.path.basename(f),
            time.strftime('%d/%m %H:%M:%S', time.localtime(ts)),
        )
    return Panel(table, title="[bold] Archivos Recientes[/bold]", border_style="white")


def panel_directorios(heavy_dirs):
    table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE, expand=True)
    table.add_column("Directorio", min_width=20)
    table.add_column("CPU %", justify="right", width=7)
    table.add_column("MEM %", justify="right", width=7)
    for d, uso in heavy_dirs:
        table.add_row(
            d[:40],
            color_pct(f"{uso['cpu']:.1f}"),
            color_pct(f"{uso['mem']:.1f}"),
        )
    return Panel(table, title="[bold] Dirs usando más CPU[/bold]", border_style="magenta")


# ─────────────────────────────────────────────
# DASHBOARD PRINCIPAL
# ─────────────────────────────────────────────

def build_dashboard():
    cpu_percents, cpu_total, ram, swap = get_cpu_ram()
    top_procs = get_top_processes()
    sent_ps, recv_ps = get_network_speed()
    temps = get_temperatures()
    heavy_dirs = get_heavy_dirs()

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="fila1", size=14),
        Layout(name="fila2", size=12),
        Layout(name="fila3"),
    )

    layout["header"].update(panel_header())

    layout["fila1"].split_row(
        Layout(panel_cpu(cpu_percents, cpu_total), name="cpu"),
        Layout(panel_ram(ram, swap), name="ram"),
        Layout(panel_procesos(top_procs), name="procs"),
    )

    layout["fila2"].split_row(
        Layout(panel_red(sent_ps, recv_ps), name="red"),
        Layout(panel_temperaturas(temps), name="temp"),
        Layout(panel_disco(), name="disco"),
    )

    layout["fila3"].split_row(
        Layout(panel_archivos_recientes(), name="archivos"),
        Layout(panel_directorios(heavy_dirs), name="dirs"),
    )

    return layout


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    console.print("[bold cyan]Iniciando monitor del sistema...[/bold cyan]")
    # Calentamiento para que cpu_percent tenga datos reales desde el primer ciclo
    psutil.cpu_percent(percpu=True)
    get_network_speed()
    time.sleep(0.8)
    console.print("[green] Listo. Cargando dashboard...[/green]")
    time.sleep(0.3)

    with Live(console=console, refresh_per_second=2, screen=True) as live:
        while True:
            try:
                dashboard = build_dashboard()
                live.update(dashboard)
                time.sleep(1)
            except KeyboardInterrupt:
                break

    console.print("\n[bold yellow]FOID cerrada, ¡Adios prro ;v! [/bold yellow]")


if __name__ == "__main__":
    main()
