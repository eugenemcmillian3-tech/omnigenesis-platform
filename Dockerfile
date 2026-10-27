FROM python:3.11-slim
WORKDIR /opt/omnicloud
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev nodejs && rm -rf /var/lib/apt/lists/*
COPY . /opt/omnicloud/
ENV PORT=8080
ENV STRIPE_WEBHOOK_SECRET=whsec_omni_prod_secret_key
EXPOSE 8080
CMD ["python3", "omnigenesis_engine.py", "--serve", "--port", "8080"]
