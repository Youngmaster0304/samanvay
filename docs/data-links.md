# Samanvay — direct links

Everything referenced in the video/demo, in one place.

## Data (COGs used by the fetch scripts)

| What | Link |
|---|---|
| Sentinel-2 red (B04) | https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/43/R/FQ/2026/5/S2B_43RFQ_20260518_1_L2A/B04.tif |
| Sentinel-2 green (B03) | https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/43/R/FQ/2026/5/S2B_43RFQ_20260518_1_L2A/B03.tif |
| Sentinel-2 blue (B02) | https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/43/R/FQ/2026/5/S2B_43RFQ_20260518_1_L2A/B02.tif |
| Copernicus DEM GLO-30 tile (38 MB, HTTP 200 verified) | https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N30_00_E076_00_DEM/Copernicus_DSM_COG_10_N30_00_E076_00_DEM.tif |
| STAC search that discovers them (`fetch_sentinel2.py`) | https://earth-search.aws.element84.com/v1/search |

Scene: `S2B_43RFQ_20260518_1_L2A`, captured 2026-05-18, cloud 0.000472%.

## Project

| What | Link |
|---|---|
| Live web app | https://samanvay-youngmaster0304s-projects.vercel.app |
| Live API | https://samanvay-api-wjkk.onrender.com |
| API readiness | https://samanvay-api-wjkk.onrender.com/readyz |
| Repository | https://github.com/Youngmaster0304/samanvay |

## Attribution

- Sentinel-2 imagery: © ESA / Copernicus, free use with attribution (AWS Element84 Earth Search archive)
- Elevation: Copernicus DEM GLO-30 © DLR / ESA (TanDEM-X 2011–2015), free use with attribution
- Vector layers: © OpenStreetMap contributors, ODbL 1.0
