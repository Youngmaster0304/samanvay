"use client";

import { useEffect, useRef } from "react";

import "maplibre-gl/dist/maplibre-gl.css";

import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";

/** Bounding box of data/osm/sector22_boundary.geojson (WGS84). */
export const SECTOR22_BBOX: [number, number, number, number] = [
  76.7629635, 30.7263491, 76.7797155, 30.7397398,
];

const OSM_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, ODbL 1.0';

const ESRI_ATTRIBUTION =
  'Tiles © <a href="https://www.esri.com/">Esri</a> — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community';

export type LayerVisibility = {
  satellite: boolean;
  osm: boolean;
  boundary: boolean;
  roads: boolean;
  [key: string]: boolean;
};

/** A registry source drawn from `GET /sources/{id}/features.geojson`. */
export interface DynamicLayer {
  id: string;
  label: string;
  color: string;
  data: GeoJSON.FeatureCollection;
  bbox: [number, number, number, number] | null;
}

/** A raster source shown from `GET /sources/{id}/preview.png` over its WGS 84 bounds. */
export interface ImageLayer {
  id: string;
  label: string;
  url: string;
  bounds: [number, number, number, number];
}

const DYN_SUFFIXES = ["line-casing", "line", "fill", "circle"] as const;

function addImageLayer(
  map: MapLibreMap,
  layer: ImageLayer,
  visible: Record<string, boolean>,
): void {
  const sourceId = `imgsrc-${layer.id}`;
  if (map.getSource(sourceId)) return;
  const [west, south, east, north] = layer.bounds;
  map.addSource(sourceId, {
    type: "image",
    url: layer.url,
    coordinates: [
      [west, north],
      [east, north],
      [east, south],
      [west, south],
    ],
  });
  map.addLayer({
    id: `img-${layer.id}`,
    type: "raster",
    source: sourceId,
    layout: { visibility: (visible[layer.id] ?? true) ? "visible" : "none" },
    paint: { "raster-opacity": 0.95 },
  });
}

function addDynamicLayer(
  map: MapLibreMap,
  layer: DynamicLayer,
  visible: Record<string, boolean>,
): void {
  const sourceId = `dyn-${layer.id}`;
  if (map.getSource(sourceId)) return;
  const shown = (visible[layer.id] ?? true) ? "visible" : "none";
  map.addSource(sourceId, { type: "geojson", data: layer.data });
  // The cream casing is a legibility halo for LINE features only. Polygon
  // outlines skip it: on small polygons the halo swallowed the fill and tiny
  // features read as white discs on the map.
  map.addLayer({
    id: `${sourceId}-line-casing`,
    type: "line",
    source: sourceId,
    layout: { visibility: shown },
    filter: ["==", ["geometry-type"], "LineString"],
    paint: { "line-color": "#fffdf7", "line-width": 3.5, "line-opacity": 0.9 },
  });
  map.addLayer({
    id: `${sourceId}-line`,
    type: "line",
    source: sourceId,
    layout: { visibility: shown },
    paint: { "line-color": layer.color, "line-width": 1.8 },
  });
  map.addLayer({
    id: `${sourceId}-fill`,
    type: "fill",
    source: sourceId,
    layout: { visibility: shown },
    paint: { "fill-color": layer.color, "fill-opacity": 0.14, "fill-outline-color": layer.color },
  });
  map.addLayer({
    id: `${sourceId}-circle`,
    type: "circle",
    source: sourceId,
    layout: { visibility: shown },
    paint: {
      "circle-color": layer.color,
      "circle-radius": 4,
      "circle-stroke-color": "#fffdf7",
      "circle-stroke-width": 1,
    },
  });
}

/**
 * MapLibre wrapper (docs/front.md §5 `MapCanvas`). The default basemap is Esri
 * World Imagery (the workbench reference is a tilted satellite scene); OSM
 * raster stays available as a second basemap row with its ODbL attribution.
 * ORI imagery arrives in Stage 5 and is not simulated here. `fitKey` re-runs
 * the extent fit; the initial view is pitched because the reference is a
 * tilted scene and MapLibre does this honestly for raster data.
 */
