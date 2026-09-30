"""Register a file from the command line, against the configured database and store.

    python -m app.ingest.cli path/to/layer.geojson --name "Sector 22 blocks" \
        --kind cadastral --licence ODbL-1.0

The API is the normal route. This exists so a batch of files can be registered without
an HTTP client, and so the same code path is exercised outside FastAPI.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from app.db.session import SessionLocal
from app.ingest.errors import IngestError
from app.ingest.service import ingest_upload, summarize
from app.ingest.store import get_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ingest.cli",
        description="Register one file in the source registry.",
    )
    parser.add_argument("path", type=Path, help="file to register")
    parser.add_argument("--name", required=True, help="human name for the source")
    parser.add_argument("--kind", required=True, help="source kind, e.g. cadastral")
    parser.add_argument("--licence", required=True, help="licence of the data")
    parser.add_argument("--authority", help="body that published the data")
    parser.add_argument("--url", help="where the data was downloaded from")
    parser.add_argument("--vintage", help="data vintage as an ISO date, e.g. 2024-01-01")
    parser.add_argument("--sigma-m", type=float, help="assumed 1-sigma positional accuracy")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="mark the data as generated rather than observed",
    )
    parser.add_argument("--declared-crs", help="CRS to record when the file carries none")
    parser.add_argument("--layer", help="layer to inspect in a multi-layer file")
    parser.add_argument("--client-key", help="idempotency key for this registration")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.path.is_file():
        print(f"error: {args.path} is not a file", file=sys.stderr)
        return 2

    vintage: date | None = None
    if args.vintage:
        try:
            vintage = date.fromisoformat(args.vintage)
        except ValueError:
            print(f"error: --vintage must be an ISO date, got {args.vintage}", file=sys.stderr)
            return 2

    with open(args.path, "rb") as stream, SessionLocal() as session:
        try:
            result = ingest_upload(
                filename=args.path.name,
                stream=stream,
                name=args.name,
                kind=args.kind,
                licence=args.licence,
                authority=args.authority,
                url=args.url,
                vintage=vintage,
                is_synthetic=args.synthetic,
                sigma_m=args.sigma_m,
                declared_crs=args.declared_crs,
                layer=args.layer,
                client_key=args.client_key,
                session=session,
                store=get_store(),
            )
        except IngestError as exc:
            print(json.dumps({"error": exc.as_detail()}, indent=2), file=sys.stderr)
            return 1

    print(json.dumps(summarize(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
