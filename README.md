# Berner Box – Home Assistant Integration

[![GitHub release](https://img.shields.io/github/v/release/moarph/homeassistant_berner_torantriebe.svg?style=for-the-badge&logo=github)](https://github.com/moarph/homeassistant_berner_torantriebe/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Integration-41BDF5.svg?style=for-the-badge&logo=homeassistant)](https://hacs.xyz)
[![Validate with hassfest](https://github.com/moarph/homeassistant_berner_torantriebe/actions/workflows/hassfest.yaml/badge.svg?branch=main)](https://github.com/moarph/homeassistant_berner_torantriebe/actions/workflows/hassfest.yaml)
[![HACS validation](https://github.com/moarph/homeassistant_berner_torantriebe/actions/workflows/hacs.yaml/badge.svg?branch=main)](https://github.com/moarph/homeassistant_berner_torantriebe/actions/workflows/hacs.yaml)

> **Official HACS integration** for connecting the *Berner Box* garage door system with Home Assistant.  
> Developed and maintained independently by [@moarph](https://github.com/moarph).  
> All communication runs locally – no cloud connection required.

---

## Overview

This integration connects your **Berner Box** (by Berner Torantriebe KG) to Home Assistant.  
It enables monitoring and control of garage doors and related devices over your local network.

- **Integration domain**: `bernerbox`  
- **Folder**: `custom_components/bernerbox`  
- **Connection type**: Local (`iot_class: local_polling`)

---

## Requirements

- Home Assistant **2024.6.0 or newer**
- **HACS** installed

---

## Installation

### Through HACS (recommended)

1. Open **HACS → Integrations → Search for “Berner Box”**  
   or go directly via this link:  
   👉 [Open in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=moarph&repository=homeassistant_berner_torantriebe&category=integration)
2. Click **Download / Install**.
3. **Restart** Home Assistant.

> This integration is officially distributed via HACS.  
> Manual installation is only necessary for development purposes.

---

## Configuration

- Go to **Settings → Devices & Services → Add Integration → “Berner Box”**,  
  or click this My-link:  
  👉 [Start Config Flow](https://my.home-assistant.io/redirect/config_flow_start/?domain=bernerbox)
- Enter your **Box IP or hostname**, **username**, and **password**.
- The integration will automatically discover and configure your devices.

> Your credentials are stored locally inside Home Assistant.

---

## Entities

| Platform | Description |
|-----------|--------------|
| **Cover** | Control garage doors (open, close, stop) |
| **Button** | Manual actions like “Impulse”, “Reboot”, or “Update all” |
| **Switch** | Toggle SSH access |
| **Sensor** | Optional status sensors (can be enabled via `Platform.SENSOR`) |

---

## Troubleshooting

**No entities appear after setup?**  
Make sure the configuration flow finished successfully and restart Home Assistant.

**My-links don’t open in HA.**  
Ensure the *My Home Assistant* helper is active (part of `default_config`).

---

## Development notes

- **Domain:** `bernerbox`  
- **Config Flow:** enabled (`config_flow: true`)  
- **Structure:** `custom_components/bernerbox/`  
- **Coordinator:** shared `DataUpdateCoordinator` for item status polling  
- **Brand assets:** hosted in [home-assistant/brands](https://github.com/home-assistant/brands/tree/master/custom_integrations/bernerbox)  

---

## License

MIT © [@moarph](https://github.com/moarph)

---

## Disclaimer

This integration is **not affiliated with, endorsed by, or supported by Berner Torantriebe KG**.  
It is an **independent open-source project**, officially listed in the **HACS registry**.  
Use at your own discretion.

---

### 🏷 Version
Current release: ![GitHub release](https://img.shields.io/github/v/release/moarph/homeassistant_berner_torantriebe.svg?label=Latest%20Release)
