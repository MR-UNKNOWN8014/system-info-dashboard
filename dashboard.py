import psutil
import argparse
import platform
import os
import time
from datetime import datetime, timedelta
import io
import sys


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
    return parser.parse_args()


"""ENTRY POINT"""
if __name__ == "__main__":
    args = parse_args()

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