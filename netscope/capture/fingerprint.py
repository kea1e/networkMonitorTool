"""Device type inference from vendor name, hostname, and protocol hints."""

import re

# Maps vendor substrings (lowercased) to device types.
VENDOR_TYPE_MAP = {
    "apple": "apple_device",
    "samsung": "smartphone",
    "google": "smart_device",
    "amazon": "smart_device",
    "sonos": "speaker",
    "roku": "streaming",
    "lg electronics": "smart_tv",
    "sony": "smart_tv",
    "vizio": "smart_tv",
    "nest": "smart_home",
    "ring": "smart_home",
    "philips": "smart_home",
    "tp-link": "network",
    "netgear": "network",
    "cisco": "network",
    "ubiquiti": "network",
    "arris": "router",
    "motorola": "router",
    "intel": "computer",
    "dell": "computer",
    "lenovo": "computer",
    "hewlett": "computer",
    "hp inc": "computer",
    "microsoft": "computer",
    "asus": "computer",
    "raspberry": "iot",
    "espressif": "iot",
    "xbox": "gaming",
    "nintendo": "gaming",
    "playstation": "gaming",
    "canon": "printer",
    "brother": "printer",
    "epson": "printer",
}

# Hostname regex patterns to device types.
HOSTNAME_PATTERNS = [
    (re.compile(r"iphone", re.I), "smartphone"),
    (re.compile(r"ipad", re.I), "tablet"),
    (re.compile(r"macbook", re.I), "laptop"),
    (re.compile(r"imac", re.I), "desktop"),
    (re.compile(r"apple.?tv", re.I), "streaming"),
    (re.compile(r"android", re.I), "smartphone"),
    (re.compile(r"galaxy", re.I), "smartphone"),
    (re.compile(r"pixel", re.I), "smartphone"),
    (re.compile(r"windows|desktop|workstation", re.I), "computer"),
    (re.compile(r"laptop|notebook", re.I), "laptop"),
    (re.compile(r"printer|mfc-|laserjet|deskjet", re.I), "printer"),
    (re.compile(r"chromecast|roku|firestick|fire.?tv", re.I), "streaming"),
    (re.compile(r"echo|alexa|home.?mini|home.?max", re.I), "smart_device"),
    (re.compile(r"nest|thermostat|ring|cam", re.I), "smart_home"),
    (re.compile(r"xbox|playstation|ps[45]|switch", re.I), "gaming"),
    (re.compile(r"sonos|speaker|soundbar", re.I), "speaker"),
    (re.compile(r"tv|bravia|tizen|webos|roku.?tv", re.I), "smart_tv"),
    (re.compile(r"raspberry|pi|esp|arduino", re.I), "iot"),
]

# Map device types to dashboard display icons (emoji shorthand).
DEVICE_ICONS = {
    "smartphone": "phone",
    "tablet": "tablet",
    "laptop": "laptop",
    "desktop": "desktop",
    "computer": "desktop",
    "apple_device": "apple",
    "printer": "printer",
    "smart_tv": "tv",
    "streaming": "tv",
    "gaming": "gamepad",
    "speaker": "speaker",
    "smart_device": "smart",
    "smart_home": "smart",
    "router": "router",
    "network": "router",
    "iot": "chip",
    "unknown": "device",
}


def infer_device_type(vendor: str | None, hostname: str | None) -> str:
    """Infer device type from vendor name and hostname patterns.

    Checks hostname patterns first (more specific), then falls back to
    vendor substring matching.

    Returns a device type string like 'smartphone', 'laptop', 'printer', etc.
    """
    # Hostname patterns are generally more specific, check first
    if hostname:
        for pattern, device_type in HOSTNAME_PATTERNS:
            if pattern.search(hostname):
                return device_type

    # Fall back to vendor substring matching
    if vendor:
        vendor_lower = vendor.lower()
        for substr, device_type in VENDOR_TYPE_MAP.items():
            if substr in vendor_lower:
                # Refine Apple devices using hostname if available
                if device_type == "apple_device" and hostname:
                    hostname_lower = hostname.lower()
                    if "iphone" in hostname_lower:
                        return "smartphone"
                    if "ipad" in hostname_lower:
                        return "tablet"
                    if "macbook" in hostname_lower:
                        return "laptop"
                    if "imac" in hostname_lower:
                        return "desktop"
                    if "apple-tv" in hostname_lower or "appletv" in hostname_lower:
                        return "streaming"
                    return "apple_device"
                return device_type

    return "unknown"


def get_device_icon(device_type: str) -> str:
    """Return the icon key for a given device type."""
    return DEVICE_ICONS.get(device_type, "device")
