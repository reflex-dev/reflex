"""Browser instrumentation: log every client-storage / cookie write, storage events, ws frames, cookie-sync Set-Cookie."""

import json
import time

INIT = r"""
(() => {
  if (window.__rxInstrumented) return;
  window.__rxInstrumented = true;
  const log = (kind, k, v) => {
    try {
      window.__rxw && window.__rxw(JSON.stringify({kind, k, v: v === undefined || v === null ? null : String(v).slice(0, 120), href: location.pathname + location.search.slice(0, 40)}));
    } catch (e) {}
  };
  const set = Storage.prototype.setItem, rm = Storage.prototype.removeItem, clr = Storage.prototype.clear;
  Storage.prototype.setItem = function (k, v) { log(this === window.localStorage ? 'ls.set' : 'ss.set', k, v); return set.call(this, k, v); };
  Storage.prototype.removeItem = function (k) { log(this === window.localStorage ? 'ls.rm' : 'ss.rm', k); return rm.call(this, k); };
  Storage.prototype.clear = function () { log(this === window.localStorage ? 'ls.clear' : 'ss.clear', '*'); return clr.call(this); };
  const d = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie');
  Object.defineProperty(document, 'cookie', {
    get() { return d.get.call(document); },
    set(v) { log('cookie.set', String(v).split('=')[0], v); return d.set.call(document, v); },
    configurable: true,
  });
  window.addEventListener('storage', (e) => log('storage.event', e.key, e.newValue));
})();
"""

WATCH_KEYS = ("latest_access_token_hash", "is_hydrated", "redirect_to_url", "app_state", "code_verifier", "rejected", "pending_event")


class Recorder:
    """Collect storage writes, ws frames and cookie-sync responses for all pages of a context."""

    def __init__(self, ctx, t0=None):
        self.t0 = t0 or time.time()
        self.events = []
        self.names = {}
        ctx.add_init_script(INIT)
        ctx.expose_binding("__rxw", self._on_write)

    def _now(self):
        return round(time.time() - self.t0, 3)

    def name(self, page, label):
        self.names[id(page)] = label
        page.on("websocket", lambda ws: self._on_ws(page, ws))
        page.on("response", lambda r: self._on_resp(page, r))
        page.on("framenavigated", lambda f: self.events.append({"t": self._now(), "tab": label, "kind": "nav", "v": f.url.split("?")[0]}) if f == page.main_frame else None)

    def _tab(self, page):
        return self.names.get(id(page), "?")

    def _on_write(self, source, payload):
        d = json.loads(payload)
        d["t"] = self._now()
        d["tab"] = self._tab(source["page"])
        self.events.append(d)

    def _on_ws(self, page, ws):
        tab = self._tab(page)

        def recv(payload):
            if not isinstance(payload, str):
                return
            hits = [k for k in WATCH_KEYS if k in payload]
            if hits:
                self.events.append({"t": self._now(), "tab": tab, "kind": "ws.recv", "hits": hits, "v": _ws_digest(payload)})

        def sent(payload):
            if isinstance(payload, str) and ("hydrate" in payload or "logout" in payload or "auth" in payload):
                self.events.append({"t": self._now(), "tab": tab, "kind": "ws.sent", "v": _sent_digest(payload)})

        ws.on("framereceived", recv)
        ws.on("framesent", sent)

    def _on_resp(self, page, r):
        if "/_reflex/cookies/sync" not in r.url:
            return
        try:
            sc = [h["value"] for h in r.headers_array() if h["name"].lower() == "set-cookie"]
        except Exception as exc:  # noqa: BLE001
            sc = [f"<{exc}>"]
        try:
            req_cookie = r.request.all_headers().get("cookie", "")
        except Exception as exc:  # noqa: BLE001
            req_cookie = f"<{exc}>"
        sent = sorted(c.split("=", 1)[0].strip() for c in req_cookie.split(";") if "=" in c and c.split("=", 1)[1].strip())
        self.events.append({
            "t": self._now(), "tab": self._tab(page), "kind": "cookie-sync", "status": r.status,
            "req_cookies_nonempty": sent,
            "set_cookie": [_cookie_digest(c) for c in sc],
        })

    def filtered(self, pred=None):
        return [e for e in self.events if pred is None or pred(e)]


def _cookie_digest(c):
    name, _, rest = c.partition("=")
    val, _, attrs = rest.partition(";")
    al = attrs.lower()
    return {"name": name, "empty": val in ("", '""'), "max_age_0": "max-age=0" in al.replace(" ", ""), "val_len": len(val)}


def _ws_digest(payload):
    """Extract the interesting keys from a socket.io event frame."""
    out = {}
    try:
        start = payload.index("[")
        msg = json.loads(payload[start:])
        body = msg[1] if len(msg) > 1 else {}
        delta = body.get("delta", {}) if isinstance(body, dict) else {}
        for st, vals in delta.items():
            for k, v in vals.items():
                if any(w in k for w in WATCH_KEYS):
                    out[st.rsplit(".", 1)[-1][-40:] + "." + k] = (str(v)[:24] if v else v)
        evs = body.get("events") if isinstance(body, dict) else None
        if evs:
            out["events"] = [e.get("name") for e in evs][:5]
    except Exception as exc:  # noqa: BLE001
        out["raw"] = payload[:200]
        out["err"] = str(exc)
    return out


def _sent_digest(payload):
    try:
        start = payload.index("[")
        msg = json.loads(payload[start:])
        body = msg[1] if len(msg) > 1 else {}
        return {"name": body.get("name"), "payload_keys": sorted((body.get("payload") or {}).keys())}
    except Exception:  # noqa: BLE001
        return payload[:120]
