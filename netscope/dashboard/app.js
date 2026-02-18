/**
 * NetScope Dashboard — WebSocket client, Chart.js rendering, theme switching.
 */

// ─── State ──────────────────────────────────────────────────────────────

let devices = [];
let stats = {};
let searchQuery = "";
let filterOnline = false;
let bandwidthChart = null;
let bandwidthHistory = [];

const MAX_CHART_POINTS = 30;

// ─── Theme ──────────────────────────────────────────────────────────────

function getTheme() {
    return document.documentElement.getAttribute("data-theme") || "dark";
}

function setTheme(theme) {
    if (theme === "light") {
        document.documentElement.setAttribute("data-theme", "light");
    } else {
        document.documentElement.removeAttribute("data-theme");
    }
    localStorage.setItem("netscope-theme", theme);
    applyChartTheme();
}

function toggleTheme() {
    setTheme(getTheme() === "dark" ? "light" : "dark");
}

/** Return the current CSS variable values for chart theming. */
function chartColors() {
    const s = getComputedStyle(document.documentElement);
    return {
        grid: s.getPropertyValue("--chart-grid").trim(),
        tick: s.getPropertyValue("--chart-tick").trim(),
        tooltipBg: s.getPropertyValue("--chart-tooltip-bg").trim(),
        tooltipBorder: s.getPropertyValue("--chart-tooltip-border").trim(),
        tooltipTitle: s.getPropertyValue("--text-primary").trim(),
        tooltipBody: s.getPropertyValue("--text-secondary").trim(),
        green: s.getPropertyValue("--green").trim(),
        accent: s.getPropertyValue("--accent").trim(),
    };
}

function applyChartTheme() {
    if (!bandwidthChart) return;
    const c = chartColors();

    bandwidthChart.options.scales.x.grid.color = c.grid;
    bandwidthChart.options.scales.x.ticks.color = c.tick;
    bandwidthChart.options.scales.y.grid.color = c.grid;
    bandwidthChart.options.scales.y.ticks.color = c.tick;
    bandwidthChart.options.plugins.legend.labels.color = c.tick;
    bandwidthChart.options.plugins.tooltip.backgroundColor = c.tooltipBg;
    bandwidthChart.options.plugins.tooltip.titleColor = c.tooltipTitle;
    bandwidthChart.options.plugins.tooltip.bodyColor = c.tooltipBody;
    bandwidthChart.options.plugins.tooltip.borderColor = c.tooltipBorder;

    bandwidthChart.data.datasets[0].borderColor = c.green;
    bandwidthChart.data.datasets[0].backgroundColor = c.green.replace(")", ", 0.08)").replace("rgb", "rgba");
    bandwidthChart.data.datasets[1].borderColor = c.accent;
    bandwidthChart.data.datasets[1].backgroundColor = c.accent.replace(")", ", 0.08)").replace("rgb", "rgba");

    bandwidthChart.update("none");
}

// ─── Device Icons (SVG) ─────────────────────────────────────────────────

const DEVICE_ICONS = {
    phone: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>`,
    tablet: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>`,
    laptop: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="2" y1="20" x2="22" y2="20"/></svg>`,
    desktop: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
    tv: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="15" rx="2" ry="2"/><polyline points="17 2 12 7 7 2"/></svg>`,
    router: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="14" width="20" height="7" rx="2"/><path d="M6.5 14V8a5.5 5.5 0 0 1 11 0v6"/></svg>`,
    printer: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>`,
    speaker: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"/><circle cx="12" cy="14" r="4"/><line x1="12" y1="6" x2="12.01" y2="6"/></svg>`,
    gamepad: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="12" x2="10" y2="12"/><line x1="8" y1="10" x2="8" y2="14"/><line x1="15" y1="13" x2="15.01" y2="13"/><line x1="18" y1="11" x2="18.01" y2="11"/><path d="M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.545-.604-6.584-.685-7.258-.007-.05-.011-.1-.017-.151A4 4 0 0 0 17.32 5z"/></svg>`,
    smart: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>`,
    chip: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>`,
    apple: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2C9.5 2 8 4 8 4s-4-.5-4 4c0 5 4 11 6 13 .5.5 1.5.5 2 0s6-8 6-13c0-4.5-4-4-4-4S14.5 2 12 2z"/></svg>`,
    device: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
};

// ─── Socket.IO Connection ───────────────────────────────────────────────

const socket = io();

socket.on("connect", () => {
    updateConnectionStatus(true);
});

socket.on("disconnect", () => {
    updateConnectionStatus(false);
});

