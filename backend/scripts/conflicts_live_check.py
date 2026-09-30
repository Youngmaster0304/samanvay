"""Live conflict-detection check against the running API (Stage 6 first slice)."""

import json
import os
import urllib.request

API = os.environ.get("SAMANVAY_API", "http://localhost:8000")


def find_source(name: str) -> str:
    for item in call("GET", "/sources")["items"]:
        if item["name"] == name:
            return str(item["source_id"])
    raise SystemExit(f"source not registered: {name}")


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


def main() -> None:
    summary = call(
        "POST",
        "/conflicts/detect",
        {
            "source_a": find_source("OSM Sector 22 roads"),
            "source_b": find_source("OSM Sector 22 municipal boundary"),
        },
    )
    print("detect:", json.dumps(summary, indent=2, ensure_ascii=False))

    queue = call("GET", "/conflicts?state=queue&limit=200")
    print(f"\nqueue total: {queue['total']}")
    for item in queue["items"][:10]:
        measured = item["area_m2"] if item["area_m2"] is not None else item["outside_m"]
        print(
            f"  [{item['severity']}] {item['type']} {item['fid_a']} x {item['fid_b']} "
            f"measured={measured} geometry={item['geometry']['type'] if item['geometry'] else None}"
        )
        print(f"      {item['reason'][:140]}")
    if queue["total"] > 10:
        print(f"  … {queue['total'] - 10} more")


if __name__ == "__main__":
    main()
