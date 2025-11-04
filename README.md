# Berner Box (Berner Torantriebe) – Home Assistant Custom Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Validate with hassfest](https://github.com/moarph/homeassistant_berner_torantriebe/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/moarph/homeassistant_berner_torantriebe/actions/workflows/hassfest.yaml)

> **Status:** Installable custom integration with UI setup (config flow).  
> Implements covers, buttons, switches (and optional sensors) for the Berner Box.  
> Current data flow is local (HA `iot_class: local_polling`).

---

## Overview

This integration connects the **Berner Box** (Berner Torantriebe) to Home Assistant.  
It aims to monitor and control garage doors and related devices via your local network.

- **Domain**: `bernerbox`  
- **Folder**: `custom_components/bernerbox`

---

## Requirements

- Home Assistant **2024.6.0 or newer**
- **HACS** installed (recommended)

---

## Installation

### A) HACS (recommended)

1. Add this repository as a **Custom Repository** in HACS (category: Integration).  
   **My link:**  
   **[Add this repo to HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=moarph&repository=homeassistant_berner_torantriebe&category=integration)**
2. In HACS → **Integrations** → search for **“Berner Box”** → **Install**.
3. **Restart** Home Assistant.

### B) Manual

1. Download this repository.
2. Copy the folder `custom_components/bernerbox` to:  
   `<config>/custom_components/bernerbox`
3. **Restart** Home Assistant.

---

## Configuration

- Go to **Settings → Devices & Services → Add Integration → “Berner Box”**,  
  or use this My link:  
  **[Start config flow](https://my.home-assistant.io/redirect/config_flow_start/?domain=bernerbox)**
- Enter your **Host/IP**, **Username**, and **Password**.  
  The flow will discover your items and create a config entry.

> Credentials are stored locally in Home Assistant.

---

## Entities (current set)

- **Cover** (`cover`): Garage door control (open/close/stop; state).  
- **Button** (`button`):  
  - “Update all / Refresh”  
  - “Reboot Box”  
  - Per-item “Impulse” (momentary action)
- **Switch** (`switch`): “SSH Access” on/off
- **(Optional) Sensor** (`sensor`): Item states via a shared coordinator  
  > Enable by adding `Platform.SENSOR` to `PLATFORMS` in `__init__.py` if you want sensors visible.

---

## Troubleshooting / FAQ

**I don’t see entities after setup.**  
Make sure the config flow completed and items were found. Then restart Home Assistant.

**My links don’t open in HA.**  
Ensure the **My Home Assistant** helper is enabled (part of `default_config`).

**HACS shows “Custom” badge.**  
That’s expected until the integration is submitted to the HACS store.

---

## Updating

- If you publish GitHub **releases** (e.g., `v1.0.0`), HACS will offer updates via the release tags.  
- Without releases, HACS tracks the latest commit.

---

## Development notes

- Integration domain: `bernerbox` (folder and `manifest.json: "domain": "bernerbox"` must match).
- UI setup via `config_flow.py` (`"config_flow": true` in `manifest.json`).
- Translations can be added in `custom_components/bernerbox/translations/` (e.g., `en.json`, `de.json`).
- For status polling and shared state, a `DataUpdateCoordinator` is used.

---

## License

MIT