socket.on("device_update", (data) => {
    devices = data.devices || [];
    stats = data.stats || {};
    updateDashboard();
});

// ─── Rendering ──────────────────────────────────────────────────────────

function updateDashboard() {
    updateStats();
    updateDeviceList();
    updateBandwidthChart();
    updateTopDevices();
}

function updateConnectionStatus(connected) {
    const badge = document.getElementById("status-badge");
    if (connected) {
        badge.className = "status-badge online";
        badge.innerHTML = `<span class="status-dot"></span> Monitoring`;
    } else {
        badge.className = "status-badge offline";
        badge.innerHTML = `<span class="status-dot"></span> Disconnected`;
    }
}

function updateStats() {
    document.getElementById("stat-total-devices").textContent =
        stats.total_devices || 0;
    document.getElementById("stat-online-devices").textContent =
        stats.online_devices || 0;
    document.getElementById("stat-total-sent").textContent = formatBytes(
        stats.total_bytes_sent || 0
    );
    document.getElementById("stat-total-recv").textContent = formatBytes(
        stats.total_bytes_recv || 0
    );

    const topEl = document.getElementById("stat-top-device");
    if (stats.top_device) {
        topEl.textContent = `${stats.top_device.hostname} (${formatBytes(stats.top_device.total_bytes)})`;
    } else {
        topEl.textContent = "\u2014";
    }
}

function updateDeviceList() {
    const container = document.getElementById("device-list");
    let filtered = devices;

    if (searchQuery) {
        const q = searchQuery.toLowerCase();
        filtered = filtered.filter(
            (d) =>
                (d.hostname && d.hostname.toLowerCase().includes(q)) ||
                (d.ip && d.ip.includes(q)) ||
                (d.mac && d.mac.toLowerCase().includes(q)) ||
                (d.vendor && d.vendor.toLowerCase().includes(q))
        );
    }

    if (filterOnline) {
        filtered = filtered.filter((d) => d.is_online);
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No devices found</h3>
                <p>${devices.length === 0 ? "Waiting for network traffic\u2026" : "Try adjusting your search or filter."}</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map((d) => deviceCardHTML(d)).join("");
}

function deviceCardHTML(device) {
    const iconKey = getIconKey(device.device_type);
    const iconSVG = DEVICE_ICONS[iconKey] || DEVICE_ICONS.device;
    const statusClass = device.is_online ? "online" : "offline";
    const statusText = device.is_online ? "Online" : "Offline";
    const lastSeen = device.last_seen
        ? timeAgo(new Date(device.last_seen + "Z"))
        : "\u2014";

    return `
        <div class="device-card" data-mac="${device.mac}">
            <div class="device-icon">${iconSVG}</div>
            <div class="device-info">
                <div class="device-name">${escapeHTML(device.hostname || device.mac)}</div>
                <div class="device-meta">
                    <span>${device.ip || "No IP"}</span>
                    <span class="separator">\u00b7</span>
                    <span>${escapeHTML(device.vendor || device.device_type || "Unknown")}</span>
                    <span class="separator">\u00b7</span>
                    <span>${lastSeen}</span>
                </div>
            </div>
            <div class="device-status">
                <span class="online-indicator ${statusClass}">
                    <span class="status-dot"></span> ${statusText}
                </span>
                <div class="device-traffic">
                    <span class="traffic-up" title="Sent">\u2191 ${formatBytes(device.bytes_sent)}</span>
                    <span class="traffic-down" title="Received">\u2193 ${formatBytes(device.bytes_recv)}</span>
                </div>
            </div>
        </div>
    `;
}

function getIconKey(deviceType) {
    const map = {
        smartphone: "phone",
        tablet: "tablet",
        laptop: "laptop",
        desktop: "desktop",
        computer: "desktop",
        apple_device: "apple",
        printer: "printer",
        smart_tv: "tv",
        streaming: "tv",
        gaming: "gamepad",
        speaker: "speaker",
        smart_device: "smart",
        smart_home: "smart",
        router: "router",
        network: "router",
        iot: "chip",
        unknown: "device",
    };
    return map[deviceType] || "device";
}

// ─── Bandwidth Chart ────────────────────────────────────────────────────

function initBandwidthChart() {
    const c = chartColors();
    const ctx = document.getElementById("bandwidth-chart").getContext("2d");

    bandwidthChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "Sent",
                    data: [],
                    borderColor: c.green,
                    backgroundColor: "rgba(48, 209, 88, 0.08)",
                    borderWidth: 1.8,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHitRadius: 8,
                },
                {
                    label: "Received",
                    data: [],
                    borderColor: c.accent,
                    backgroundColor: "rgba(99, 102, 241, 0.08)",
                    borderWidth: 1.8,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHitRadius: 8,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            animation: { duration: 0 },
            plugins: {
                legend: {
                    labels: {
                        color: c.tick,
                        boxWidth: 10,
                        boxHeight: 10,
                        padding: 16,
                        usePointStyle: true,
                        pointStyle: "circle",
                        font: { size: 12, family: "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif" },
                    },
                },
                tooltip: {
                    backgroundColor: c.tooltipBg,
                    titleColor: c.tooltipTitle,
                    bodyColor: c.tooltipBody,
                    borderColor: c.tooltipBorder,
                    borderWidth: 1,
                    cornerRadius: 10,
                    padding: 10,
                    titleFont: { size: 12, weight: "600" },
                    bodyFont: { size: 12 },
                    callbacks: {
                        label: (item) => ` ${item.dataset.label}: ${formatBytes(item.raw)}/s`,
                    },
                },
            },
            scales: {
                x: {
                    grid: { color: c.grid, drawBorder: false },
                    ticks: { color: c.tick, maxTicksLimit: 6, font: { size: 11 } },
                    border: { display: false },
                },
                y: {
                    grid: { color: c.grid, drawBorder: false },
                    ticks: {
                        color: c.tick,
                        font: { size: 11 },
                        callback: (v) => formatBytes(v) + "/s",
                    },
                    border: { display: false },
                    beginAtZero: true,
                },
            },
        },
    });
}