export function MapCanvas({
  visible,
  fitKey = 0,
  dynamicLayers = [],
  imageLayers = [],
  fitBounds,
}: {
  visible: Record<string, boolean>;
  fitKey?: number;
  dynamicLayers?: DynamicLayer[];
  imageLayers?: ImageLayer[];
  fitBounds?: [number, number, number, number] | null;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const visibleRef = useRef(visible);
  const dynamicRef = useRef<DynamicLayer[]>(dynamicLayers);
  const imageRef = useRef<ImageLayer[]>(imageLayers);
  const boundsRef = useRef<[number, number, number, number]>(SECTOR22_BBOX);

  useEffect(() => {
    dynamicRef.current = dynamicLayers;
    imageRef.current = imageLayers;
    boundsRef.current = fitBounds ?? SECTOR22_BBOX;
  }, [dynamicLayers, imageLayers, fitBounds]);

  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | null = null;

    void (async () => {
      const maplibregl = await import("maplibre-gl");
      // Turbopack rewrites import.meta.url, so maplibre cannot locate its own
      // worker next to the bundle. The worker is shipped as a static file.
      maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
      if (cancelled || !containerRef.current) return;

      const style: StyleSpecification = {
        version: 8,
        sources: {
          satellite: {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
            maxzoom: 19,
            attribution: ESRI_ATTRIBUTION,
          },
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: OSM_ATTRIBUTION,
          },
          boundary: { type: "geojson", data: "/data/sector22_boundary.geojson" },
          roads: { type: "geojson", data: "/data/sector22_roads.geojson" },
        },
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#1a1712" } },
          {
            id: "osm",
            type: "raster",
            source: "osm",
            layout: { visibility: visibleRef.current.osm ? "visible" : "none" },
            paint: { "raster-opacity": 0.9 },
          },
          {
            id: "satellite",
            type: "raster",
            source: "satellite",
            layout: { visibility: visibleRef.current.satellite ? "visible" : "none" },
            paint: { "raster-opacity": 1 },
          },
          {
            id: "roads-casing",
            type: "line",
            source: "roads",
            layout: { visibility: visibleRef.current.roads ? "visible" : "none" },
            paint: { "line-color": "#fffdf7", "line-width": 3.5, "line-opacity": 0.9 },
          },
          {
            id: "roads",
            type: "line",
            source: "roads",
            layout: { visibility: visibleRef.current.roads ? "visible" : "none" },
            paint: { "line-color": "#8fbf00", "line-width": 1.8 },
          },
          {
            id: "boundary-casing",
            type: "line",
            source: "boundary",
            layout: { visibility: visibleRef.current.boundary ? "visible" : "none" },
            paint: { "line-color": "#fffdf7", "line-width": 6, "line-opacity": 0.9 },
          },
          {
            id: "boundary",
            type: "line",
            source: "boundary",
            layout: { visibility: visibleRef.current.boundary ? "visible" : "none" },
            paint: { "line-color": "#c4183c", "line-width": 2.6 },
          },
        ],
      };

      const created = new maplibregl.Map({
        container: containerRef.current,
        style,
        attributionControl: false,
        maxZoom: 19,
        pitch: 45,
        bearing: -12,
        dragRotate: true,
        touchZoomRotate: true,
      });
      created.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
      created.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
      created.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
      created.fitBounds(boundsRef.current, { padding: 48 });
      for (const layer of dynamicRef.current) {
        addDynamicLayer(created, layer, visibleRef.current);
      }
      for (const layer of imageRef.current) {
        addImageLayer(created, layer, visibleRef.current);
      }
      map = created;
      mapRef.current = created;
    })();

    return () => {
      cancelled = true;
      mapRef.current = null;
      map?.remove();
    };
  }, []);

  useEffect(() => {
    visibleRef.current = visible;
    const map = mapRef.current;
    if (!map) return;
    const pairs: [string, string[]][] = [
      ["satellite", ["satellite"]],
      ["osm", ["osm"]],
      ["boundary", ["boundary", "boundary-casing"]],
      ["roads", ["roads", "roads-casing"]],
    ];
    for (const [key, layerIds] of pairs) {
      for (const id of layerIds) {
        if (map.getLayer(id)) {
          map.setLayoutProperty(id, "visibility", visible[key] ? "visible" : "none");
        }
      }
    }
  }, [visible]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || dynamicLayers.length === 0) return;
    for (const layer of dynamicLayers) {
      addDynamicLayer(map, layer, visible);
      for (const suffix of DYN_SUFFIXES) {
        const id = `dyn-${layer.id}-${suffix}`;
        if (map.getLayer(id)) {
          map.setLayoutProperty(
            id,
            "visibility",
            (visible[layer.id] ?? true) ? "visible" : "none",
          );
        }
      }
    }
  }, [dynamicLayers, visible]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || imageLayers.length === 0) return;
    for (const layer of imageLayers) {
      addImageLayer(map, layer, visible);
      const id = `img-${layer.id}`;
      if (map.getLayer(id)) {
        map.setLayoutProperty(
          id,
          "visibility",
          (visible[layer.id] ?? true) ? "visible" : "none",
        );
      }
    }
  }, [imageLayers, visible]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || fitKey === 0) return;
    map.fitBounds(boundsRef.current, { padding: 48, duration: 600 });
  }, [fitKey]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "absolute",
        inset: 0,
        background: "var(--paper-50)",
        borderRadius: "var(--radius-panel)",
      }}
    />
  );
}
