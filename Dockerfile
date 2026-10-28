FROM python:3.13-slim
WORKDIR /opt/omnicloud
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev nodejs && rm -rf /var/lib/apt/lists/*
COPY . /opt/omnicloud/
RUN python3 -m pip install --no-cache-dir -r requirements.lock \
    && useradd --system --create-home --home-dir /opt/omnicloud/app --shell /bin/bash omni \
    && mkdir -p /opt/omnicloud/app/.ssh \
    && chmod 0700 /opt/omnicloud/app/.ssh \
    && mkdir -p /var/lib/omnigenesis \
    && chown -R omni:omni /opt/omnicloud /var/lib/omnigenesis
USER omni
ENV PORT=8080 OMNIGENESIS_PRIVATE_BETA=1 PYTHONUNBUFFERED=1
ENV OMNIGENESIS_DATA_DIR=/var/lib/omnigenesis
EXPOSE 8080
CMD ["bash", "deploy/start-beta.sh"]
