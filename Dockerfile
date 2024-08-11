#checkov:skip=CKV_DOCKER_2
#checkov:skip=CKV_DOCKER_3
FROM python:3.12-slim@sha256:a3e58f9399353be051735f09be0316bfdeab571a5c6a24fd78b92df85bcb2d85
LABEL com.github.actions.name="ghidd" \
    com.github.actions.description="Detects and triages duplicate issues" \
    com.github.actions.icon="copy" \
    com.github.actions.color="green" \
    maintainer="@01x4-dev" \
    org.opencontainers.image.url="https://github.com/01x4-dev/ghidd" \
    org.opencontainers.image.source="https://github.com/01x4-dev/ghidd" \
    org.opencontainers.image.documentation="https://github.com/01x4-dev/ghidd" \
    org.opencontainers.image.vendor="01x4-dev" \
    org.opencontainers.image.description="Detects and triages duplicate issues"

COPY requirements.txt /requirements.txt
COPY main.py /main.py

RUN python3 -m pip install --no-cache-dir -r requirements.txt \
    && apt-get -y update \
    && apt-get -y install --no-install-recommends git-all=1:2.39.2-1.1 \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["python3", "-u", "main.py"]
