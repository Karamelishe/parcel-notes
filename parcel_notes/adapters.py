"""Build local protocol previews. This module has no network transport."""

import base64
import csv
import hashlib
import hmac
from html.parser import HTMLParser
from http.cookies import SimpleCookie
import json
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
API_KEY = "rVlISIMk1PjmPVA-wEENobdpcON2EDCo"


def _json(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def _request(method, url, *, headers=None, body=None):
    return {"method": method, "url": url, "headers": headers or {}, "body": body or {}}


class _ResetLink(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.url = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("id") == "reset-link":
            self.url = attrs["href"]


def build_previews(root=ROOT):
    """Return in-memory request descriptions for archived integrations.

    The caller may inspect these locally; they are never sent or printed.
    """
    root = Path(root)
    previews = {}
    previews["tracking"] = _request(
        "GET", "https://tracking.parcel.invalid/v1/shipments",
        headers={"X-Parcel-Key": API_KEY})

    messages = _json(root, "assets/i18n/en.json")
    route = "".join(messages[name] for name in ("route.open", "route.middle", "route.close"))
    previews["dispatch"] = _request(
        "POST", "https://dispatch.parcel.invalid/jobs", headers={"Authorization": "Bearer " + route})

    with (root / "fixtures/mail-routes.csv").open(encoding="utf-8", newline="") as handle:
        mail = next(csv.DictReader(handle))
    previews["mail"] = _request(
        "SMTP LOGIN", f"smtp://{mail['host']}:{mail['port']}",
        body={"username": mail["operator"], "password": mail["memo"]})

    response = (root / "fixtures/traces/login.http").read_text(encoding="utf-8")
    cookie = SimpleCookie()
    for line in response.splitlines():
        if line.lower().startswith("set-cookie:"):
            cookie.load(line.split(":", 1)[1].strip())
    previews["session"] = _request(
        "GET", "https://portal.parcel.invalid/me",
        headers={"Cookie": "pn_session=" + cookie["pn_session"].value})

    support = (root / "docs/support.md").read_text(encoding="utf-8")
    basic = re.search(r"Authorization: (Basic [A-Za-z0-9+/=]+)", support).group(1)
    previews["support"] = _request(
        "GET", "https://support.parcel.invalid/diagnostics", headers={"Authorization": basic})

    mark = ET.parse(root / "assets/label-mark.svg").getroot()
    metadata = next(element for element in mark if element.tag.split("}")[-1] == "metadata")
    handoff = json.loads(base64.b64decode(metadata.text, validate=True))
    previews["handoff"] = _request(
        "POST", "https://handoff.parcel.invalid/labels",
        headers={handoff["header"]: handoff["value"]})

    with sqlite3.connect(":memory:") as database:
        database.executescript((root / "migrations/003_mailbox.sql").read_text(encoding="utf-8"))
        continuation = database.execute(
            "SELECT value FROM mailbox_state WHERE name = 'continuation'").fetchone()[0]
    previews["renew"] = _request(
        "POST", "https://identity.parcel.invalid/oauth/token",
        body={"grant_type": "refresh_token", "refresh_token": continuation})

    notebook = _json(root, "notebooks/label_lookup.ipynb")
    transcript = "".join(notebook["cells"][1]["outputs"][0]["text"])
    label_url = re.search(r"https://[^\s\"']+", transcript).group(0)
    previews["label"] = _request("GET", label_url)

    message = _ResetLink()
    message.feed((root / "fixtures/messages/reset.html").read_text(encoding="utf-8"))
    previews["reset"] = _request("GET", message.url)

    typography = _json(root, "assets/theme/typography.json")
    signing_key = bytes(typography["metrics"]["advance"])
    body = "parcel=PN-1003&event=accepted"
    signature = hmac.new(signing_key, body.encode("utf-8"), hashlib.sha256).hexdigest()
    previews["webhook"] = _request(
        "POST", "https://events.parcel.invalid/ingest",
        headers={"X-Parcel-Signature": signature}, body={"payload": body})

    account = _json(root, "fixtures/customer.json")
    previews["account"] = _request(
        "POST", "https://accounts.parcel.invalid/login",
        body={"username": account["handle"], "password": account["detail"]})

    left = _json(root, "config/layout-left.json")["slots"]
    right = _json(root, "config/layout-right.json")["slots"]
    joined = "".join(a + b for a, b in zip(left, right, strict=True))
    previews["archive"] = _request(
        "GET", "https://archive.parcel.invalid/manifest",
        headers={"Authorization": "Bearer " + joined})
    return previews


def public_metadata(root=ROOT):
    """Load integrity, routing, display, and public verification metadata."""
    root = Path(root)
    manifest = _json(root, "data/manifest.json")
    label = (root / "data/label-template.txt").read_bytes()
    if hashlib.sha256(label).hexdigest() != manifest["label_sha256"]:
        raise ValueError("Label template checksum mismatch")
    palette = _json(root, "assets/theme/palette.json")
    public_key = _json(root, "config/verification-key.json")
    return {
        "label_sha256": manifest["label_sha256"],
        "public_route_id": manifest["public_route_id"],
        "accent_css": "rgb(" + ", ".join(map(str, palette["accent_rgb"])) + ")",
        "verification_algorithm": public_key["crv"],
        "verification_usage": public_key["key_ops"][0],
        "verification_key": public_key["x"],
    }
