"""Live conflict-detection check against the running API (Stage 6 first slice)."""

import json
import urllib.request

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


def main() -> None:
    summary = call(
        "POST",
        "/conflicts/detect",
        {"source_a": ROADS, "source_b": BOUNDARY},
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
