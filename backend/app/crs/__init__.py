"""CRS engine: transformations to the storage CRS, rubber-sheeting, feature loading.

Modules:
- `transform`   — build the pyproj transformer plus its PROJ pipeline string.
- `rubber_sheet` — fit the model ladder to control points and pick it by leave-one-out RMSE.
- `service`     — the API-facing operations: fit, reload, health.
- `errors`      — refusals shaped like the ingest ones.
"""
