"use client";

import { useRef, useState } from "react";

import { KIND_LABELS, uploadSource, type Source } from "@/lib/sources";

const INPUT: React.CSSProperties = {
  minHeight: "36px",
  padding: "0 10px",
  border: "1px solid var(--border-ctl)",
  borderRadius: "var(--radius-control)",
  background: "var(--surface)",
  color: "var(--text)",
  font: "inherit",
  width: "100%",
  boxSizing: "border-box",
};

const FIELD: React.CSSProperties = {
  display: "grid",
  gap: "4px",
  fontSize: "12px",
  color: "var(--text-muted)",
  alignContent: "start",
};

const UPLOAD_KINDS = [
  "cadastral",
  "revenue",
  "municipal",
  "utility",
  "gnss",
  "drone_ori",
  "satellite",
  "dsm",
  "dtm",
  "footprint_ai",
  "footprint_ref",
] as const;

/**
 * Multipart upload to `POST /sources`. The backend registers the bytes,
 * records provenance and auto-loads vector features, so the caller only
 * needs to refetch the registry afterwards.
 */
export function UploadSourcePanel({ onUploaded }: { onUploaded: (source: Source) => void }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<string>("cadastral");
  const [licence, setLicence] = useState("");
  const [authority, setAuthority] = useState("");
  const [vintage, setVintage] = useState("");
  const [declaredCrs, setDeclaredCrs] = useState("");
  const [sigma, setSigma] = useState("");
  const [synthetic, setSynthetic] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }
    if (!name.trim() || !licence.trim()) {
      setError("Name and licence are required — provenance is not optional.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const created = await uploadSource({
        file,
        name: name.trim(),
        kind,
        licence: licence.trim(),
        authority: authority.trim() || undefined,
        vintage: vintage || undefined,
        sigmaM: sigma ? Number(sigma) : undefined,
        isSynthetic: synthetic,
        declaredCrs: declaredCrs.trim() || undefined,
      });
      formRef.current?.reset();
      setFile(null);
      setName("");
      setLicence("");
      setAuthority("");
      setVintage("");
      setDeclaredCrs("");
      setSigma("");
      setSynthetic(false);
      setOpen(false);
      onUploaded(created);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "upload failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="panel" style={{ padding: "14px 16px", marginBottom: "16px" }}>
      <div
        style={{
          display: "flex",
          gap: "12px",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <p className="label" style={{ margin: "0 0 2px", color: "var(--text-muted)" }}>
            Bring your own data
          </p>
          <p className="small" style={{ margin: 0, color: "var(--text-muted)", maxWidth: "78ch" }}>
            Upload a GeoJSON, GeoPackage, shapefile (zip), GeoTIFF or CSV. The API records the
            checksum, CRS and licence, loads vector features into storage, and the layer appears on
            the satellite map. Single files up to 512&nbsp;MB.
          </p>
        </div>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
        >
          {open ? "Close" : "Upload a dataset"}
        </button>
      </div>

      {open && (
        <form
          ref={formRef}
          onSubmit={(event) => void submit(event)}
          style={{ display: "grid", gap: "12px", marginTop: "14px" }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
              gap: "12px",
            }}
          >
            <label style={FIELD}>
              File *
              <input
                type="file"
                accept=".geojson,.json,.gpkg,.shp,.zip,.tif,.tiff,.csv"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                required
                style={{ ...INPUT, padding: "7px 8px" }}
              />
            </label>
            <label style={FIELD}>
              Dataset name *
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Sector 22 ward blocks"
                required
                style={INPUT}
              />
            </label>
            <label style={FIELD}>
              Kind *
              <select value={kind} onChange={(event) => setKind(event.target.value)} style={INPUT}>
                {UPLOAD_KINDS.map((value) => (
                  <option key={value} value={value}>
                    {KIND_LABELS[value] ?? value}
                  </option>
                ))}
              </select>
            </label>
            <label style={FIELD}>
              Licence *
              <input
                value={licence}
                onChange={(event) => setLicence(event.target.value)}
                placeholder="e.g. ODbL-1.0"
                required
                style={INPUT}
              />
            </label>
            <label style={FIELD}>
              Authority
              <input
                value={authority}
                onChange={(event) => setAuthority(event.target.value)}
                placeholder="e.g. MC Chandigarh"
                style={INPUT}
              />
            </label>
            <label style={FIELD}>
              Vintage
              <input
                type="date"
                value={vintage}
                onChange={(event) => setVintage(event.target.value)}
                style={INPUT}
              />
            </label>
            <label style={FIELD}>
              Declared CRS
              <input
                value={declaredCrs}
                onChange={(event) => setDeclaredCrs(event.target.value)}
                placeholder="EPSG:32643 (blank = read from file)"
                style={INPUT}
              />
            </label>
            <label style={FIELD}>
              Sigma (m)
              <input
                type="number"
                step="0.1"
                min="0"
                value={sigma}
                onChange={(event) => setSigma(event.target.value)}
                placeholder="e.g. 0.5"
                style={INPUT}
              />
            </label>
          </div>

          <label className="small" style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <input
              type="checkbox"
              checked={synthetic}
              onChange={(event) => setSynthetic(event.target.checked)}
            />
            Synthetic data — generated for testing, not a real survey
          </label>

          {error && (
            <p className="small" role="alert" style={{ color: "var(--status-needs-review)", margin: 0 }}>
              {error}
            </p>
          )}

          <div>
            <button type="submit" className="btn btn--primary" disabled={pending}>
              {pending ? "Registering…" : "Register & load"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
