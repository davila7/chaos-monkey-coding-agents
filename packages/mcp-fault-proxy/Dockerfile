FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392
COPY dist/bin/gateway.mjs /srv/gateway/gateway.mjs
RUN mkdir -p /var/log/tt
EXPOSE 8000
CMD ["node", "/srv/gateway/gateway.mjs"]
