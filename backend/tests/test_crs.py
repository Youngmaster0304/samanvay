"""The CRS rules from `backend.md` §5.1, including who wins when two disagree."""

import pytest

from app.domain.sources import CrsSource
from app.ingest.crs import resolve_crs
from app.ingest.errors import IngestError


def test_reads_the_crs_from_the_file() -> None:
    decision = resolve_crs(
        file_crs="EPSG:4326", file_crs_hint=CrsSource.FILE, declared_crs=None, has_geometry=True
    )
    assert decision.crs == "EPSG:4326"
    assert decision.source is CrsSource.FILE


def test_normalises_an_authority_code() -> None:
    decision = resolve_crs(
        file_crs="WGS 84",
        file_crs_hint=CrsSource.FILE,
        declared_crs=None,
        has_geometry=True,
    )
    assert decision.crs == "EPSG:4326"


def test_refuses_geometry_without_a_crs() -> None:
    with pytest.raises(IngestError) as excinfo:
        resolve_crs(
            file_crs=None, file_crs_hint=CrsSource.NONE, declared_crs=None, has_geometry=True
        )
    assert excinfo.value.code == "missing_crs"


def test_refuses_a_file_that_disagrees_with_the_declaration() -> None:
    with pytest.raises(IngestError) as excinfo:
        resolve_crs(
            file_crs="EPSG:4326",
            file_crs_hint=CrsSource.FILE,
            declared_crs="EPSG:32643",
            has_geometry=True,
        )
    assert excinfo.value.code == "crs_conflict"


def test_uses_the_declaration_when_the_file_has_none() -> None:
    decision = resolve_crs(
        file_crs=None, file_crs_hint=CrsSource.NONE, declared_crs="EPSG:32643", has_geometry=True
    )
    assert decision.crs == "EPSG:32643"
    assert decision.source is CrsSource.DECLARED
    assert decision.declared == "EPSG:32643"


def test_an_assumed_crs_never_beats_a_declared_one() -> None:
    decision = resolve_crs(
        file_crs="EPSG:4326",
        file_crs_hint=CrsSource.IMPLICIT_WGS84,
        declared_crs="EPSG:4269",
        has_geometry=True,
    )
    assert decision.crs == "EPSG:4269"
    assert decision.source is CrsSource.DECLARED
    # What the file implied is still reported, so the assumption stays visible.
    assert decision.from_file == "EPSG:4326"


def test_an_assumed_crs_is_used_when_nothing_is_declared() -> None:
    decision = resolve_crs(
        file_crs="EPSG:4326",
        file_crs_hint=CrsSource.IMPLICIT_WGS84,
        declared_crs=None,
        has_geometry=True,
    )
    assert decision.crs == "EPSG:4326"
    assert decision.source is CrsSource.IMPLICIT_WGS84


def test_a_table_has_no_crs_and_may_not_be_given_one() -> None:
    decision = resolve_crs(
        file_crs=None, file_crs_hint=CrsSource.NONE, declared_crs=None, has_geometry=False
    )
    assert decision.crs is None
    assert decision.source is CrsSource.NONE

    with pytest.raises(IngestError) as excinfo:
        resolve_crs(
            file_crs=None,
            file_crs_hint=CrsSource.NONE,
            declared_crs="EPSG:32643",
            has_geometry=False,
        )
    assert excinfo.value.code == "crs_not_applicable"


def test_refuses_a_crs_pyproj_does_not_recognise() -> None:
    with pytest.raises(IngestError) as excinfo:
        resolve_crs(
            file_crs=None,
            file_crs_hint=CrsSource.NONE,
            declared_crs="EPSG:999999",
            has_geometry=True,
        )
    assert excinfo.value.code == "invalid_crs"
