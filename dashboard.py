import psutil
import argparse
import platform
import os
import time
from datetime import datetime, timedelta
import io
import sys
import json
import csv


"""SECTION: Visual Progress Bar"""

def make_bar(percent, width=36):
    filled = int(width * percent / 100)
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)

def color_bar(percent):
    """ (Notes to self)
        Returns an ANSI color code based on usage level.
        Green = safe, Yellow = moderate, Red = high.

        ANSI codes work on Linux/macOS terminals and Windows 10+.
    """

    if percent < 60:
        return "\033[92m"    # bright green
    elif percent < 85:
        return "\033[93m"    # bright yellow
    else:
        return "\033[91m"    # bright red

RESET = "\033[0m"
BOLD  = "\033[1m"
CYAN  = "\033[96m"
DIM   = "\033[2m"


"""SECTION: System Identity"""
def get_system_info():
    """
        Returns a dict with OS name, hostname, architecture, Python version,
        and current date/time.
    """

    return {
        "os": platform.system(),
        "os_version": platform.version()[:60],
        "hostname": platform.node(),
        "architecture": platform.machine(),
        "processor": platform.processor()[:50] or "N/A",
        "python": platform.python_version(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H%M%S"),
    }


"""SECTION: Uptime"""
def get_uptime():
    boot_timestamp = psutil.boot_time()
    boot_time = datetime.fromtimestamp(boot_timestamp)
    uptime_delta = datetime.now() - boot_time

    total_seconds = int(uptime_delta.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes        = (total_seconds % 3600) // 60

    return f"{days}d {hours}h {minutes}m", boot_time.strftime("%Y-%m-%d %H:%M")


"""SECTION: CPU"""
def get_cpu_info():
    """
        cpu_percent(interval=0.5): measures CPU usage over 0.5 seconds — more accurate than instant reads.
        cpu_count(logical=False): physical cores.
        cpu_count(logical=True):  logical cores (includes hyperthreading).
        cpu_freq(): current, min, max clock speed in MHz.
    """
    usage = psutil.cpu_percent(interval=0.5)
    cores_p = psutil.cpu_count(logical=False) or 1
    cores_l = psutil.cpu_count(logical=True) or 1
    freq = psutil.cpu_freq()

    freq_str = f"{freq.current:.0f} MHz  (max {freq.max:.0f} MHz)" if freq else "N/A"

    # Per-Core Breakdown
    per_core = psutil.cpu_percent(interval=0, percpu=True)

    return {
        "usage": usage,
        "cores_p": cores_p,
        "cores_l": cores_l,
        "freq": freq_str,
        "per_core": per_core,
    }


"""#  SECTION: Memory (RAM + Swap)"""
def bytes_to_gb(b):
    """Converts bytes to gigabytes, rounded to 2 decimal places."""
    return round(b / (1024 ** 3), 2)

def get_memory_info():
    ram = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        "ram_total": bytes_to_gb(ram.total),
        "ram_used": bytes_to_gb(ram.used),
        "ram_available": bytes_to_gb(ram.available),
        "ram_percent": ram.percent,
        "swap_total": bytes_to_gb(swap.total),
        "swap_used": bytes_to_gb(swap.used),
        "swap_percent": swap.percent,
    }


"""SECTION: DISK"""
def get_disk_info():
    partitions = []
    for part in psutil.disk_partitions():
        # skips Virtual/System filesystems
        if part.fstype in ("tmpfs", "devtmpfs", "squashfs", "overlay", ""):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            partitions.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total": bytes_to_gb(usage.total),
                "used": bytes_to_gb(usage.used),
                "free": bytes_to_gb(usage.free),
                "percent": usage.percent,
            })
        except PermissionError:
            # Some system mounts raise PermissionError
            continue

    return partitions


"""SECTION: Network"""
def bytes_to_mb(b):
    return round(b / (1024 ** 2), 2)

