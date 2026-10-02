"""Source kinds, ingest formats and the rules that constrain them.

`SourceKind` matches the `kind` comment in the `source_registry` schema in
`backend.md` §4. `SourceFormat` is what the uploaded bytes actually are; a kind and a
format are deliberately separate concepts, because the same kind can arrive as vectors,
as a scanned sheet, or as a table.
"""

from enum import StrEnum


class SourceKind(StrEnum):
    """What a source *is*, from the point of view of the harmonization pipeline."""

    DRONE_ORI = "drone_ori"
    SATELLITE = "satellite"
    DSM = "dsm"
    DTM = "dtm"
    CADASTRAL = "cadastral"
    REVENUE = "revenue"
    MUNICIPAL = "municipal"
    UTILITY = "utility"
    GNSS = "gnss"
    FOOTPRINT_AI = "footprint_ai"
    FOOTPRINT_REF = "footprint_ref"


class SourceFormat(StrEnum):
    """What the uploaded file *is*."""

    GEOTIFF = "geotiff"
    GEOJSON = "geojson"
    GPKG = "gpkg"
    SHAPEFILE = "shapefile"
    CSV_GNSS = "csv_gnss"
    CSV_ROR = "csv_ror"


class CrsSource(StrEnum):
    """Where the coordinate reference system came from; recorded for every source."""

    FILE = "file"
    DECLARED = "declared"
    IMPLICIT_WGS84 = "implicit_wgs84"
    NONE = "none"


RASTER_FORMATS: frozenset[SourceFormat] = frozenset({SourceFormat.GEOTIFF})
VECTOR_FORMATS: frozenset[SourceFormat] = frozenset(
    {SourceFormat.GEOJSON, SourceFormat.GPKG, SourceFormat.SHAPEFILE}
)
GEOMETRY_FORMATS: frozenset[SourceFormat] = VECTOR_FORMATS | {SourceFormat.CSV_GNSS}

# Kinds whose payload shape is constrained. A kind with no entry accepts any supported
# format: a cadastral source may legitimately arrive as vectors or as a scanned sheet.
KIND_FORMAT_RULES: dict[SourceKind, frozenset[SourceFormat]] = {
    SourceKind.SATELLITE: RASTER_FORMATS,
    SourceKind.DSM: RASTER_FORMATS,
    SourceKind.DTM: RASTER_FORMATS,
    SourceKind.GNSS: GEOMETRY_FORMATS,
    SourceKind.FOOTPRINT_AI: VECTOR_FORMATS,
    SourceKind.FOOTPRINT_REF: VECTOR_FORMATS,
}


def allowed_formats_for(kind: SourceKind) -> frozenset[SourceFormat] | None:
    """Formats accepted for `kind`, or None when the kind accepts any format."""
    return KIND_FORMAT_RULES.get(kind)
