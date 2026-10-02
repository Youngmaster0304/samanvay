import { describe, expect, it } from "vitest";

import {
  crsSourceLabel,
  describeSource,
  formatLabel,
  kindHex,
  kindLabel,
  type Source,
} from "../src/lib/sources";

function baseSource(overrides: Partial<Source>): Source {
  return {
    source_id: "e60246ee-0000-0000-0000-000000000000",
    name: "Test layer",
    kind: "cadastral",
    format: "geojson",
    authority: null,
    licence: "ODbL-1.0",
    url: null,
    vintage: null,
    is_synthetic: false,
    sigma_m: null,
    sha256: "a".repeat(64),
    size_bytes: 2048,
    object_key: "sources/xx/yy",
    crs: "EPSG:4326",
    crs_source: "file",
    crs_original: "EPSG:4326",
    crs_declared: null,
    has_geometry: true,
    feature_count: 10,
    coverage: [76.77, 30.73, 76.78, 30.74],
    attributes: ["khasra"],
    geometry_types: ["Polygon"],
    layer: null,
    layers: ["layer"],
    raster: null,
    notes: ["loaded 10 features into storage CRS EPSG:32643"],
    ingested_at: "2026-10-01T10:00:00",
    ...overrides,
  };
}

describe("describeSource", () => {
  it("describes a vector upload in plain English", () => {
    const text = describeSource(baseSource({})).join(" ");
    expect(text).toContain("GeoJSON file of cadastral data");
    expect(text).toContain("10 feature(s)");
    expect(text).toContain("EPSG:4326 (read from the file itself)");
    expect(text).toContain("Extent from (76.77000, 30.73000)");
    expect(text).toContain("Attributes carried: khasra");
  });

  it("labels synthetic data instead of hiding it", () => {
    const text = describeSource(baseSource({ is_synthetic: true })).join(" ");
    expect(text).toContain("SYNTHETIC");
  });

  it("describes a raster with its pixel facts", () => {
    const text = describeSource(
      baseSource({
        kind: "drone_ori",
        format: "geotiff",
        feature_count: null,
        geometry_types: [],
        attributes: [],
        raster: { width: 3000, height: 3000, bands: 3, resolution: [1, 1] },
      }),
    ).join(" ");
    expect(text).toContain("GeoTIFF raster of drone / ori data");
    expect(text).toContain("3000 × 3000 pixels, 3 band(s)");
    expect(text).toContain("Pixel size 1 × 1");
  });

  it("describes a record table with no geometry", () => {
    const text = describeSource(
      baseSource({
        kind: "revenue",
        format: "csv_ror",
        has_geometry: false,
        crs: null,
        feature_count: 1,
        geometry_types: [],
        attributes: ["khasra", "owner"],
        coverage: null,
      }),
    ).join(" ");
    expect(text).toContain("with 1 row(s) and no geometry");
    expect(text).toContain("No coordinates");
    expect(text).toContain("Columns: khasra, owner");
  });

  it("adds authority and vintage when the API supplied them", () => {
    const text = describeSource(
      baseSource({ authority: "MC Chandigarh", vintage: "2026-01-15", sigma_m: 0.5 }),
    ).join(" ");
    expect(text).toContain("From MC Chandigarh.");
    expect(text).toContain("Vintage 2026-01-15.");
    expect(text).toContain("±0.5 m");
  });
});

describe("kind and format labels", () => {
  it("labels every backend source kind", () => {
    const kinds = [
      "drone_ori",
      "satellite",
      "dsm",
      "dtm",
      "cadastral",
      "revenue",
      "municipal",
      "utility",
      "gnss",
      "footprint_ai",
      "footprint_ref",
    ];
    for (const kind of kinds) {
      expect(kindLabel(kind)).not.toBe(kind);
    }
  });

  it("labels upload formats", () => {
    expect(formatLabel("gpkg")).toBe("GeoPackage");
    expect(formatLabel("shapefile")).toBe("shapefile");
    expect(formatLabel("unknown-fmt")).toBe("unknown-fmt");
  });

  it("explains where the CRS came from", () => {
    expect(crsSourceLabel("declared")).toContain("declared by the uploader");
    expect(crsSourceLabel("implicit_wgs84")).toContain("WGS 84");
  });

  it("returns a hex colour MapLibre can paint with", () => {
    expect(kindHex("footprint_ai")).toMatch(/^#[0-9a-f]{6}$/i);
    expect(kindHex("unknown-kind")).toMatch(/^#[0-9a-f]{6}$/i);
  });
});
