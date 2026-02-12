"""Flask REST endpoints and SocketIO events for the NetScope dashboard."""

import logging
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO

from ..core.database import (
    get_all_devices,
    get_device_bandwidth_history,
    get_online_devices,
    get_session,
    mark_stale_devices_offline,
)

logger = logging.getLogger(__name__)

# Dashboard static files directory
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"

app = Flask(__name__, static_folder=str(DASHBOARD_DIR))
app.config["SECRET_KEY"] = "netscope-dev-key"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")


# ─── Static file serving ────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main dashboard page."""
    return send_from_directory(str(DASHBOARD_DIR), "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    """Serve dashboard static assets (JS, CSS)."""
    return send_from_directory(str(DASHBOARD_DIR), filename)


# ─── REST API ────────────────────────────────────────────────────────────

@app.route("/api/devices")
def api_devices():
    """Return all known devices as JSON."""
    db = get_session()
    mark_stale_devices_offline(db)
    devices = get_all_devices(db)
    result = [d.to_dict() for d in devices]
    db.close()
    return jsonify(result)


@app.route("/api/devices/online")
def api_online_devices():
    """Return currently online devices."""
    db = get_session()
    mark_stale_devices_offline(db)
    devices = get_online_devices(db)
    result = [d.to_dict() for d in devices]
    db.close()
    return jsonify(result)


@app.route("/api/devices/<mac>/bandwidth")
def api_device_bandwidth(mac):
    """Return bandwidth history for a specific device."""
    minutes = request.args.get("minutes", 1, type=int)
    db = get_session()
    stats = get_device_bandwidth_history(db, mac, minutes=minutes)
    result = [
        {
            "timestamp": s.timestamp.isoformat(),
            "bytes_sent": s.bytes_sent,
            "bytes_recv": s.bytes_recv,
            "bandwidth_bps": s.bandwidth_bps,
        }
        for s in stats
    ]
    db.close()
    return jsonify(result)


@app.route("/api/stats")
def api_stats():
    """Return aggregate network statistics."""
    db = get_session()
    mark_stale_devices_offline(db)
    all_devices = get_all_devices(db)
    online_devices = [d for d in all_devices if d.is_online]

    total_sent = sum(d.bytes_sent for d in all_devices)
    total_recv = sum(d.bytes_recv for d in all_devices)

    # Find top bandwidth user
    top_device = None
    if all_devices:
        top = max(all_devices, key=lambda d: d.bytes_sent + d.bytes_recv)
        top_device = {
            "hostname": top.display_name,
            "mac": top.mac,
            "total_bytes": top.bytes_sent + top.bytes_recv,
        }

    db.close()
    return jsonify({
        "total_devices": len(all_devices),
        "online_devices": len(online_devices),
        "total_bytes_sent": total_sent,
        "total_bytes_recv": total_recv,
        "top_device": top_device,
    })


# ─── SocketIO events ────────────────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    """Send initial device list on client connection."""
    logger.info("Dashboard client connected")
    _emit_device_update()


@socketio.on("request_update")
def handle_request_update():
    """Client-requested refresh."""
    _emit_device_update()


def _emit_device_update():
    """Push current device list and stats to all connected clients."""
    db = get_session()
    mark_stale_devices_offline(db)
    devices = get_all_devices(db)
    online = [d for d in devices if d.is_online]

    total_sent = sum(d.bytes_sent for d in devices)
    total_recv = sum(d.bytes_recv for d in devices)

    top_device = None
    if devices:
        top = max(devices, key=lambda d: d.bytes_sent + d.bytes_recv)
        top_device = {
            "hostname": top.display_name,
            "mac": top.mac,
            "total_bytes": top.bytes_sent + top.bytes_recv,
        }

    payload = {
        "devices": [d.to_dict() for d in devices],
        "stats": {
            "total_devices": len(devices),
            "online_devices": len(online),
            "total_bytes_sent": total_sent,
            "total_bytes_recv": total_recv,
            "top_device": top_device,
        },
    }
    db.close()

    socketio.emit("device_update", payload)


def broadcast_update():
    """Called by the capture engine to push updates to clients.

    This is the callback passed to PacketCapture.on_device_update.
    """
    _emit_device_update()
