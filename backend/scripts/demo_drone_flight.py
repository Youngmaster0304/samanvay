"""Live demo: a clearly SYNTHETIC drone orthophoto + AI footprints over Sector 22.

What it builds (all synthetic, flagged ``is_synthetic=true`` in the registry):

1. a 1 m/px RGB GeoTIFF "orthophoto": a noise terrain tinted with park greens,
   OSM roads widened into asphalt strips, OSM buildings rasterised with
   per-building roof colours and a small cast shadow. It exists to exercise the
   raster path end to end (registry -> WGS 84 preview -> image layer on the map),
   NOT to impersonate a real survey.
2. a ``footprint_ai`` layer: a seeded subset of the OSM building footprints with
   a metre-scale position jitter (the original polygon is kept when the jitter
   would make it invalid).

Run against any API:

    uv run python scripts/demo_drone_flight.py                      # build only, no upload
    SAMANVAY_API=https://samanvay-api-wjkk.onrender.com \
        uv run python scripts/demo_drone_flight.py                  # register on the live API
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path

import numpy as np
from demo_harmonization import call
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import transform_geom
from shapely import affinity
from shapely.geometry import shape

API = os.environ.get("SAMANVAY_API", "http://localhost:8000")
DATA = Path(__file__).resolve().parents[2] / "data" / "osm"
BACKEND_DATA = Path(__file__).resolve().parents[1] / "data" / "osm"
ROADS_PATH = DATA / "sector22_roads.geojson"
BUILDINGS_PATH = BACKEND_DATA / "sector22_buildings.geojson"

# The same bbox the map uses (WGS 84).
WEST, SOUTH, EAST, NORTH = 76.7629635, 30.7263491, 76.7797155, 30.7397398
EPSG = 32643
RES = 1.0  # metres per pixel
SEED = 2026

ORTHO_NAME = "SYNTHETIC demo drone orthophoto (Sector 22)"
FOOTPRINT_NAME = "SYNTHETIC demo AI footprints (OSM-derived, jittered)"


def post_bytes(
    data: bytes, *, filename: str, kind: str, name: str, extra: dict[str, str] | None = None
) -> str:
    """Register raw bytes as a source.

    Always POSTs: the server dedups by content hash and, when its ephemeral
    bucket lost the stored bytes, restores them on that reuse. A same-named
    source with different content is superseded (deleted) first, so a rebuild
    does not leave two rows with one name.
    """
    local_sha = hashlib.sha256(data).hexdigest()
    for item in call("GET", "/sources")["items"]:
        if item["name"] != name:
            continue
        if item["sha256"] == local_sha:
            print(f"  {name}: same bytes as {item['source_id']}, POSTing to heal/confirm")
        else:
            print(f"  {name}: superseding {item['source_id']} (content changed)")
            call("DELETE", f"/sources/{item['source_id']}")
        break
    fields = {"name": name, "kind": kind, "licence": "CC0-1.0"}
    fields.update(extra or {})
    boundary = uuid.uuid4().hex
    body = b""
    for key, value in fields.items():
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
        ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    ).encode()
    body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{API}/sources",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return str(json.loads(response.read().decode())["source_id"])


def _shift_in(mask: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Shift a mask inward (no wrap-around) so edges do not smear to the border."""
    out = np.zeros_like(mask)
    height, width = mask.shape
    ys, ye = max(dy, 0), min(height + dy, height)
    xs, xe = max(dx, 0), min(width + dx, width)
    out[ys - dy : ye - dy, xs - dx : xe - dx] = mask[ys:ye, xs:xe]
    return out


def _thicken(mask: np.ndarray, radius: int) -> np.ndarray:
    thick = mask.copy()
    for k in range(1, radius + 1):
        for dy in (-k, 0, k):
            for dx in (-k, 0, k):
                if dx or dy:
                    thick |= _shift_in(mask, dy, dx)
    return thick


