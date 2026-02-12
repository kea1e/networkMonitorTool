"""Database initialization and helper queries for NetScope."""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, CaptureSession, Device, PacketStat

logger = logging.getLogger(__name__)

# Default database location
DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "netscope.db"

_engine = None
_SessionFactory = None


def init_db(db_path: str | None = None) -> sessionmaker:
    """Initialize the database engine and create tables.

    Args:
        db_path: Optional custom path for the SQLite database file.
                 Defaults to data/netscope.db relative to project root.

    Returns:
        A sessionmaker factory bound to the engine.
    """
    global _engine, _SessionFactory

    if db_path is None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        db_path = str(DB_PATH)

    _engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(_engine)
    _SessionFactory = sessionmaker(bind=_engine)
    logger.info("Database initialized at %s", db_path)
    return _SessionFactory


def get_session() -> Session:
    """Return a new database session."""
    if _SessionFactory is None:
        init_db()
    return _SessionFactory()


def upsert_device(
    session: Session,
    mac: str,
    ip: str | None = None,
    hostname: str | None = None,
    vendor: str | None = None,
    device_type: str | None = None,
    dhcp_hostname: str | None = None,
    mdns_name: str | None = None,
    ssdp_description: str | None = None,
) -> Device:
    """Insert or update a device record by MAC address.

    Only non-None fields are updated on existing records to avoid
    overwriting previously discovered information.
    """
    device = session.query(Device).filter_by(mac=mac).first()
    now = datetime.now(timezone.utc)

    if device is None:
        device = Device(
            mac=mac,
            ip=ip,
            hostname=hostname,
            vendor=vendor,
            device_type=device_type,
            dhcp_hostname=dhcp_hostname,
            mdns_name=mdns_name,
            ssdp_description=ssdp_description,
            first_seen=now,
            last_seen=now,
            is_online=True,
        )
        session.add(device)
        logger.info("New device discovered: %s (%s)", mac, hostname or ip or "unknown")
    else:
        # Update only fields that have new non-None values
        if ip is not None:
            device.ip = ip
        if hostname is not None:
            device.hostname = hostname
        if vendor is not None:
            device.vendor = vendor
        if device_type is not None:
            device.device_type = device_type
        if dhcp_hostname is not None:
            device.dhcp_hostname = dhcp_hostname
        if mdns_name is not None:
            device.mdns_name = mdns_name
        if ssdp_description is not None:
            device.ssdp_description = ssdp_description
        device.last_seen = now
        device.is_online = True

    session.commit()
    return device


def update_device_traffic(session: Session, mac: str, bytes_sent: int, bytes_recv: int):
    """Increment traffic counters for a device."""
    device = session.query(Device).filter_by(mac=mac).first()
    if device:
        device.bytes_sent += bytes_sent
        device.bytes_recv += bytes_recv
        device.last_seen = datetime.now(timezone.utc)
        device.is_online = True
        session.commit()


def record_packet_stat(
    session: Session,
    mac: str,
    bytes_sent: int,
    bytes_recv: int,
    packets_sent: int,
    packets_recv: int,
    bandwidth_bps: float,
):
    """Record a bandwidth sample for a device."""
    stat = PacketStat(
        mac=mac,
        bytes_sent=bytes_sent,
        bytes_recv=bytes_recv,
        packets_sent=packets_sent,
        packets_recv=packets_recv,
        bandwidth_bps=bandwidth_bps,
    )
    session.add(stat)
    session.commit()


def mark_stale_devices_offline(session: Session, timeout_seconds: int = 120):
    """Mark devices as offline if not seen within timeout period."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
    stale = (
        session.query(Device)
        .filter(Device.is_online == True, Device.last_seen < cutoff)
        .all()
    )
    for device in stale:
        device.is_online = False
    if stale:
        session.commit()
        logger.debug("Marked %d devices offline", len(stale))


def get_all_devices(session: Session) -> list[Device]:
    """Return all known devices, ordered by last_seen descending."""
    return session.query(Device).order_by(Device.last_seen.desc()).all()


def get_online_devices(session: Session) -> list[Device]:
    """Return currently online devices."""
    return (
        session.query(Device)
        .filter_by(is_online=True)
        .order_by(Device.last_seen.desc())
        .all()
    )


def get_device_bandwidth_history(
    session: Session, mac: str, minutes: int = 1
) -> list[PacketStat]:
    """Return recent bandwidth samples for a device."""
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return (
        session.query(PacketStat)
        .filter(PacketStat.mac == mac, PacketStat.timestamp >= since)
        .order_by(PacketStat.timestamp.asc())
        .all()
    )


def start_capture_session(session: Session, interface: str | None = None) -> CaptureSession:
    """Record a new capture session."""
    cs = CaptureSession(interface=interface)
    session.add(cs)
    session.commit()
    return cs


def end_capture_session(session: Session, capture_session: CaptureSession, packet_count: int):
    """Finalize a capture session."""
    capture_session.ended_at = datetime.now(timezone.utc)
    capture_session.packet_count = packet_count
    session.commit()