def get_network_info():
    """
        net_io_counters(): total bytes sent/received since boot (all interfaces combined).
        net_if_addrs():    IP addresses per interface.
        filter to only show interfaces that have an IPv4 address assigned.
    """
    io = psutil.net_io_counters()
    addrs = psutil.net_if_addrs()

    interfaces = []
    for iface, addr_list in addrs.items():
        for addr in addr_list:
            # socket.AF_INET = 2 (IPv4)
            if addr.family == 2:
                interfaces.append({
                    "name": iface,
                    "ip": addr.address,
                })

    return {
        "sent_mb": bytes_to_mb(io.bytes_sent),
        "recv_mb": bytes_to_mb(io.bytes_recv),
        "interfaces": interfaces,
    }


"""SECTION: Top Processes"""
def get_top_processes(n=5):
    # First pass: prime the cpu_percent counter for every process
    procs = []
    for proc in psutil.process_iter(["pid", "name", "memory_percent", "status"]):
        try:
            proc.cpu_percent(interval=None)  # primes the counter, returns 0 — we discard it
            procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Wait briefly so the kernel can measure actual CPU delta
    time.sleep(0.5)

    # Second pass: now cpu_percent returns real values
    results = []
    for proc in procs:
        try:
            results.append({
                "pid": proc.pid,
                "name": proc.name(),
                "cpu_percent": proc.cpu_percent(interval=None),
                "memory_percent": proc.memory_percent(),
                "status": proc.status(),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    results.sort(key=lambda p: p["cpu_percent"] or 0, reverse=True)
    return results[:n]



"""DISPLAY: Rendering the full dashboard"""
def clear_screen():
    """Clears the terminal. 'cls' on Windows, 'clear' on Linux/macOS."""
    os.system("cls" if os.name == "nt" else "clear")

def print_header(title):
    width = 60
    print(f"\n{CYAN}{'═' * width}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{'═' * width}{RESET}")

def print_section(title):
    print(f"\n{BOLD}  ── {title} {'─' * (50 - len(title))}{RESET}")


def render_dashboard():
    """
        Gathers all data and prints the full dashboard to the terminal.
        Each section calls its own data-fetching function.
    """

    # HEADER
    print_header("  System Info Dashboard")


    # SYSTEM
    print_section("System")
    info = get_system_info()
    uptime_str, boot_str = get_uptime()

    print(f"  {'Hostname': <16} {info['hostname']}")
    print(f"  {'OS':<16} {info['os']}  {info['os_version']}")
    print(f"  {'Architecture':<16} {info['architecture']}")
    print(f"  {'Processor':<16} {info['processor']}")
    print(f"  {'Python':<16} {info['python']}")
    print(f"  {'Boot time':<16} {boot_str}")
    print(f"  {'Uptime':<16} {uptime_str}")
    print(f"  {'Timestamp':<16} {info['timestamp']}")

    # CPU
    print_section("CPU")
    cpu = get_cpu_info()
    col = color_bar(cpu['usage'])
    bar = make_bar(cpu['usage'])
    print(f"  {'Usage':<16} {col}[{bar}]{RESET} {cpu['usage']:.1f}%")
    print(f"  {'Cores':<16} {cpu['cores_p']} physical  /  {cpu['cores_l']} logical")
    print(f"  {'Frequency':<16} {cpu['freq']}")

    # Per-core bars (show up to 8 cores to avoid overflow)
    if len(cpu['per_core']) > 1:
        print(f"\n  {DIM}Per-core usage:{RESET}")
        for i, c in enumerate(cpu['per_core'][:8]):
            c_col = color_bar(c)
            c_bar = make_bar(c, width=20)
            print(f"  Core {i:<3}        {c_col}[{c_bar}]{RESET} {c:.1f}%")

    # Memory
    print_section("Memory")
    mem = get_memory_info()
    ram_col = color_bar(mem['ram_percent'])
    swap_col = color_bar(mem['swap_percent'])
    ram_bar = make_bar(mem['ram_percent'])
    swap_bar = make_bar(mem['swap_percent'])

    print(f"  {'RAM':<16} {ram_col}[{ram_bar}]{RESET} {mem['ram_percent']:.1f}%")
    print(f"  {'':<16} {mem['ram_used']} GB used  /  {mem['ram_total']} GB total  ({mem['ram_available']} GB free)")

    if mem['swap_total'] > 0:
        print(f"  {'Swap':<16} {swap_col}[{swap_bar}]{RESET} {mem['swap_percent']:.1f}%")
        print(f"  {'':<16} {mem['swap_used']} GB used  /  {mem['swap_total']} GB total")
    else:
        print(f"  {'Swap':<16} Not configured")


    # DISK
    print_section("Disk")
    disks = get_disk_info()
    if disks:
        for disk in disks:
            d_col = color_bar(disk['percent'])
            d_bar = make_bar(disk['percent'])
            label = f"{disk['mountpoint']} ({disk['fstype']})"
            print(f"  {label}")
            print(
                f"  {'':>4}{d_col}[{d_bar}]{RESET} {disk['percent']:.1f}%  —  {disk['used']}/{disk['total']} GB  ({disk['free']} GB free)")
    else:
        print("  No readable disk partitions found.")


    # NETWORK
    print_section("Network")
    net = get_network_info()
    print(f"  {'Sent':<16} {net['sent_mb']} MB")
    print(f"  {'Received':<16} {net['recv_mb']} MB")
    if net['interfaces']:
        print(f"\n  {DIM}Interfaces:{RESET}")
        for iface in net['interfaces']:
            print(f"  {iface['name']:<16} {iface['ip']}")


    # TOP PROCESSES
    print_section("Top Processes (By CPU)")
    procs = get_top_processes(n=5)
    print(f"  {DIM}{'PID':<8} {'Name':<22} {'CPU%':>6}  {'MEM%':>6}  {'Status'}{RESET}")
    print(f"  {'─' * 56}")
    for p in procs:
        name = (p['name'] or 'N/A')[:22]
        cpu_p = f"{p['cpu_percent']:.1f}" if p['cpu_percent'] is not None else "N/A"
        mem_p = f"{p['memory_percent']:.1f}" if p['memory_percent'] is not None else "N/A"
        status = p['status'] or ''
        print(f"  {p['pid']:<8} {name:<22} {cpu_p:>6}  {mem_p:>6}  {status}")


    # FOOTER
    print(f"\n{CYAN}{'═' * 60}{RESET}\n")


"""Argument Parser: CLI Flags"""
#  EXPORT: Collect all data into one snapshot dict
def collect_snapshot():
    uptime_str, boot_str = get_uptime()
    sys_info = get_system_info()
    sys_info["uptime"]    = uptime_str
    sys_info["boot_time"] = boot_str

    return {
        "system":    sys_info,
        "cpu":       get_cpu_info(),
        "memory":    get_memory_info(),
        "disks":     get_disk_info(),
        "network":   get_network_info(),
        "processes": get_top_processes(n=5),
    }


def make_filename(fmt):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"dashboard_{timestamp}.{fmt}"


#  EXPORT: JSON
def export_json(snapshot):
    filename = make_filename("json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=4, default=str)
    return filename


#  EXPORT: CSV
def export_csv(snapshot):
    filename = make_filename("csv")
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # System
        writer.writerow(["SECTION", "KEY", "VALUE"])
        for key, val in snapshot["system"].items():
            writer.writerow(["System", key, val])
        writer.writerow([])

        # CPU
        cpu = snapshot["cpu"]
        writer.writerow(["SECTION", "KEY", "VALUE"])
        writer.writerow(["CPU", "usage_percent",  cpu["usage"]])
        writer.writerow(["CPU", "physical_cores", cpu["cores_p"]])
        writer.writerow(["CPU", "logical_cores",  cpu["cores_l"]])
        writer.writerow(["CPU", "frequency",      cpu["freq"]])
        for i, c in enumerate(cpu["per_core"]):
            writer.writerow(["CPU", f"core_{i}_percent", c])
        writer.writerow([])

        # Memory
        writer.writerow(["SECTION", "KEY", "VALUE"])
        for key, val in snapshot["memory"].items():
            writer.writerow(["Memory", key, val])
        writer.writerow([])

        # Disks
        writer.writerow(["SECTION", "device", "mountpoint", "fstype", "total_gb", "used_gb", "free_gb", "percent"])
        for disk in snapshot["disks"]:
            writer.writerow([
                "Disk",
                disk["device"], disk["mountpoint"], disk["fstype"],
                disk["total"],  disk["used"],       disk["free"],  disk["percent"]
            ])
        writer.writerow([])

        # Network
        net = snapshot["network"]
        writer.writerow(["SECTION", "KEY", "VALUE"])
        writer.writerow(["Network", "sent_mb", net["sent_mb"]])
        writer.writerow(["Network", "recv_mb", net["recv_mb"]])
        for iface in net["interfaces"]:
            writer.writerow(["Network", f"interface_{iface['name']}", iface["ip"]])
        writer.writerow([])

        # Processes
        writer.writerow(["SECTION", "pid", "name", "cpu_percent", "memory_percent", "status"])
        for p in snapshot["processes"]:
            writer.writerow([
                "Process",
                p["pid"], p["name"], p["cpu_percent"], p["memory_percent"], p["status"]
            ])

    return filename


#  EXPORT: HTML
def export_html(snapshot):

    def pct_bar(percent):
        if percent is None:
            return "N/A"
        clamped = min(float(percent), 100)   # BUG FIX: clamp to 100% max so bar never overflows
        if percent < 60:
            color = "#1D9E75"
        elif percent < 85:
            color = "#EF9F27"
        else:
            color = "#E24B4A"
        return (
            f'<div class="bar-wrap">'
            f'<div class="bar" style="width:{clamped:.1f}%;background:{color}"></div>'
            f'</div>'
            f'<span class="pct">{percent:.1f}%</span>'
        )

    def section(title, icon, content):
        return f"""
        <div class="card">
            <div class="card-header">
                <span class="card-icon">{icon}</span>
                <h2>{title}</h2>
            </div>
            {content}
        </div>"""

    def kv_table(rows):
        html = '<table><tbody>'
        for label, value in rows:
            html += f'<tr><td class="label">{label}</td><td class="value">{value}</td></tr>'
        html += '</tbody></table>'
        return html

    def disk_table(disks):
        if not disks:
            return '<p class="empty">No readable partitions found.</p>'
        rows = ""
        for d in disks:
            rows += f"""
            <tr>
                <td class="label">{d['mountpoint']}</td>
                <td class="label dim">{d['fstype']}</td>
                <td>{pct_bar(d['percent'])}</td>
                <td class="value">{d['used']}/{d['total']} GB</td>
                <td class="value">{d['free']} GB free</td>
            </tr>"""
        return f'<table><tbody>{rows}</tbody></table>'

    def proc_table(procs):
        rows = ""
        for p in procs:
            cpu_p  = f"{p['cpu_percent']:.1f}" if p['cpu_percent'] is not None else "N/A"
            mem_p  = f"{p['memory_percent']:.1f}%" if p['memory_percent'] is not None else "N/A"
            status = p['status'] or ''
            rows += f"""
            <tr>
                <td class="label dim">{p['pid']}</td>
                <td class="value">{p['name'] or 'N/A'}</td>
                <td>{pct_bar(p['cpu_percent']) if p['cpu_percent'] is not None else 'N/A'}</td>
                <td class="value">{mem_p}</td>
                <td><span class="badge">{status}</span></td>
            </tr>"""
        return f"""
        <table>
            <thead><tr>
                <th>PID</th><th>Name</th><th>CPU %</th><th>MEM %</th><th>Status</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>"""

    cpu  = snapshot["cpu"]
    mem  = snapshot["memory"]
    net  = snapshot["network"]
    sys  = snapshot["system"]

    # Per-core rows
    core_rows = [(f"Core {i}", pct_bar(c)) for i, c in enumerate(cpu["per_core"])]

    sys_content  = kv_table([
        ("Hostname",     sys["hostname"]),
        ("OS",           f"{sys['os']} — {sys['os_version']}"),
        ("Architecture", sys["architecture"]),
        ("Processor",    sys["processor"]),
        ("Python",       sys["python"]),
        ("Boot time",    sys.get("boot_time", "N/A")),
        ("Uptime",       sys.get("uptime", "N/A")),
    ])

    cpu_content  = kv_table([
        ("Usage",           pct_bar(cpu["usage"])),
        ("Physical cores",  cpu["cores_p"]),
        ("Logical cores",   cpu["cores_l"]),
        ("Frequency",       cpu["freq"]),
        *core_rows,
    ])

    mem_content  = kv_table([
        ("RAM usage",   pct_bar(mem["ram_percent"])),
        ("RAM used",    f"{mem['ram_used']} GB"),
        ("RAM total",   f"{mem['ram_total']} GB"),
        ("RAM free",    f"{mem['ram_available']} GB"),
        ("Swap usage",  pct_bar(mem["swap_percent"])),
        ("Swap used",   f"{mem['swap_used']} GB"),
        ("Swap total",  f"{mem['swap_total']} GB"),
    ])

    net_rows = [("Sent", f"{net['sent_mb']} MB"), ("Received", f"{net['recv_mb']} MB")]
    for iface in net["interfaces"]:
        net_rows.append((iface["name"], iface["ip"]))
    net_content = kv_table(net_rows)

    hostname  = sys["hostname"]
    timestamp = sys["timestamp"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>System Dashboard — {hostname}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Inter', sans-serif;
      background: #0b0d14;
      color: #c8cdd8;
      padding: 2rem;
      min-height: 100vh;
    }}

    /* ── Header ── */
    .header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      margin-bottom: 2rem;
      padding-bottom: 1.25rem;
      border-bottom: 1px solid #1e2235;
    }}
    .header-left h1 {{
      font-size: 1.5rem;
      font-weight: 600;
      color: #e8ebf2;
      letter-spacing: -0.02em;
    }}
    .header-left .sub {{
      font-size: 0.82rem;
      color: #4a5068;
      margin-top: 4px;
      font-family: 'JetBrains Mono', monospace;
    }}
    .header-right .timestamp {{
      font-size: 0.8rem;
      color: #4a5068;
      font-family: 'JetBrains Mono', monospace;
      text-align: right;
    }}
    .dot {{
      display: inline-block;
      width: 8px; height: 8px;
      background: #1D9E75;
      border-radius: 50%;
      margin-right: 6px;
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.4; }}
    }}

    /* ── Grid ── */
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 1rem;
    }}
    .grid-full {{
      grid-column: 1 / -1;
    }}

    /* ── Card ── */
    .card {{
      background: #10121c;
      border: 1px solid #1e2235;
      border-radius: 10px;
      overflow: hidden;
    }}
    .card-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 0.85rem 1.25rem;
      border-bottom: 1px solid #1e2235;
      background: #0e1018;
    }}
    .card-header h2 {{
      font-size: 0.78rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #5b6480;
    }}
    .card-icon {{
      font-size: 1rem;
    }}

    /* ── Tables ── */
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.855rem;
    }}
    thead tr {{
      background: #0e1018;
    }}
    th {{
      text-align: left;
      padding: 9px 1.25rem;
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      color: #3d4460;
      border-bottom: 1px solid #1e2235;
    }}
    td {{
      padding: 9px 1.25rem;
      border-bottom: 1px solid #131624;
      vertical-align: middle;
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #13162080; }}

    td.label {{
      color: #5b6480;
      font-size: 0.82rem;
      white-space: nowrap;
      width: 1%;
      padding-right: 2rem;
    }}
    td.label.dim {{ color: #343850; }}
    td.value {{
      color: #c8cdd8;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
    }}

    /* ── Progress bar ── */
    .bar-wrap {{
      display: inline-block;
      width: 140px;
      height: 6px;
      background: #1e2235;
      border-radius: 99px;
      vertical-align: middle;
      margin-right: 10px;
      overflow: hidden;        /* this is the real fix — clips bar at container edge */
    }}
    .bar {{
      height: 6px;
      border-radius: 99px;
      max-width: 100%;         /* belt-and-suspenders: never exceed container */
    }}
    .pct {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: #8891a8;
      vertical-align: middle;
    }}

    /* ── Badge ── */
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.72rem;
      font-weight: 500;
      background: #1a1e2e;
      color: #4a6fa5;
      border: 1px solid #1e2a42;
      font-family: 'JetBrains Mono', monospace;
    }}

    .empty {{
      padding: 1rem 1.25rem;
      color: #3d4460;
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>

  <div class="header">
    <div class="header-left">
      <h1><span class="dot"></span>{hostname}</h1>
      <p class="sub">system info dashboard</p>
    </div>
    <div class="header-right">
      <p class="timestamp">exported<br>{timestamp}</p>
    </div>
  </div>

  <div class="grid">

    <div class="card">
      <div class="card-header"><span class="card-icon">🖥</span><h2>System</h2></div>
      {sys_content}
    </div>

    <div class="card">
      <div class="card-header"><span class="card-icon">⚡</span><h2>CPU</h2></div>
      {cpu_content}
    </div>

    <div class="card">
      <div class="card-header"><span class="card-icon">🧠</span><h2>Memory</h2></div>
      {mem_content}
    </div>

    <div class="card">
      <div class="card-header"><span class="card-icon">📡</span><h2>Network</h2></div>
      {net_content}
    </div>

    <div class="card grid-full">
      <div class="card-header"><span class="card-icon">💾</span><h2>Disk</h2></div>
      {disk_table(snapshot["disks"])}
    </div>

    <div class="card grid-full">
      <div class="card-header"><span class="card-icon">📊</span><h2>Top Processes</h2></div>
      {proc_table(snapshot["processes"])}
    </div>

  </div>
</body>
</html>"""

    filename = make_filename("html")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    return filename


#  EXPORT: Router

def run_export(fmt):
    print(f"  Collecting system snapshot...")
    snapshot = collect_snapshot()
    exporters = {
        "json": export_json,
        "csv":  export_csv,
        "html": export_html,
    }
    filename = exporters[fmt](snapshot)
    print(f"  ✅ Exported → {os.path.abspath(filename)}\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="CLI System Info Dashboard"
    )
    parser.add_argument(
        "--watch",
        action="store_true",    # flag with no value: presence = True
        help="Continuously refresh the dashboard (like 'watch' on Linux)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Refresh interval in seconds when using --watch (default: 2)"
    )
    parser.add_argument(
        "--export",
        choices=["json", "csv", "html"],
        help="Export a snapshot to a file (json, csv, or html)"
    )
    return parser.parse_args()


"""ENTRY POINT"""
if __name__ == "__main__":
    args = parse_args()
    if args.export:
        run_export(args.export)
    if args.watch:
        print(f"  Watching system... refreshing every {args.interval}s.  Press Ctrl+C to exit.\n")
        try:
            while True:
                buffer = io.StringIO()
                sys.stdout = buffer  # redirect output to memory
                render_dashboard()  # runs silently (including the 0.5s CPU sample)
                sys.stdout = sys.__stdout__  # restore normal output
                clear_screen()  # NOW clear — data is ready
                print(buffer.getvalue())  # print everything at once, no flicker
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n  Dashboard stopped. Goodbye!\n")
    else:
        render_dashboard()