def _load_features(path: Path) -> list[dict]:
    collection = json.loads(path.read_text(encoding="utf-8"))
    return [f for f in collection["features"] if f.get("geometry")]


def build_orthophoto() -> bytes:
    """Render the synthetic ortho and return it as GeoTIFF bytes."""
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{EPSG}", always_xy=True)
    x0, y0 = transformer.transform(WEST, SOUTH)
    x1, y1 = transformer.transform(EAST, NORTH)
    west, east = min(x0, x1), max(x0, x1)
    south, north = min(y0, y1), max(y0, y1)
    width = math.ceil((east - west) / RES)
    height = math.ceil((north - south) / RES)
    transform = from_origin(west, north, RES, RES)
    print(f"raster: {width}x{height} px @ {RES} m, EPSG:{EPSG}")

    rng = np.random.default_rng(SEED)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)

    # Terrain: a mid-grey earth base with soft patches and sensor grain.
    field = np.zeros((height, width), dtype=np.float32)
    for _ in range(48):
        cx, cy = rng.uniform(0, width), rng.uniform(0, height)
        radius = rng.uniform(80, 320)
        amplitude = rng.uniform(-18, 18)
        d2 = (xx - cx) ** 2 + (yy - cy) ** 2
        field += amplitude * np.exp(-d2 / (2.0 * (radius / 2.0) ** 2))
    ground = np.clip(128.0 + field, 40, 230)
    rgb = np.repeat(ground[None, :, :], 3, axis=0)
    rgb[1] = np.clip(ground * 1.02, 0, 255)  # faint vegetation tint in green

    # Park greens: a handful of soft green blobs (Chandigarh's tree cover).
    park = np.zeros((height, width), dtype=np.float32)
    for _ in range(12):
        cx, cy = rng.uniform(0, width), rng.uniform(0, height)
        radius = rng.uniform(40, 160)
        d2 = (xx - cx) ** 2 + (yy - cy) ** 2
        park = np.maximum(park, np.exp(-d2 / (2.0 * (radius / 2.5) ** 2)))
    alpha = np.clip(park * 1.4, 0, 0.9)[None, :, :]
    green = np.array([58.0, 118.0, 58.0], dtype=np.float32)[:, None, None]
    rgb = rgb * (1.0 - alpha) + green * alpha

    # Roads: OSM linework, widened into asphalt strips, painted mid-grey.
    roads = [
        (transform_geom("EPSG:4326", f"EPSG:{EPSG}", f["geometry"]), 1)
        for f in _load_features(ROADS_PATH)
        if f["geometry"]["type"] in ("LineString", "MultiLineString")
    ]
    road_mask = rasterize(
        roads,
        out_shape=(height, width),
        transform=transform,
        all_touched=True,
        dtype="uint8",
    ).astype(bool)
    thick_roads = _thicken(road_mask, radius=3)
    asphalt = np.array([150.0, 148.0, 145.0], dtype=np.float32)[:, None, None]
    rgb = np.where(thick_roads[None, :, :], asphalt, rgb)

    # Buildings: rasterised per feature so each roof gets its own colour.
    buildings = _load_features(BUILDINGS_PATH)
    shapes = []
    for feature in buildings:
        geom = feature["geometry"]
        if geom["type"] != "Polygon":
            continue
        geom = transform_geom("EPSG:4326", f"EPSG:{EPSG}", geom)
        if not shape(geom).is_valid:
            geom = shape(geom).buffer(0).__geo_interface__
        shapes.append((geom, len(shapes) + 1))
    index = rasterize(
        shapes,
        out_shape=(height, width),
        transform=transform,
        all_touched=True,
        dtype="uint32",
    )
    roof_palette = np.array(
        [
            [176, 96, 70],
            [196, 178, 160],
            [150, 148, 146],
            [120, 118, 116],
            [206, 200, 190],
            [168, 140, 120],
            [110, 130, 150],
        ],
        dtype=np.float32,
    )
    chosen = rng.integers(0, len(roof_palette), size=len(shapes) + 1)
    roof_lut = roof_palette[chosen] + rng.normal(0, 5, size=(len(shapes) + 1, 3)).astype(np.float32)
    roof_lut[0] = 0.0

    building_mask = index > 0
    shadow = _shift_in(building_mask, 3, 3) & ~building_mask
    rgb[:, shadow] = rgb[:, shadow] * 0.55
    rgb = np.where(building_mask[None, :, :], roof_lut[index].transpose(2, 0, 1), rgb)

    rgb = rgb + rng.normal(0, 3.0, size=rgb.shape).astype(np.float32)
    pixels = np.clip(rgb, 0, 255).astype("uint8")

    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff",
            width=width,
            height=height,
            count=3,
            dtype="uint8",
            crs=f"EPSG:{EPSG}",
            transform=transform,
            compress="deflate",
        ) as dst:
            dst.write(pixels)
        return memfile.read()


