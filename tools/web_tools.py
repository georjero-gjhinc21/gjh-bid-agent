"""Web tools — fetch and lightly parse public procurement pages.

V1 just fetches the configured WEB_SOURCES and returns text. V2 will add
a per-source diff (track which links are new since last run).
"""
from __future__ import annotations
import requests
from bs4 import BeautifulSoup

import config
from agents.base import Tool


HEADERS = {
    "User-Agent": "GJH-BidAgent/1.0 (procurement monitoring)",
}


def _fetch_source(state, name: str) -> dict:
    """Fetch one configured web source by name. Returns title + text + links."""
    src = next((s for s in config.WEB_SOURCES if s["name"] == name), None)
    if not src:
        return {"error": f"unknown source: {name}"}
    try:
        r = requests.get(src["url"], headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        return {"error": f"fetch failed: {e}", "url": src["url"]}

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())[:8000]
    links = []
    for a in soup.find_all("a", href=True)[:200]:
        href = a["href"]
        label = a.get_text(strip=True)[:200]
        if label and href:
            links.append({"href": href, "label": label})
    return {
        "url": src["url"],
        "name": src["name"],
        "text": text,
        "links": links[:80],
    }


def _list_web_sources(state) -> list[dict]:
    return [{"name": s["name"], "url": s["url"], "priority": s.get("priority", 5)}
            for s in config.WEB_SOURCES]


list_web_sources = Tool(
    name="list_web_sources",
    description="List the configured public procurement web sources to monitor.",
    input_schema={"type": "object", "properties": {}},
    fn=_list_web_sources,
)

fetch_source = Tool(
    name="fetch_source",
    description=(
        "Fetch a configured web source by name and return cleaned text + "
        "links. Use to detect new solicitations on procurement portals."
    ),
    input_schema={
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string", "description": "Source name from list_web_sources."}
        },
    },
    fn=_fetch_source,
)
