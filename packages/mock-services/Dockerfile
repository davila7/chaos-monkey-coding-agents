FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392
# One image per service, from the same bundle: docker build --build-arg SERVICE=<name>.
ARG SERVICE=tickets
COPY dist/bin/${SERVICE}.mjs /srv/${SERVICE}/${SERVICE}.mjs
RUN mkdir -p /var/lib/${SERVICE} && ln -s /srv/${SERVICE}/${SERVICE}.mjs /srv/service.mjs
EXPOSE 8080
CMD ["node", "/srv/service.mjs"]