def build_footprints() -> bytes:
    """A jittered, seeded subset of the OSM footprints, as GeoJSON bytes."""
    rng = np.random.default_rng(SEED)
    buildings = [f for f in _load_features(BUILDINGS_PATH) if f["geometry"]["type"] == "Polygon"]
    size = min(60, len(buildings))
    picked = rng.choice(len(buildings), size=size, replace=False)
    features = []
    kept_original = 0
    for position, i in enumerate(sorted(int(p) for p in picked)):
        source = buildings[i]
        jitter_m = rng.normal(0.0, 1.5, size=2)
        dx = jitter_m[0] / (111_320.0 * math.cos(math.radians(SOUTH)))
        dy = jitter_m[1] / 110_574.0
        moved = affinity.translate(shape(source["geometry"]), xoff=dx, yoff=dy)
        if not moved.is_valid:
            moved = shape(source["geometry"])
            kept_original += 1
        properties = dict(source.get("properties") or {})
        properties["extractor_conf"] = round(float(rng.uniform(0.62, 0.94)), 2)
        properties["demo_index"] = position
        features.append(
            {"type": "Feature", "properties": properties, "geometry": moved.__geo_interface__}
        )
    print(f"footprints: {len(features)} features ({kept_original} kept un-jittered)")
    return json.dumps(
        {"type": "FeatureCollection", "features": features}, separators=(",", ":")
    ).encode()


def main() -> None:
    ortho = build_orthophoto()
    footprints = build_footprints()
    if "--build-only" in sys.argv:
        tmp = Path(tempfile.gettempdir())
        (tmp / "samanvay_demo_ortho.tif").write_bytes(ortho)
        (tmp / "samanvay_demo_footprints.geojson").write_bytes(footprints)
        print(f"build-only: wrote {len(ortho)} bytes / {len(footprints)} bytes to {tmp}")
        return

    print(f"uploading to {API} ...")
    ortho_id = post_bytes(
        ortho,
        filename="sector22_synthetic_ortho.tif",
        kind="drone_ori",
        name=ORTHO_NAME,
        extra={
            "is_synthetic": "true",
            "authority": "SYNTHETIC - generated by scripts/demo_drone_flight.py",
            "vintage": "2026-09-30",
        },
    )
    print(f"  ortho source_id = {ortho_id}")
    print(f"  preview: {API}/sources/{ortho_id}/preview.png")

    footprints_id = post_bytes(
        footprints,
        filename="sector22_demo_footprints.geojson",
        kind="footprint_ai",
        name=FOOTPRINT_NAME,
        extra={
            "is_synthetic": "true",
            "licence": "ODbL-1.0",
            "authority": "OpenStreetMap - jittered synthetic variant",
            "vintage": "2026-09-30",
        },
    )
    loaded = call("POST", f"/sources/{footprints_id}/load")
    print(f"  footprints source_id = {footprints_id}")
    print(f"  QC: {json.dumps(loaded.get('qc', {}), indent=2)}")
    print(f"  features: {API}/sources/{footprints_id}/features.geojson")


if __name__ == "__main__":
    main()
