"""SQLAlchemy models for NetScope device and session tracking."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class Device(Base):
    """Represents a discovered network device."""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac = Column(String(17), unique=True, nullable=False, index=True)
    ip = Column(String(45), nullable=True)
    hostname = Column(String(255), nullable=True)
    vendor = Column(String(255), nullable=True)
    device_type = Column(String(64), nullable=True)
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_online = Column(Boolean, default=True)
    bytes_sent = Column(Integer, default=0)
    bytes_recv = Column(Integer, default=0)
    mdns_name = Column(String(255), nullable=True)
    ssdp_description = Column(Text, nullable=True)
    dhcp_hostname = Column(String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "mac": self.mac,
            "ip": self.ip,
            "hostname": self.display_name,
            "vendor": self.vendor,
            "device_type": self.device_type or "unknown",
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_online": self.is_online,
            "bytes_sent": self.bytes_sent,
            "bytes_recv": self.bytes_recv,
        }

    @property
    def display_name(self):
        """Return the best available name for this device."""
        return (
            self.dhcp_hostname
            or self.mdns_name
            or self.hostname
            or self.ip
            or self.mac
        )


class CaptureSession(Base):
    """Tracks a capture session (one run of NetScope)."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    interface = Column(String(64), nullable=True)
    packet_count = Column(Integer, default=0)


class PacketStat(Base):
    """Per-device bandwidth sample recorded every few seconds."""

    __tablename__ = "packet_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac = Column(String(17), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    bytes_sent = Column(Integer, default=0)
    bytes_recv = Column(Integer, default=0)
    packets_sent = Column(Integer, default=0)
    packets_recv = Column(Integer, default=0)
    bandwidth_bps = Column(Float, default=0.0)
