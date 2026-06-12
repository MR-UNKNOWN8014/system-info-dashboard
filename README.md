# CLI System Info Dashboard

A terminal-based system monitoring dashboard built with Python and `psutil`. Displays live CPU, RAM, Disk, Network, and Process info with color-coded progress bars and a flicker free live watch mode.

---

## Preview

```
════════════════════════════════════════════════════════════
  🖥️  System Info Dashboard
════════════════════════════════════════════════════════════

  ── System ────────────────────────────────────────────
  Hostname         my-machine
  OS               Windows
  Architecture     x86_64
  Python           3.12.3
  Uptime           2d 4h 17m

  ── CPU ───────────────────────────────────────────────
  Usage            [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 23.4%
  Cores            4 physical  /  8 logical

  ── Memory ────────────────────────────────────────────
  RAM              [██████████████░░░░░░░░░░░░░░░░░░░░░░] 38.2%
                   6.1 GB used  /  16.0 GB total  (9.9 GB free)

  ── Top Processes (by CPU) ────────────────────────────
  PID      Name                     CPU%    MEM%  Status
  ────────────────────────────────────────────────────────
  4821     chrome.exe               12.4     3.1  running
  1234     python.exe                4.2     1.8  running
```

---

## Features

- **System info**: hostname, OS, architecture, Python version, uptime
- **CPU monitoring**: overall usage + per-core breakdown with color-coded bars
- **Memory monitoring**: RAM and swap usage with live percentages
- **Disk monitoring**: all mounted partitions with usage percentages
- **Network info**: total bytes sent/received, active IPv4 interfaces
- **Top processes**: top 5 processes ranked by real CPU usage (not zeroed readings)
- **Color-coded bars**: green / yellow / red based on usage thresholds
- **Live watch mode**: flicker-free auto-refresh at a configurable interval

---

## Tech Stack

|Tool|Purpose|
|---|---|
|`psutil`|System resource data (CPU, RAM, disk, network, processes)|
|`platform`|OS name, hostname, architecture|
|`argparse`|CLI flags (`--watch`, `--interval`)|
|`datetime`|Uptime calculation and timestamps|
|`os`|Cross-platform terminal clear|
|`io` / `sys`|Output buffering for flicker-free watch mode|

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/MR-UNKNOWN8014/system-info-dashboard.git
cd system-info-dashboard
```

### 2. Create and activate a virtual environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
# One-shot snapshot (with accurate CPU readings)
python dashboard.py

# Live refresh every 2 seconds — flicker-free
python dashboard.py --watch

# Live refresh every 5 seconds
python dashboard.py --watch --interval 5
```

### CLI Flags

|Flag|Default|Description|
|---|---|---|
|`--watch`|off|Enable live refresh mode|
|`--interval N`|`2`|Refresh interval in seconds|

---

## Project Structure

```
system-info-dashboard/
│
├── dashboard.py        # Main script
├── requirements.txt    # Python dependencies
├── README.md           # Project documentation
└── .gitignore          # Git ignore rules
```

---

## Requirements

```
psutil>=5.9.0
```

Python 3.8+ recommended. Works on Windows, Linux, and macOS.

---

## Skills Demonstrated

- Python scripting and modular code organization
- System-level programming with `psutil`
- CLI application design with `argparse`
- ANSI terminal formatting and color output
- Cross-platform compatibility (Windows, Linux, macOS)
- Real-time monitoring with flicker-free output buffering (`io.StringIO`)
- Two-pass CPU sampling to eliminate zeroed process readings
- Graceful `KeyboardInterrupt` exit handling

---

## Bugs Fixed During Development

| Bug                                     | Cause                                                               | Fix                                                                    |
| --------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Top processes showed 0% CPU             | `psutil.cpu_percent()` returns 0 on first call — needs two readings | Prime all processes, wait 0.5s, read again                             |
| Watch mode flickered on process section | Screen cleared before CPU sample completed                          | Buffer full output with `io.StringIO`, clear only when render is ready |


---
