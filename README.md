# NetScope — Network Monitoring Dashboard

A cross-platform Python network monitoring tool that captures and visualizes live network traffic. NetScope passively discovers every device on your local network, identifies device types and vendors from MAC addresses and protocol fingerprinting, and displays real-time bandwidth metrics through a clean web dashboard.

## Features

- **Device Discovery** — Passive ARP, DHCP, mDNS/Bonjour, and SSDP sniffing to detect all devices on the subnet, plus an active ARP scan on startup
- **Device Identification** — MAC OUI vendor lookup, DHCP hostname extraction, mDNS name parsing, and pattern-based device type inference (smartphone, laptop, smart TV, IoT, etc.)
- **Bandwidth Monitoring** — Per-device bytes sent/received tracking, rolling throughput graph, and total network traffic gauges
- **Web Dashboard** — Real-time dark-themed UI with device cards, search/filter, live Chart.js bandwidth graph, and top devices panel — all updated via WebSocket
- **Persistent Storage** — SQLite database retains device history across sessions

## Prerequisites

### Windows
1. Install **[Npcap](https://npcap.com/#download)** (required for packet capture on Windows)
   - During installation, check **"Install Npcap in WinPcap API-compatible Mode"**
   - Npcap is the modern replacement for WinPcap and is maintained by the Nmap project

### Linux
- libpcap is typically pre-installed
- You will need to run NetScope with `sudo` or configure capabilities:
  ```bash
  sudo setcap cap_net_raw,cap_net_admin=eip $(which python3)
  ```

### macOS
- libpcap is included with macOS
- Run with `sudo` for packet capture permissions

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/netscope.git
cd netscope

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Basic usage (auto-detect interface, dashboard on http://127.0.0.1:5000)
python -m netscope

# Specify network interface
python -m netscope --interface eth0

# Custom port and host
python -m netscope --port 8080 --host 0.0.0.0

# Enable debug logging
python -m netscope --debug

# All options
python -m netscope --interface eth0 --port 5000 --host 127.0.0.1 --db ./my_data.db --threshold 500000 --debug
```

Then open your browser to the displayed URL (default: http://127.0.0.1:5000).

### Command-line Options

| Flag | Description | Default |
|------|-------------|---------|
| `--interface`, `-i` | Network interface to capture on | Auto-detect |
| `--port`, `-p` | Dashboard web server port | 5000 |
| `--host` | Dashboard bind address | 127.0.0.1 |
| `--db` | SQLite database file path | `data/netscope.db` |
| `--threshold` | Bandwidth threshold (bytes/sec) to flag devices | 1000000 |
| `--debug` | Enable debug logging | Off |

## Project Structure

```
netscope/
├── capture/
│   ├── sniffer.py        # Scapy packet capture engine (background thread)
│   ├── parser.py         # ARP/DHCP/mDNS/SSDP packet parsing
│   └── fingerprint.py    # Device type inference from vendor + hostname
├── core/
│   ├── models.py         # SQLAlchemy models (Device, CaptureSession, PacketStat)
│   └── database.py       # DB init, upsert, and query helpers
├── api/
│   └── routes.py         # Flask REST API + SocketIO real-time events
├── dashboard/
│   ├── index.html        # Single-page dashboard
│   ├── app.js            # WebSocket client, Chart.js rendering
│   └── styles.css        # Dark theme UI
├── main.py               # Entry point — ties capture engine to web server
└── __main__.py           # Enables `python -m netscope`
```

## REST API

| Endpoint | Description |
|----------|-------------|
| `GET /api/devices` | All discovered devices |
| `GET /api/devices/online` | Currently online devices |
| `GET /api/devices/<mac>/bandwidth?minutes=1` | Bandwidth history for a device |
| `GET /api/stats` | Aggregate network statistics |

## How It Works

1. **Startup**: The capture engine initializes Scapy, detects the platform (Windows/Npcap, Linux/macOS/libpcap), and fires an ARP scan across the /24 subnet to discover existing devices.

2. **Passive Capture**: A background thread sniffs all Ethernet frames and passes them through protocol-specific parsers:
   - **ARP** packets yield IP-to-MAC mappings
   - **DHCP** packets reveal hostnames (e.g., "Johns-iPhone")
   - **mDNS/Bonjour** responses expose device names and service types
   - **SSDP/UPnP** announcements provide device descriptions

3. **Fingerprinting**: Discovered vendor names and hostnames are matched against pattern tables to infer device types (smartphone, laptop, smart TV, printer, IoT, etc.).

4. **Stats Loop**: Every 2 seconds, accumulated per-device byte counters are flushed to SQLite and broadcast to the dashboard via SocketIO.

5. **Dashboard**: The browser connects via WebSocket and receives live device updates rendered as cards with hostname, IP, MAC, vendor, device type icon, online status, and traffic counters. A Chart.js line graph shows rolling network throughput.

## Known Limitations

- **Permissions**: Packet capture requires elevated privileges (Administrator on Windows, root/sudo on Linux/macOS)
- **Subnet scope**: The initial ARP scan covers /24 only; devices on other subnets won't be discovered via ARP
- **Encrypted traffic**: NetScope sees packet metadata (src/dst IP, size) but cannot inspect encrypted payloads
- **Bandwidth accuracy**: Byte counts reflect traffic visible to the capture interface — a Wi-Fi adapter in managed mode won't see traffic between other wireless clients
- **MAC vendor database**: The `mac-vendor-lookup` library ships a bundled OUI database that may not cover the newest hardware

## TODO

- [ ] Add PCAP file export for captured sessions
- [ ] Implement device alerting (email/webhook) when new devices join
- [ ] Support multiple subnet scanning
- [ ] Add per-device bandwidth history page with longer time windows
- [ ] Docker container support
- [ ] HTTPS support for the dashboard
- [ ] Configuration file support (YAML/TOML)

## License

MIT
