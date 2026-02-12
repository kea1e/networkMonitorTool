"""NetScope — Network Monitoring Dashboard entry point.

Usage:
    python -m netscope.main [--interface IFACE] [--port PORT] [--host HOST]

Starts the packet capture engine in background threads and serves the
web dashboard via Flask + SocketIO.
"""

import argparse
import logging
import signal
import sys

import eventlet
eventlet.monkey_patch()

from .api.routes import app, broadcast_update, socketio
from .capture.sniffer import PacketCapture
from .core.database import init_db


def parse_args():
    parser = argparse.ArgumentParser(
        description="NetScope — Real-time network monitoring dashboard"
    )
    parser.add_argument(
        "--interface", "-i",
        default=None,
        help="Network interface to capture on (default: auto-detect)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=5000,
        help="Web dashboard port (default: 5000)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Web dashboard host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to SQLite database file (default: data/netscope.db)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=1_000_000,
        help="Bandwidth threshold in bytes/sec to flag devices (default: 1000000)",
    )
    return parser.parse_args()


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy libraries
    logging.getLogger("engineio").setLevel(logging.WARNING)
    logging.getLogger("socketio").setLevel(logging.WARNING)
    logging.getLogger("scapy").setLevel(logging.WARNING)


def main():
    args = parse_args()
    setup_logging(args.debug)

    logger = logging.getLogger("netscope")
    logger.info("Starting NetScope...")

    # Initialize database
    init_db(args.db)

    # Start packet capture engine
    capture = PacketCapture(
        interface=args.interface,
        bandwidth_threshold=args.threshold,
        on_device_update=broadcast_update,
    )
    capture.start()

    # Graceful shutdown handler
    def shutdown(signum=None, frame=None):
        logger.info("Shutting down...")
        capture.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start the web server
    logger.info("Dashboard available at http://%s:%d", args.host, args.port)
    socketio.run(app, host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
