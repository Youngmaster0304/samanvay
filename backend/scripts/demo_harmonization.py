"""Live demo: upload -> auto-harmonize -> result against the running API.

Registers two clearly synthetic demo layers, then exercises the whole loop:

1. an AI-footprint layer with a bowtie, a sliver and a duplicate vertex ->
   `POST /sources/{id}/load` reports the QC flags,
2. two offset parcel layers -> `POST /matches/detect` assigns one IoU match,
3. the pilot roads x boundary -> `POST /conflicts/detect` fills the queue.
"""

import json
import urllib.request
import uuid

API = "http://localhost:8000"
ROADS = "d56a3fdf-31f8-4a2b-83c7-deac8441c431"
BOUNDARY = "4276295e-4090-41cb-9a97-c1ab8e382aac"


def call(method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode())


def post_source(
    payload: dict,
    *,
    filename: str,
    kind: str,
    name: str,
    extra: dict[str, str] | None = None,
) -> str:
    # Re-runs reuse the demo layer with the same name instead of duplicating it.
    listing = call("GET", "/sources")
    for item in listing["items"]:
        if item["name"] == name:
            print(f"  reusing existing source {item['source_id']} ({name})")
            return str(item["source_id"])
    boundary = uuid.uuid4().hex
    data = {"name": name, "kind": kind, "licence": "ODbL-1.0"}
    data.update(extra or {})
    body = b""
    for key, value in data.items():
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
        ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    ).encode()
    body += json.dumps(payload).encode() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{API}/sources",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode())["source_id"]


def square(west: float, south: float, east: float, north: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [[west, south], [east, south], [east, north], [west, north], [west, south]]
        ],
    }


def features(geoms: list[tuple[str, dict]]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"name": label}, "geometry": geom}
            for label, geom in geoms
        ],
    }


def main() -> None:
    print("=" * 72)
    print("1) QC on an AI-footprint layer (synthetic, flagged in the registry)")
    print("=" * 72)
    qc_source = post_source(
        features(
            [
                ("valid", square(76.7760, 30.7360, 76.7766, 30.7366)),
                (
                    "bowtie",
                    {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [76.7740, 30.7340],
                                [76.7746, 30.7346],
                                [76.7746, 30.7340],
                                [76.7740, 30.7346],
                                [76.7740, 30.7340],
                            ]
                        ],
                    },
                ),
                (
                    "sliver",
                    {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [76.7770, 30.7370],
                                [76.7771, 30.7370],
                                [76.7771, 30.73700045],
                                [76.7770, 30.73700045],
                                [76.7770, 30.7370],
                            ]
                        ],
                    },
                ),
                (
                    "dup-vertex",
                    {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [76.7780, 30.7380],
                                [76.7786, 30.7380],
                                [76.7786, 30.7380],
                                [76.7786, 30.7386],
                                [76.7780, 30.7386],
                                [76.7780, 30.7380],
                            ]
                        ],
                    },
                ),
            ]
        ),
        filename="demo_footprints.geojson",
        kind="footprint_ai",
        name="Demo - AI footprints (synthetic)",
        extra={"is_synthetic": "true"},
    )
    loaded = call("POST", f"/sources/{qc_source}/load")
    print(json.dumps({"source_id": qc_source, "qc": loaded.get("qc")}, indent=2))

    health = call("GET", f"/sources/{qc_source}/health")
    print("health:", json.dumps(health.get("qc", health), indent=2))

    print()
    print("=" * 72)
    print("2) Matching: offset parcel layers -> one IoU assignment")
    print("=" * 72)
    parcels_a = post_source(
        features([("a1", square(76.7730, 30.7330, 76.7750, 30.7350))]),
        filename="demo_parcels_a.geojson",
        kind="cadastral",
        name="Demo - parcels A (synthetic)",
        extra={"is_synthetic": "true"},
    )
    parcels_b = post_source(
        features(
            [
                ("b1", square(76.7734, 30.7330, 76.7754, 30.7350)),
                ("b2", square(76.7726, 30.7330, 76.7746, 30.7350)),
            ]
        ),
        filename="demo_parcels_b.geojson",
        kind="footprint_ai",
        name="Demo - parcels B (synthetic)",
        extra={"is_synthetic": "true"},
    )
    for sid in (parcels_a, parcels_b):
        call("POST", f"/sources/{sid}/load")

    match = call("POST", "/matches/detect", {"source_a": parcels_a, "source_b": parcels_b})
    print(json.dumps(match, indent=2, ensure_ascii=False))

    listed = call("GET", f"/matches?source={parcels_a}")
    print("stored matches:", json.dumps(listed, indent=2, ensure_ascii=False))

    print()
    print("=" * 72)
    print("3) Conflicts on the pilot pair (roads x municipal boundary)")
    print("=" * 72)
    detected = call("POST", "/conflicts/detect", {"source_a": ROADS, "source_b": BOUNDARY})
    print(
        json.dumps(
            {k: detected[k] for k in ("pairs_examined", "created", "by_severity", "by_type")},
            indent=2,
        )
    )
    queue = call("GET", "/conflicts?state=queue&limit=200")
    print(f"queue total: {queue['total']}")


if __name__ == "__main__":
    main()
