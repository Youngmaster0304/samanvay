"""What each connector reports back, using files written by the geo stack itself."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from affine import Affine
from shapely.geometry import Polygon

from app.domain.sources import CrsSource, SourceFormat
from app.ingest.connectors import inspect_payload
from app.ingest.errors import IngestError

BLOCK = Polygon(
    [
        (76.7730, 30.7330),
        (76.7740, 30.7330),
        (76.7740, 30.7340),
        (76.7730, 30.7340),
        (76.7730, 30.7330),
    ]
)


def _frame() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"name": ["block 12"]}, geometry=[BLOCK], crs="EPSG:4326")


def test_geojson_reports_geometry_count_and_crs(tmp_path: Path) -> None:
    path = tmp_path / "layer.geojson"
    _frame().to_file(path, driver="GeoJSON")

    inspection = inspect_payload(path, SourceFormat.GEOJSON)

    assert inspection.format is SourceFormat.GEOJSON
    assert inspection.crs == "EPSG:4326"
    assert inspection.crs_hint is CrsSource.FILE
    assert inspection.feature_count == 1
    assert inspection.has_geometry is True
    assert inspection.coverage is not None
    assert len(inspection.coverage) == 4


def test_geotiff_reports_a_structural_cog_failure(tmp_path: Path) -> None:
    path = tmp_path / "ori.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=16,
        width=16,
        count=1,
        dtype="uint8",
        crs="EPSG:32643",
        transform=Affine.translation(360000, 3396000) @ Affine.scale(30, -30),
    ) as dst:
        dst.write(np.ones((16, 16), dtype="uint8"), 1)

    inspection = inspect_payload(path, SourceFormat.GEOTIFF)

    assert inspection.raster is not None
    assert inspection.raster.is_cog is False
    assert inspection.crs == "EPSG:32643"
    assert inspection.has_geometry is True
    assert inspection.feature_count is None
    assert any("Cloud Optimized" in note for note in inspection.notes)


def test_shapefile_without_a_prj_is_reported_as_missing_its_crs(tmp_path: Path) -> None:
    path = tmp_path / "parcels.shp"
    _frame().to_file(path)
    path.with_suffix(".prj").unlink()

    inspection = inspect_payload(path, SourceFormat.SHAPEFILE)

    assert inspection.format is SourceFormat.SHAPEFILE
    assert inspection.crs is None
    assert inspection.has_geometry is True
    assert any("declared_crs is required" in note for note in inspection.notes)


def test_geopackage_reports_every_layer_it_holds(tmp_path: Path) -> None:
    path = tmp_path / "layers.gpkg"
    _frame().to_file(path, layer="parcels", driver="GPKG")
    _frame().to_file(path, layer="roads", driver="GPKG", mode="a")

    inspection = inspect_payload(path, SourceFormat.GPKG)

    assert set(inspection.layers) == {"parcels", "roads"}
    assert inspection.layer in {"parcels", "roads"}
    assert any("layers in this file" in note for note in inspection.notes)


def test_gnss_csv_counts_only_usable_points(tmp_path: Path) -> None:
    path = tmp_path / "points.csv"
    path.write_text(
        "latitude,longitude,note\n"
        "30.7330,76.7794,ok\n"
        "30.7340,76.7800,ok\n"
        ",76.7800,missing latitude\n"
        "130.7,76.7800,out of range\n"
        "abc,76.7800,not a number\n",
        encoding="utf-8",
    )

    inspection = inspect_payload(path, SourceFormat.CSV_GNSS)

    assert inspection.feature_count == 2
    assert inspection.has_geometry is True
    assert inspection.crs == "EPSG:4326"
    assert inspection.crs_hint is CrsSource.IMPLICIT_WGS84
    assert inspection.geometry_types == ["Point"]
    assert inspection.coverage == pytest.approx((76.7794, 30.733, 76.78, 30.734))
    assert any("not counted as points" in note for note in inspection.notes)


def test_projected_gnss_csv_asks_for_a_declared_crs(tmp_path: Path) -> None:
    path = tmp_path / "points.csv"
    path.write_text("easting,northing\n360000,3396000\n", encoding="utf-8")

    inspection = inspect_payload(path, SourceFormat.CSV_GNSS)

    assert inspection.crs is None
    assert inspection.crs_hint is CrsSource.NONE
    assert inspection.feature_count == 1


def test_a_csv_with_no_coordinates_refuses_to_be_a_gnss_export(tmp_path: Path) -> None:
    path = tmp_path / "ror.csv"
    path.write_text("khasra,owner\n12,recorded\n", encoding="utf-8")

    with pytest.raises(IngestError) as excinfo:
        inspect_payload(path, SourceFormat.CSV_GNSS)
    assert excinfo.value.code == "no_coordinate_columns"


def test_a_csv_with_no_usable_points_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "points.csv"
    path.write_text("latitude,longitude\n,\n", encoding="utf-8")

    with pytest.raises(IngestError) as excinfo:
        inspect_payload(path, SourceFormat.CSV_GNSS)
    assert excinfo.value.code == "no_usable_coordinates"


def test_record_of_rights_table_has_no_geometry_and_no_crs(tmp_path: Path) -> None:
    path = tmp_path / "ror.csv"
    path.write_text("khasra,owner,sqm\n12,recorded,505\n13,recorded,505\n", encoding="utf-8")

    inspection = inspect_payload(path, SourceFormat.CSV_ROR)

    assert inspection.has_geometry is False
    assert inspection.crs is None
    assert inspection.feature_count == 2
    assert inspection.attributes == ["khasra", "owner", "sqm"]
    assert any("does not apply" in note for note in inspection.notes)
