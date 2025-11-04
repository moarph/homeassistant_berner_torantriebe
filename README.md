# Berner Box (Berner Torantriebe) – Home Assistant (Custom Integration)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

> **Status:** Funktionsfähige Custom-Integration mit UI-Setup (Config-Flow) und Entitäten (Cover/Buttons/Switch, Sensor/Coordinator).  
> API-Aufrufe erfolgen lokal (iot_class: local_polling).

---

## ✨ Überblick

Diese Integration bindet die **BERNER-BOX** (Berner Torantriebe KG) in Home Assistant ein.  
Unterstützt werden u. a. **Garage-Covers**, **Impuls-Buttons**, ein **SSH-Schalter** und **Status-Sensoren**.

---

## ✅ Voraussetzungen

- Home Assistant **2024.6.0+** (empfohlen)
- **HACS** installiert

---

## 🛠️ Installation (HACS, empfohlen)

1. **Custom Repository hinzufügen**  
   Öffne diesen My-Link und bestätige dein Home-Assistant-System:  
   **[HACS: Repository hinzufügen](https://my.home-assistant.io/redirect/hacs_repository/?owner=moarph&repository=homeassistant_berner_torantriebe&category=integration)**
2. In HACS → **Integrationen** → nach **Berner Box** suchen → **Installieren**.
3. Home Assistant **neu starten**.

### Manuell (ohne HACS)

1. Dieses Repository herunterladen.
2. Den Ordner `custom_components/bernerbox` nach  
   `<config>/custom_components/bernerbox` kopieren.
3. Home Assistant **neu starten**.

---

## ⚙️ Einrichtung

- **Einstellungen → Geräte & Dienste → Integration hinzufügen → „Berner Box“**,  
  oder direkt per My-Link:  
  **[Integration jetzt hinzufügen](https://my.home-assistant.io/redirect/config_flow_start/?domain=bernerbox)**
- Eingaben: **Host/IP** (ohne/mit http), **Benutzername**, **Passwort**.  
  Die Integration ermittelt automatisch `api_key`, `user_id` und die `ids` deiner Items.

---

## 🔧 Entitäten (Überblick)

- **Cover** (`cover`): Garage-Tore (Open/Close).  
- **Button** (`button`):  
  - „Status aktualisieren“ (triggert Update-All + Refresh)
  - „Box neu starten“ (Reboot)
  - „<Item> Impuls“ (Momentkontakt pro Item)
- **Switch** (`switch`): „SSH Zugriff“ (on/off)  
- **Sensor** (`sensor`): Status pro Item via gemeinsamem **Coordinator**

> Die Abfragen & Aktionen laufen gegen die lokalen Box-Endpoints.

---

## 🔄 Updates

- Mit HACS wirst du über neue Versionen informiert (empfohlen: Releases wie `v1.0.0`).

---

## ❓ FAQ

**Ich sehe keine Entitäten?**  
Prüfe, ob der Config-Flow vollständig war und ob Items gefunden wurden. Danach HA neu starten.

**My-Links funktionieren nicht?**  
Stelle sicher, dass die *My Home Assistant*-Integration aktiv ist (Teil von `default_config`).

---

## 🧩 Entwickeln

- Domain/Ordner: `custom_components/bernerbox`  
- Manifest: `manifest.json` enthält u. a. `domain`, `name`, `version`, `documentation`, `issue_tracker`, `codeowners`, `config_flow`.  
- Config-Flow: `config_flow.py` (UI-Setup)  
- Optional: `translations/<lang>.json` für lokalisierte Texte.

---

## 📝 Lizenz

MIT
