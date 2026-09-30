"""Fetch real OSM building footprints for Sector 22 (ODbL) and optionally register them.

    uv run python scripts/fetch_osm_buildings.py          # save data/osm/sector22_buildings.geojson
    uv run python scripts/fetch_osm_buildings.py --register   # ...and POST it to the running API

Query is overpass `way["building"]` clipped to the same bbox the map uses
(76.7629635, 30.7263491, 76.7797155, 30.7397398). OSM data is ODbL 1.0.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BBOX = "30.7263491,76.7629635,30.7397398,76.7797155"  # south, west, north, east
WEST, SOUTH, EAST, NORTH = "76.7629635", "30.7263491", "76.7797155", "30.7397398"
QUERY = f'[out:json][timeout:40];way["building"]({BBOX});out geom;'
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OSM_API = f"https://api.openstreetmap.org/api/0.6/map?bbox={WEST},{SOUTH},{EAST},{NORTH}"
OUT = Path(__file__).resolve().parents[1] / "data" / "osm" / "sector22_buildings.geojson"
API = os.environ.get("SAMANVAY_API", "http://localhost:8000")
UA = {"User-Agent": "samanvay-sih2026/0.1"}


def fetch() -> dict:
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    overpass_error: Exception | None = None
    for endpoint in ENDPOINTS:
        try:
            request = urllib.request.Request(endpoint, data=body, headers=UA)
            with urllib.request.urlopen(request, timeout=45) as response:
                print(f"overpass: {endpoint}")
                return json.loads(response.read().decode())
        except Exception as exc:
            overpass_error = exc
            print(f"overpass miss ({endpoint}): {exc}")

    # Fallback: the plain OSM API returns every object in the bbox as XML.
    print("falling back to api.openstreetmap.org /map")
    request = urllib.request.Request(OSM_API, headers=UA)
    with urllib.request.urlopen(request, timeout=90) as response:
        root = ET.fromstring(response.read())
    nodes = {
        el.get("id"): (float(el.get("lat", "0")), float(el.get("lon", "0")))
        for el in root.findall("node")
    }
    elements = []
    for way in root.findall("way"):
        tags = {tag.get("k"): tag.get("v") for tag in way.findall("tag")}
        if "building" not in tags:
            continue
        geometry = []
        for ref in way.findall("nd"):
            position = nodes.get(ref.get("ref"))
            if position is None:
                geometry = []
                break
            geometry.append({"lat": position[0], "lon": position[1]})
        if not geometry:
            continue
        elements.append(
            {"type": "way", "id": int(way.get("id", 0)), "tags": tags, "geometry": geometry}
        )
    if not elements:
        raise SystemExit(f"no building ways found (overpass error was: {overpass_error})")
    return {"elements": elements}


def to_geojson(payload: dict) -> tuple[dict, int]:
    features = []
    skipped = 0
    for way in payload.get("elements", []):
        if way.get("type") != "way":
            continue
        tags = way.get("tags") or {}
        geometry = way.get("geometry") or []
        if len(geometry) < 4:
            skipped += 1
            continue
        coords = [[point["lon"], point["lat"]] for point in geometry]
        if coords[0] != coords[-1]:
            # A building way that is not closed: OSM says it is incomplete, so drop it
            # rather than guess a ring.
            skipped += 1
            continue
        properties = {"osm_id": way["id"], "building": tags.get("building", "yes")}
        if "name" in tags:
            properties["name"] = tags["name"]
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": {"type": "Polygon", "coordinates": [coords]},
            }
        )
    return (
        {"type": "FeatureCollection", "features": features},
        skipped,
    )


def register() -> str:
    payload = OUT.read_bytes()
    boundary = "osmbuildings22"
    data = {
        "name": "Sector 22 buildings (OSM)",
        "kind": "footprint_ref",
        "licence": "ODbL-1.0",
        "vintage": "2026-09-30",
    }
    body = b""
    field = '--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
    for key, value in data.items():
        rendered = field.format(b=boundary, k=key, v=value)
        body += rendered.encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="sector22_buildings.geojson"\r\nContent-Type: application/octet-stream\r\n\r\n'
    ).encode()
    body += payload + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{API}/sources",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode())
    return str(result["source_id"])


def main() -> None:
    if "--refetch" in sys.argv or not OUT.exists():
        payload = fetch()
        collection, skipped = to_geojson(payload)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(collection), encoding="utf-8")
        print(
            f"saved {len(collection['features'])} closed building rings to {OUT} "
            f"(skipped {skipped})"
        )
    else:
        print(f"reusing {OUT} (pass --refetch to pull from OSM again)")

    if "--register" in sys.argv:
        # Re-registering the same name is fine for the demo: the registry keys on the
        # upload, and the load is idempotent per source id.
        source_id = register()
        print(f"registered real source {source_id}")


if __name__ == "__main__":
    main()
