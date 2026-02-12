"""Scapy packet capture engine for NetScope.

Runs packet capture in a background thread, processes packets through
the parser, updates the database, and emits real-time stats.
"""

import logging
import platform
import time
import threading
from collections import defaultdict
from datetime import datetime, timezone

from scapy.all import conf, sniff, ARP, Ether, srp
from scapy.arch import get_if_addr, get_if_hwaddr

from .parser import ParsedDeviceInfo, parse_packet
from .fingerprint import infer_device_type
from ..core.database import (
    get_session,
    upsert_device,
    update_device_traffic,
    record_packet_stat,
    mark_stale_devices_offline,
    start_capture_session,
    end_capture_session,
)

logger = logging.getLogger(__name__)


class PacketCapture:
    """Background packet capture engine.

    Attributes:
        interface: Network interface to capture on (None for default).
        bandwidth_threshold: Bytes/sec threshold to flag high bandwidth devices.
        stats_interval: Seconds between bandwidth stat recordings.
    """

    def __init__(
        self,
        interface: str | None = None,
        bandwidth_threshold: int = 1_000_000,
        stats_interval: float = 2.0,
        on_device_update: callable = None,
    ):
        self.interface = interface
        self.bandwidth_threshold = bandwidth_threshold
        self.stats_interval = stats_interval
        self.on_device_update = on_device_update

        self._stop_event = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._stats_thread: threading.Thread | None = None
        self._packet_count = 0
        self._capture_session = None

        # Per-MAC traffic counters for the current stats window
        self._traffic_lock = threading.Lock()
        self._traffic: dict[str, dict] = defaultdict(
            lambda: {"bytes_sent": 0, "bytes_recv": 0, "packets_sent": 0, "packets_recv": 0}
        )

        # Set of MAC addresses seen (our local machine)
        self._local_macs: set[str] = set()

        # Vendor lookup instance
        self._mac_lookup = None

        # Platform-specific setup
        self._setup_platform()

    def _setup_platform(self):
        """Configure Scapy for the current platform."""
        system = platform.system()
        if system == "Windows":
            # Require Npcap on Windows
            conf.use_npcap = True
            logger.info("Windows detected, using Npcap")
        elif system == "Darwin":
            logger.info("macOS detected, using libpcap")
        else:
            logger.info("Linux detected, using libpcap")

    def _init_mac_lookup(self):
        """Initialize MAC vendor lookup, handling import failures gracefully."""
        try:
            from mac_vendor_lookup import MacLookup
            self._mac_lookup = MacLookup()
            # Pre-load the vendor database
            try:
                self._mac_lookup.update_vendors()
            except Exception:
                pass  # Use bundled data if update fails
            logger.info("MAC vendor lookup initialized")
        except ImportError:
            logger.warning("mac-vendor-lookup not installed, vendor resolution disabled")
            self._mac_lookup = None

    def lookup_vendor(self, mac: str) -> str | None:
        """Look up the vendor for a MAC address."""
        if self._mac_lookup is None:
            return None
        try:
            return self._mac_lookup.lookup(mac)
        except Exception:
            return None

    def start(self):
        """Start the capture and stats threads."""
        if self._capture_thread and self._capture_thread.is_alive():
            logger.warning("Capture already running")
            return

        self._stop_event.clear()
        self._init_mac_lookup()

        # Record local MAC for direction tracking
        try:
            iface = self.interface or conf.iface
            local_mac = get_if_hwaddr(iface)
            self._local_macs.add(local_mac.lower())
            logger.info("Local interface: %s (MAC: %s)", iface, local_mac)
        except Exception as e:
            logger.warning("Could not determine local MAC: %s", e)

        # Start database session and record capture session
        db = get_session()
        self._capture_session = start_capture_session(db, self.interface)
        db.close()

        # Run initial ARP scan to discover devices on the subnet
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="netscope-capture"
        )
        self._stats_thread = threading.Thread(
            target=self._stats_loop, daemon=True, name="netscope-stats"
        )

        self._capture_thread.start()
        self._stats_thread.start()
        logger.info("Capture engine started")

        # Run ARP scan in a separate thread to avoid blocking
        threading.Thread(
            target=self._initial_arp_scan, daemon=True, name="netscope-arpscan"
        ).start()

    def stop(self):
        """Stop capture gracefully."""
        logger.info("Stopping capture engine...")
        self._stop_event.set()

        if self._capture_thread:
            self._capture_thread.join(timeout=5)
        if self._stats_thread:
            self._stats_thread.join(timeout=5)

        # Finalize capture session
        if self._capture_session:
            db = get_session()
            end_capture_session(db, self._capture_session, self._packet_count)
            db.close()

        logger.info("Capture engine stopped (%d packets captured)", self._packet_count)

    @property
    def is_running(self) -> bool:
        return self._capture_thread is not None and self._capture_thread.is_alive()

    def _capture_loop(self):
        """Main packet capture loop using Scapy sniff."""
        try:
            sniff(
                iface=self.interface,
                prn=self._process_packet,
                stop_filter=lambda _: self._stop_event.is_set(),
                store=False,
            )
        except PermissionError:
            logger.error(
                "Permission denied. Run with administrator/root privileges, "
                "or ensure Npcap is installed on Windows."
            )
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error("Capture error: %s", e)

    def _process_packet(self, packet):
        """Process a single captured packet."""
        self._packet_count += 1

        info = parse_packet(packet, self._local_macs)
        if info is None or info.mac is None:
            return

        mac = info.mac.lower()

        # Update traffic counters
        with self._traffic_lock:
            counters = self._traffic[mac]
            if info.direction == "sent":
                counters["bytes_sent"] += info.bytes_size
                counters["packets_sent"] += 1
            else:
                counters["bytes_recv"] += info.bytes_size
                counters["packets_recv"] += 1

        # Update device in database for discovery-type packets
        if info.packet_type in ("arp", "dhcp", "mdns", "ssdp"):
            self._update_device(info)

    def _update_device(self, info: ParsedDeviceInfo):
        """Update or insert a device in the database."""
        try:
            db = get_session()
            vendor = self.lookup_vendor(info.mac)
            device_type = infer_device_type(vendor, info.hostname)

            upsert_device(
                db,
                mac=info.mac.lower(),
                ip=info.ip,
                hostname=info.hostname,
                vendor=vendor,
                device_type=device_type,
                dhcp_hostname=info.dhcp_hostname,
                mdns_name=info.mdns_name,
                ssdp_description=info.ssdp_description,
            )
            db.close()

            # Notify callback (used by SocketIO to push updates)
            if self.on_device_update:
                self.on_device_update()

        except Exception as e:
            logger.error("Error updating device %s: %s", info.mac, e)

    def _stats_loop(self):
        """Periodically flush traffic counters to the database."""
        while not self._stop_event.wait(self.stats_interval):
            self._flush_stats()
            # Mark stale devices offline
            try:
                db = get_session()
                mark_stale_devices_offline(db)
                db.close()
            except Exception as e:
                logger.error("Error marking stale devices: %s", e)

    def _flush_stats(self):
        """Write accumulated traffic counters to the database and reset."""
        with self._traffic_lock:
            snapshot = dict(self._traffic)
            self._traffic.clear()

        if not snapshot:
            return

        try:
            db = get_session()
            for mac, counters in snapshot.items():
                total_bytes = counters["bytes_sent"] + counters["bytes_recv"]
                bandwidth = total_bytes / self.stats_interval

                update_device_traffic(
                    db, mac, counters["bytes_sent"], counters["bytes_recv"]
                )
                record_packet_stat(
                    db,
                    mac=mac,
                    bytes_sent=counters["bytes_sent"],
                    bytes_recv=counters["bytes_recv"],
                    packets_sent=counters["packets_sent"],
                    packets_recv=counters["packets_recv"],
                    bandwidth_bps=bandwidth,
                )
            db.close()

            # Notify frontend after stats update
            if self.on_device_update:
                self.on_device_update()

        except Exception as e:
            logger.error("Error flushing stats: %s", e)

    def _initial_arp_scan(self):
        """Send ARP requests to discover devices on the local subnet."""
        try:
            iface = self.interface or conf.iface
            local_ip = get_if_addr(iface)
            if not local_ip or local_ip == "0.0.0.0":
                logger.warning("Could not determine local IP for ARP scan")
                return

            # Derive /24 subnet from local IP
            parts = local_ip.rsplit(".", 1)
            subnet = f"{parts[0]}.0/24"
            logger.info("Running initial ARP scan on %s", subnet)

            answered, _ = srp(
                Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet),
                timeout=3,
                iface=iface,
                verbose=False,
            )

            db = get_session()
            for sent, received in answered:
                mac = received.hwsrc.lower()
                ip = received.psrc
                vendor = self.lookup_vendor(mac)
                device_type = infer_device_type(vendor, None)

                upsert_device(
                    db,
                    mac=mac,
                    ip=ip,
                    vendor=vendor,
                    device_type=device_type,
                )
            db.close()

            logger.info("ARP scan complete, found %d devices", len(answered))

            if self.on_device_update and answered:
                self.on_device_update()

        except PermissionError:
            logger.warning("ARP scan requires elevated privileges, skipping")
        except Exception as e:
            logger.error("ARP scan failed: %s", e)

    def get_packet_count(self) -> int:
        return self._packet_count
