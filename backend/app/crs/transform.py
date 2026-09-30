"""CRS transformations: source CRS to the storage CRS of the AOI.

`backend.md` §5.2 — build the transformation with pyproj and store the PROJ pipeline
string, so any loaded feature can be traced back to the exact operation that produced
its coordinates. Nothing here chooses a CRS; the decision was made at ingest
(`app.ingest.crs`) and is carried on the registry row.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from app.crs.errors import CrsError


@dataclass(frozen=True)
class CrsTransformation:
    """A ready transformer plus the pipeline string that must be stored with it."""

    transformer: Transformer
    pipeline: str
    source_crs: str
    target_crs: str

    def apply(self, geometry: BaseGeometry) -> BaseGeometry:
        """Reproject one shapely geometry. Axis order is always lon/lat, x/y."""
        if geometry.is_empty:
            return geometry
        return shapely_transform(self.transformer.transform, geometry)


def build_transformation(source_crs: str, target_crs: str) -> CrsTransformation:
    """pyproj transformer between two CRS strings, with its PROJ pipeline string."""
    try:
        source = CRS.from_user_input(source_crs)
        target = CRS.from_user_input(target_crs)
    except CRSError as exc:
        raise CrsError(
            "invalid_crs",
            f"pyproj does not recognise {source_crs!r} or {target_crs!r}: {exc}",
        ) from exc

    transformer = Transformer.from_crs(source, target, always_xy=True)
    pipeline = _pipeline_string(transformer)
    return CrsTransformation(
        transformer=transformer,
        pipeline=pipeline,
        source_crs=source_crs,
        target_crs=target_crs,
    )


def _pipeline_string(transformer: Transformer) -> str:
    """The PROJ pipeline, falling back to the operation description if PROJ omits it."""
    try:
        pipeline = transformer.to_proj4()
    except Exception:  # a CRS that PROJ describes as a single step has no pipeline text
        pipeline = ""
    pipeline = pipeline.strip()
    return pipeline or transformer.description
