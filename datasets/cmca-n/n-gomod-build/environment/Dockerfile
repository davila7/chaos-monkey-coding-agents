FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build
COPY gen /gen
RUN python3 -B /gen/build.py /out --mirror /mirror

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      golang-1.19-go=1.19.8-2 golang-1.19-src=1.19.8-2 make=4.3-4.1 \
 && rm -rf /var/lib/apt/lists/*
ENV PATH=/usr/lib/go-1.19/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    CGO_ENABLED=0 GOPROXY=file:///srv/gomirror GOSUMDB=off
WORKDIR /app
COPY --from=build /mirror/ /srv/gomirror/
COPY --from=build /out/ /app/
