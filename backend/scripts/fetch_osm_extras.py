"""Fetch real OSM planning layers for Sector 22: land use, parks, wards (ODbL).

    uv run python scripts/fetch_osm_extras.py            # save data/osm/sector22_*.geojson
    uv run python scripts/fetch_osm_extras.py --refetch  # pull from Overpass again
    SAMANVAY_API=https://samanvay-api-wjkk.onrender.com \
        uv run python scripts/fetch_osm_extras.py --register

Each layer is a separate registered source (kind `municipal`, ODbL-1.0). A
layer with zero matched features is skipped rather than registered empty.
Wards are OSM relations, so that layer assembles closed member ways into
polygon/multipolygon geometry instead of reading single ways.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from demo_drone_flight import post_bytes

BBOX = "30.7263491,76.7629635,30.7397398,76.7797155"  # south, west, north, east
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "osm"
API = os.environ.get("SAMANVAY_API", "http://localhost:8000")
UA = {"User-Agent": "samanvay-sih2026/0.1"}
VINTAGE = "2026-09-30"

# label -> (filename, overpass query, property keys, geometry kind)
LAYERS: dict[str, tuple[str, str, tuple[str, ...], str]] = {
    "Sector 22 land use (OSM)": (
        "sector22_landuse.geojson",
        f'[out:json][timeout:40];way["landuse"]({BBOX});out geom;',
        ("landuse", "name"),
        "ways",
    ),
    "Sector 22 parks and green (OSM)": (
        "sector22_parks.geojson",
        f'[out:json][timeout:40];(way["leisure"~"^(park|garden|playground)$"]({BBOX});'
        f'way["landuse"="grass"]({BBOX});way["natural"="wood"]({BBOX}););out geom;',
        ("leisure", "landuse", "natural", "name"),
        "ways",
    ),
    "Chandigarh wards touching Sector 22 (OSM)": (
        "sector22_wards.geojson",
        f'[out:json][timeout:40];rel["boundary"="administrative"]'
        f'["admin_level"="9"]({BBOX});out ids;',
        ("admin_level", "name"),
        "ward_relations",
    ),
}


def fetch(query: str) -> dict:
    body = urllib.parse.urlencode({"data": query}).encode()
    last_error: Exception | None = None
    for endpoint in ENDPOINTS:
        try:
            request = urllib.request.Request(endpoint, data=body, headers=UA)
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode())
            if "elements" in payload:
                print(f"overpass: {endpoint}")
                return payload
            last_error = RuntimeError(f"no elements key: {payload}")
        except Exception as exc:
            last_error = exc
            print(f"overpass miss ({endpoint}): {exc}")
        time.sleep(2)
    raise SystemExit(f"overpass failed everywhere: {last_error}")


def _ring(geometry: list[dict]) -> list[list[float]] | None:
    if len(geometry) < 4:
        return None
    coords = [[point["lon"], point["lat"]] for point in geometry]
    if coords[0] != coords[-1]:
        return None
    return coords


def assemble_rings(lines: list[list[list[float]]]) -> tuple[list[list[list[float]]], int]:
    """Stitch open OSM boundary ways end-to-end into closed rings.

    Administrative boundary ways are shared between adjacent areas, so a ward
    relation's members are usually open segments. Returns (closed rings, count
    of segments that could not be closed).
    """
    rings: list[list[list[float]]] = []
    remaining = [list(line) for line in lines]
    failed = 0
    while remaining:
        ring = remaining.pop(0)
        extended = True
        while ring[0] != ring[-1] and extended:
            extended = False
            for index, line in enumerate(remaining):
                if line[-1] == ring[0]:
                    ring = line[:-1] + ring
                elif line[0] == ring[0]:
                    ring = list(reversed(line))[:-1] + ring
                elif line[0] == ring[-1]:
                    ring = ring + line[1:]
                elif line[-1] == ring[-1]:
                    ring = ring + list(reversed(line))[1:]
                else:
                    continue
                remaining.pop(index)
                extended = True
                break
        if ring[0] == ring[-1] and len(ring) >= 4:
            rings.append(ring)
        else:
            failed += 1
    return rings, failed


def to_geojson(payload: dict, keys: tuple[str, ...], mode: str) -> tuple[dict, int, int]:
    """Return (collection, skipped, inner_members_dropped)."""
    features = []
    skipped = 0
    inners = 0
    if mode == "relations":
        for relation in payload.get("elements", []):
            tags = relation.get("tags") or {}
            segments: list[list[list[float]]] = []
            for member in relation.get("members", []):
                if member.get("type") != "way":
                    continue
                if member.get("role") == "inner":
                    inners += 1
                    continue
                ring = _ring(member.get("geometry") or [])
                if ring is not None:
                    segments.append(ring)
                    continue
                coords = [[point["lon"], point["lat"]] for point in (member.get("geometry") or [])]
                if len(coords) >= 2:
                    segments.append(coords)
                else:
                    skipped += 1
            outers, failed = assemble_rings(segments)
            skipped += failed
            if not outers:
                skipped += 1
                continue
            properties = {"osm_id": relation["id"]}
            for key in keys:
                if key in tags:
                    properties[key] = tags[key]
            geometry = (
                {"type": "Polygon", "coordinates": [outers[0]]}
                if len(outers) == 1
                else {"type": "MultiPolygon", "coordinates": [[ring] for ring in outers]}
            )
            features.append({"type": "Feature", "properties": properties, "geometry": geometry})
    else:
        for way in payload.get("elements", []):
            if way.get("type") != "way":
                continue
            tags = way.get("tags") or {}
            ring = _ring(way.get("geometry") or [])
            if ring is None:
                skipped += 1
                continue
            properties = {"osm_id": way["id"]}
            for key in keys:
                if key in tags:
                    properties[key] = tags[key]
            features.append(
                {
                    "type": "Feature",
                    "properties": properties,
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                }
            )
    return {"type": "FeatureCollection", "features": features}, skipped, inners


def fetch_ward_geometry(query: str) -> dict:
    """Two-phase: resolve ward relation ids in the bbox, then geometry by id.

    A single `rel[..](bbox);out geom;` query times out on every public
    Overpass endpoint, while both small phases succeed.
    """
    ids_payload = fetch(query)
    ids = [element["id"] for element in ids_payload.get("elements", []) if "id" in element]
    if not ids:
        return {"elements": []}
    listed = ",".join(str(ward_id) for ward_id in ids)
    return fetch(f"[out:json][timeout:60];rel(id:{listed});out geom;")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for label, (filename, query, keys, mode) in LAYERS.items():
        path = OUT_DIR / filename
        if "--refetch" in sys.argv or not path.exists():
            if mode == "ward_relations":
                payload = fetch_ward_geometry(query)
                collection, skipped, inners = to_geojson(payload, keys, "relations")
            else:
                collection, skipped, inners = to_geojson(fetch(query), keys, mode)
            if not collection["features"]:
                print(f"{label}: no matching OSM features in bbox, skipping layer")
                continue
            path.write_text(json.dumps(collection), encoding="utf-8")
            note = f", dropped {inners} inner ring(s)" if inners else ""
            print(
                f"{label}: saved {len(collection['features'])} features to {path} "
                f"(skipped {skipped}{note})"
            )
        else:
            print(f"{label}: reusing {path} (pass --refetch to pull from OSM again)")

        if "--register" in sys.argv:
            source_id = post_bytes(
                path.read_bytes(),
                filename=filename,
                kind="municipal",
                name=label,
                extra={
                    "licence": "ODbL-1.0",
                    "authority": "OpenStreetMap contributors",
                    "url": "https://www.openstreetmap.org/copyright",
                    "vintage": VINTAGE,
                    "is_synthetic": "false",
                },
            )
            print(f"{label}: registered real source {source_id}")


if __name__ == "__main__":
    main()
