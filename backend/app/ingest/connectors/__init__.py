"""Dispatch: a detected format and a file become one `Inspection`."""

from __future__ import annotations

from pathlib import Path

from app.domain.sources import SourceFormat
from app.ingest.connectors.base import Inspection
from app.ingest.connectors.cog import inspect_geotiff
from app.ingest.connectors.csv_gnss import inspect_gnss_csv
from app.ingest.connectors.csv_ror import inspect_ror_csv
from app.ingest.connectors.geojson import inspect_geojson
from app.ingest.connectors.gpkg import inspect_gpkg
from app.ingest.connectors.shp import inspect_shapefile
from app.ingest.errors import IngestError


def inspect_payload(path: Path, fmt: SourceFormat, *, layer: str | None = None) -> Inspection:
    """Inspect `path` as `fmt`, raising a refusal the operator can act on.

    Any exception GDAL or the standard library raises for a malformed file is converted
    to a `IngestError` here, so the API reports a refusal instead of a 500.
    """
    try:
        if fmt is SourceFormat.GEOTIFF:
            return inspect_geotiff(path)
        if fmt is SourceFormat.GEOJSON:
            return inspect_geojson(path, layer=layer)
        if fmt is SourceFormat.GPKG:
            return inspect_gpkg(path, layer=layer)
        if fmt is SourceFormat.SHAPEFILE:
            return inspect_shapefile(path, layer=layer)
        if fmt is SourceFormat.CSV_GNSS:
            return inspect_gnss_csv(path)
        if fmt is SourceFormat.CSV_ROR:
            return inspect_ror_csv(path)
    except IngestError:
        raise
    except Exception as exc:  # a malformed file must be a refusal, not a 500
        raise IngestError(
            "unreadable_file",
            f"{path.name} could not be read as {fmt.value}: {type(exc).__name__}: {exc}",
        ) from exc

    raise IngestError("unsupported_format", f"{fmt.value} has no inspector")


__all__ = ["Inspection", "inspect_payload"]
