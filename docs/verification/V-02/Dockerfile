# The image all.sh runs. In a session behind a TLS-intercepting proxy, also add its CA
# (COPY to /usr/local/share/ca-certificates, update-ca-certificates, NODE_EXTRA_CA_CERTS, npm cafile).
FROM mirror.gcr.io/library/node:22-bookworm-slim
RUN apt-get update -qq && apt-get install -y -qq ca-certificates python3 >/dev/null
RUN npm install -g @openai/codex@0.163.0 && codex --version
