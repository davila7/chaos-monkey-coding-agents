FROM node:22-bookworm-slim
COPY ca-bundle.crt /usr/local/share/ca-certificates/proxy.crt
ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/proxy.crt
RUN npm install -g @anthropic-ai/claude-code@2.1.289 && claude --version