function updateBandwidthChart() {
    if (!bandwidthChart) return;

    const now = new Date();
    const label = now.toLocaleTimeString([], { minute: "2-digit", second: "2-digit" });

    const totalSent = devices.reduce((sum, d) => sum + (d.bytes_sent || 0), 0);
    const totalRecv = devices.reduce((sum, d) => sum + (d.bytes_recv || 0), 0);

    if (bandwidthHistory.length > 0) {
        const prev = bandwidthHistory[bandwidthHistory.length - 1];
        const sentRate = Math.max(0, totalSent - prev.totalSent);
        const recvRate = Math.max(0, totalRecv - prev.totalRecv);

        bandwidthChart.data.labels.push(label);
        bandwidthChart.data.datasets[0].data.push(sentRate);
        bandwidthChart.data.datasets[1].data.push(recvRate);

        if (bandwidthChart.data.labels.length > MAX_CHART_POINTS) {
            bandwidthChart.data.labels.shift();
            bandwidthChart.data.datasets[0].data.shift();
            bandwidthChart.data.datasets[1].data.shift();
        }

        bandwidthChart.update("none");
    }

    bandwidthHistory.push({ totalSent, totalRecv, time: now });
    if (bandwidthHistory.length > MAX_CHART_POINTS + 1) {
        bandwidthHistory.shift();
    }
}

// ─── Top Devices Panel ──────────────────────────────────────────────────

function updateTopDevices() {
    const container = document.getElementById("top-devices-list");
    if (!devices.length) {
        container.innerHTML = `<div class="empty-state"><p>No device data yet</p></div>`;
        return;
    }

    const sorted = [...devices]
        .sort((a, b) => (b.bytes_sent + b.bytes_recv) - (a.bytes_sent + a.bytes_recv))
        .slice(0, 5);

    container.innerHTML = sorted
        .map(
            (d) => `
        <div class="top-device-item">
            <span class="top-device-name">${escapeHTML(d.hostname || d.mac)}</span>
            <span class="top-device-bytes">${formatBytes(d.bytes_sent + d.bytes_recv)}</span>
        </div>
    `
        )
        .join("");
}

// ─── Utilities ──────────────────────────────────────────────────────────

function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const val = bytes / Math.pow(1024, i);
    return `${val.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function timeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 5) return "just now";
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

function escapeHTML(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// ─── Init ───────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    initBandwidthChart();

    // Theme toggle
    document.getElementById("theme-toggle").addEventListener("click", toggleTheme);

    // Search
    document.getElementById("search-input").addEventListener("input", (e) => {
        searchQuery = e.target.value;
        updateDeviceList();
    });

    // Online filter
    const filterBtn = document.getElementById("filter-online-btn");
    filterBtn.addEventListener("click", () => {
        filterOnline = !filterOnline;
        filterBtn.classList.toggle("active", filterOnline);
        filterBtn.textContent = filterOnline ? "Show All" : "Online Only";
        updateDeviceList();
    });
});
