from __future__ import annotations

from typing import Tuple, List, Dict, Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN


def _normalize_host(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return raw
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw.rstrip("/")
    return f"http://{raw.rstrip('/')}"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    STEP_USER_DATA_SCHEMA = vol.Schema({
        vol.Required("host"): str,                  # z.B. 172.18.1.35 (ohne http)
        vol.Required("username"): str,              # App-Login
        vol.Required("password"): str,              # App-Login
        vol.Optional("request_timeout", default=6): int,  # Sekunden
    })

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors: Dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.STEP_USER_DATA_SCHEMA)

        host_in = str(user_input["host"]).strip()
        username = str(user_input["username"]).strip()
        password = str(user_input["password"]).strip()
        timeout = int(user_input.get("request_timeout", 6))

        if not host_in or not username or not password:
            errors["base"] = "missing_fields"
            return self.async_show_form(step_id="user", data_schema=self.STEP_USER_DATA_SCHEMA, errors=errors)

        host = _normalize_host(host_in)

        # Eindeutige ID pro Host (ein Eintrag pro Box)
        await self.async_set_unique_id(f"{DOMAIN}-{host}")
        self._abort_if_unique_id_configured()

        # 1) Login -> api_key + user_id
        api_key, user_id, err = await self._login_get_key_and_user_id(host, username, password, timeout=max(6, timeout))
        if err or not api_key or user_id is None:
            mapping = {
                "http_401": "invalid_auth",
                "http_403": "invalid_auth",
                "invalid_auth": "invalid_auth",
                "cannot_connect": "cannot_connect",
                "invalid_json": "unknown",
                "no_api_key": "unknown",
                "no_user_id": "unknown",
            }
            errors["base"] = mapping.get(err, "unknown")
            return self.async_show_form(step_id="user", data_schema=self.STEP_USER_DATA_SCHEMA, errors=errors)

        # 2) Items des Users holen -> ids
        ids, err2 = await self._fetch_item_ids(host, api_key, user_id, timeout=max(6, timeout))
        if err2:
            mapping = {
                "cannot_connect": "cannot_connect",
                "invalid_json": "unknown",
                "http_error": "unknown",
            }
            errors["base"] = mapping.get(err2, "unknown")
            return self.async_show_form(step_id="user", data_schema=self.STEP_USER_DATA_SCHEMA, errors=errors)

        if not ids:
            errors["base"] = "no_devices_found"
            return self.async_show_form(step_id="user", data_schema=self.STEP_USER_DATA_SCHEMA, errors=errors)

        data = {
            "host": host,
            "api_key": api_key,
            "user_id": user_id,
            "ids": ids,                     # automatisch ermittelt
            "request_timeout": timeout,
        }
        return self.async_create_entry(title=f"BernerBox ({host})", data=data)

    # ------------------ Helpers ------------------

    async def _login_get_key_and_user_id(
        self, host: str, username: str, password: str, timeout: int = 10
    ) -> Tuple[str | None, int | None, str | None]:
        """
        POST /api/v1/User/authUser -> { status, info }
        info kann Liste oder Objekt sein. Wir extrahieren api_key und id (user_id).
        Rückgabe: (api_key, user_id, error)
        """
        session = async_get_clientsession(self.hass)
        url = f"{host}/api/v1/User/authUser"
        payload = {"username": username, "password": password, "uuid": ""}

        try:
            async with session.post(url, data=payload, timeout=timeout, headers={"Accept": "application/json"}) as resp:
                text = await resp.text()
                if resp.status != 200:
                    return None, None, f"http_{resp.status}"
                try:
                    j = await resp.json(content_type=None)
                except Exception:
                    return None, None, "invalid_json"
        except Exception:
            return None, None, "cannot_connect"

        if not isinstance(j, dict) or j.get("status") != "OK":
            return None, None, "invalid_auth"

        info = j.get("info")
        api_key: str | None = None
        user_id: int | None = None

        def _extract(obj: Dict[str, Any]) -> Tuple[str | None, int | None]:
            ak = obj.get("api_key")
            uid = obj.get("id")
            try:
                uid_int = int(uid) if uid is not None else None
            except Exception:
                uid_int = None
            return (str(ak).strip() if isinstance(ak, str) and ak.strip() else None, uid_int)

        if isinstance(info, list) and info and isinstance(info[0], dict):
            api_key, user_id = _extract(info[0])
        elif isinstance(info, dict):
            api_key, user_id = _extract(info)

        if not api_key:
            return None, None, "no_api_key"
        if user_id is None:
            return None, None, "no_user_id"

        return api_key, user_id, None

    async def _fetch_item_ids(
        self, host: str, api_key: str, user_id: int, timeout: int = 10
    ) -> Tuple[List[int], str | None]:
        """
        GET /api/item/getItemsByUser.json/{user_id}?api_key=KEY -> Liste von Items.
        Wir extrahieren alle id_item als ints, deduplizieren und sortieren.
        """
        session = async_get_clientsession(self.hass)
        url = f"{host}/api/item/getItemsByUser.json/{user_id}?api_key={api_key}"
        try:
            async with session.get(url, timeout=timeout, headers={"Accept": "application/json"}) as resp:
                text = await resp.text()
                if resp.status != 200:
                    return [], "http_error"
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    return [], "invalid_json"
        except Exception:
            return [], "cannot_connect"

        if not isinstance(data, list):
            return [], "invalid_json"

        ids: List[int] = []
        for it in data:
            try:
                iid = int(it.get("id_item"))
                ids.append(iid)
            except Exception:
                continue

        # dedupe + sort
        ids = sorted(set(ids))
        return ids, None
