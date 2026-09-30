# MinIO + mc for the Render deployment (compose uses bitnamilegacy/minio directly).
# The stock image never creates the app bucket and Render free services have no
# persistent disk, so the entrypoint starts the server, waits for health, then
# (re)creates the bucket on every boot.
FROM bitnamilegacy/minio:latest

USER root
COPY deploy/minio/init.sh /init.sh

ENTRYPOINT ["/bin/sh", "/init.sh"]
