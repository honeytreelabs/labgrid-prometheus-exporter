# Builds the labgrid-prometheus-exporter image for one backend variant at a
# time (BACKEND=grpc or BACKEND=wamp) -- matching the "one backend per
# environment" constraint enforced elsewhere (see [tool.uv] conflicts in
# pyproject.toml).
FROM python:3.13-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY . .

ARG BACKEND=grpc
RUN uv sync --frozen \
    --package labgrid-toolkit-core \
    --package labgrid-prometheus-exporter \
    --package "labgrid-toolkit-backend-${BACKEND}"

EXPOSE 9314

ENTRYPOINT ["uv", "run", "--no-sync", "labgrid-prometheus-exporter"]
