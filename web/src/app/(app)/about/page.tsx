import { EmptyState } from "@/components/empty-state";

export default function AboutPage() {
  return (
    <>
      <p className="label" style={{ color: "var(--text-muted)", margin: "0 0 4px" }}>
        About
      </p>
      <h1 className="h1" style={{ margin: "0 0 16px" }}>
        What this prototype is
      </h1>

      <div style={{ display: "grid", gap: "20px", maxWidth: "68ch" }}>
        <p className="lead" style={{ margin: 0 }}>
          Samanvay is a hackathon prototype for Smart India Hackathon 2026, problem statement 26013
          (Ministry of Rural Development, Department of Land Resources). It harmonises drone-derived,
          AI-extracted, cadastral, revenue, municipal, utility and GNSS layers over one coordinate
          frame and hands whatever it cannot settle to a human reviewer with the evidence attached.
          It is not an official DoLR, Survey of India or NAKSHA system, and it carries no
          certification, partnership or approval of any kind.
        </p>

        <section className="panel" style={{ padding: "18px 20px" }}>
          <h2 className="h2" style={{ margin: "0 0 8px" }}>
            What it does not do
          </h2>
          <ul style={{ margin: 0, paddingLeft: "20px", display: "grid", gap: "6px" }}>
            <li>It does not determine legal title and does not issue ULPINs. ULPIN is a linked field only.</li>
            <li>It does not average two boundaries. Resolution selects one source&apos;s geometry or goes to a human.</li>
            <li>It never shows a number the backend did not return, and it labels synthetic data as SYNTHETIC.</li>
            <li>Owner details are held outside the OGC APIs and are only readable through a purpose-bound dialog.</li>
          </ul>
        </section>

        <section className="panel" style={{ padding: "18px 20px" }}>
          <h2 className="h2" style={{ margin: "0 0 8px" }}>
            Data and attribution
          </h2>
          <ul style={{ margin: 0, paddingLeft: "20px", display: "grid", gap: "6px" }}>
            <li>
              Map basemap and the Sector 22 boundary, road, land-use, park/green and ward
              extracts are © OpenStreetMap contributors, licensed ODbL 1.0, retrieved 2026-09-30.
              Checksums are recorded in <span className="data">data/osm/manifest.json</span>.
            </li>
            <li>
              Satellite imagery: a real Sentinel-2 L2A scene over Sector 22 (2026-05-18,
              0.0005% cloud) is registered as satellite imagery, its colour bands stretched for
              display — © ESA Copernicus, free use with attribution, delivered through the
              open Element84 Earth Search archive.
            </li>
            <li>
              Elevation: the Copernicus DEM GLO-30 tile covering the pilot (© DLR / ESA,
              TanDEM-X acquisitions 2011–2015, free use with attribution) is registered as a
              real DSM with elevations in metres.
            </li>
            <li>
              Synthetic demo layers (a drone orthophoto, two parcel layers, jittered AI
              footprints) are flagged <strong>SYNTHETIC</strong> in the registry and wherever
              they are drawn; real ORI, cadastral sheets, revenue records and utility maps have
              not been ingested, and those screens stay empty rather than showing stand-ins.
            </li>
          </ul>
        </section>

        <EmptyState
          title="Privacy, terms and contact"
          body="These pages must state in plain language what data the prototype handles, that owner data is access-controlled and logged, and who to contact. They are written with the legal review in Stage 10, not before."
          note="no invented certifications, partnerships or legal claims"
        />
      </div>
    </>
  );
}
