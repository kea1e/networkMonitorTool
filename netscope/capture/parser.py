"""Extract device info from ARP, DHCP, mDNS, and SSDP packets using Scapy."""

import logging
import struct
from dataclasses import dataclass, field

from scapy.layers.dhcp import BOOTP, DHCP
from scapy.layers.dns import DNS, DNSQR, DNSRR
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import ARP, Ether
from scapy.packet import Packet

logger = logging.getLogger(__name__)

# SSDP multicast address and port
SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900

# mDNS multicast address and port
MDNS_ADDR = "224.0.0.251"
MDNS_PORT = 5353


@dataclass
class ParsedDeviceInfo:
    """Information extracted from a single packet."""

    mac: str | None = None
    ip: str | None = None
    hostname: str | None = None
    dhcp_hostname: str | None = None
    mdns_name: str | None = None
    ssdp_description: str | None = None
    packet_type: str = "unknown"
    bytes_size: int = 0
    direction: str = "unknown"  # "sent" or "recv" relative to the local net source


def parse_packet(packet: Packet, local_macs: set[str] | None = None) -> ParsedDeviceInfo | None:
    """Parse a captured packet and extract device information.

    Args:
        packet: A Scapy packet.
        local_macs: Set of known local MAC addresses (for direction tracking).

    Returns:
        ParsedDeviceInfo if useful info was extracted, None otherwise.
    """
    if not packet.haslayer(Ether):
        return None

    info = ParsedDeviceInfo(
        mac=packet[Ether].src,
        bytes_size=len(packet),
    )

    # Determine direction based on source MAC
    if local_macs and info.mac in local_macs:
        info.direction = "sent"
    elif local_macs:
        info.direction = "recv"

    # Try each parser in order of specificity
    if packet.haslayer(ARP):
        _parse_arp(packet, info)
    elif packet.haslayer(DHCP):
        _parse_dhcp(packet, info)
    elif packet.haslayer(DNS) and packet.haslayer(UDP):
        _parse_mdns(packet, info)
    elif packet.haslayer(UDP) and packet.haslayer(IP):
        _parse_ssdp(packet, info)
    elif packet.haslayer(IP):
        _parse_ip(packet, info)
    else:
        return None

    return info


def _parse_arp(packet: Packet, info: ParsedDeviceInfo):
    """Extract IP/MAC mappings from ARP packets."""
    arp = packet[ARP]
    info.packet_type = "arp"
    # ARP reply (is-at) or request (who-has)
    if arp.op in (1, 2):
        info.mac = arp.hwsrc
        info.ip = arp.psrc


def _parse_dhcp(packet: Packet, info: ParsedDeviceInfo):
    """Extract hostname and IP from DHCP packets."""
    info.packet_type = "dhcp"
    bootp = packet[BOOTP]
    dhcp_options = packet[DHCP].options

    # Client IP from BOOTP
    if bootp.ciaddr and bootp.ciaddr != "0.0.0.0":
        info.ip = bootp.ciaddr
    elif bootp.yiaddr and bootp.yiaddr != "0.0.0.0":
        info.ip = bootp.yiaddr

    info.mac = _format_mac(bootp.chaddr[:6])

    for option in dhcp_options:
        if isinstance(option, tuple):
            key, value = option[0], option[1]
            if key == "hostname":
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                info.dhcp_hostname = value
                info.hostname = value
            elif key == "requested_addr" and not info.ip:
                info.ip = value


def _parse_mdns(packet: Packet, info: ParsedDeviceInfo):
    """Extract device names from mDNS/Bonjour responses."""
    udp = packet[UDP]
    if udp.dport != MDNS_PORT and udp.sport != MDNS_PORT:
        return

    info.packet_type = "mdns"
    dns = packet[DNS]

    if packet.haslayer(IP):
        info.ip = packet[IP].src

    # Parse answer records for device names
    if dns.ancount and dns.ancount > 0:
        for i in range(dns.ancount):
            try:
                rr = dns.an[i]
                if hasattr(rr, "rrname"):
                    name = rr.rrname
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", errors="replace")
                    # Strip trailing dot from DNS names
                    name = name.rstrip(".")
                    # Look for PTR and TXT records with useful names
                    if hasattr(rr, "type") and rr.type in (12, 16):  # PTR, TXT
                        # Filter out generic service names
                        if not name.startswith("_") and ".local" in name:
                            device_name = name.split(".")[0]
                            if device_name:
                                info.mdns_name = device_name
                                info.hostname = device_name
                                break
                    # SRV or A records
                    elif hasattr(rr, "type") and rr.type in (1, 33):  # A, SRV
                        if ".local" in name:
                            device_name = name.split(".")[0]
                            if device_name:
                                info.mdns_name = device_name
                                info.hostname = device_name
                                break
            except (IndexError, AttributeError):
                continue


def _parse_ssdp(packet: Packet, info: ParsedDeviceInfo):
    """Extract UPnP device info from SSDP packets."""
    ip = packet[IP]
    udp = packet[UDP]

    if udp.dport != SSDP_PORT and udp.sport != SSDP_PORT:
        return

    info.packet_type = "ssdp"
    info.ip = ip.src

    # Parse the SSDP payload for SERVER or USN headers
    if packet.haslayer(UDP) and hasattr(packet[UDP], "load"):
        try:
            payload = packet[UDP].load.decode("utf-8", errors="replace")
        except (AttributeError, UnicodeDecodeError):
            return

        for line in payload.split("\r\n"):
            line_lower = line.lower()
            if line_lower.startswith("server:"):
                info.ssdp_description = line.split(":", 1)[1].strip()
            elif line_lower.startswith("usn:"):
                usn = line.split(":", 1)[1].strip()
                if "::" in usn:
                    info.ssdp_description = info.ssdp_description or usn


def _parse_ip(packet: Packet, info: ParsedDeviceInfo):
    """Extract basic IP info from any IP packet."""
    info.packet_type = "ip"
    info.ip = packet[IP].src


def _format_mac(mac_bytes: bytes) -> str:
    """Format raw MAC bytes as colon-separated hex string."""
    return ":".join(f"{b:02x}" for b in mac_bytes)
