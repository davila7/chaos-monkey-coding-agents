FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build
COPY gen /gen
RUN python3 -B /gen/build.py /out --mirror /mirror

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      rustc=1.63.0+dfsg1-2 cargo=0.66.0+ds1-1 \
      libstd-rust-1.63=1.63.0+dfsg1-2 libstd-rust-dev=1.63.0+dfsg1-2 \
      gcc=4:12.2.0-3 gcc-12=12.2.0-14+deb12u1 cpp-12=12.2.0-14+deb12u1 \
      libc6-dev=2.36-9+deb12u14 binutils=2.40-2 make=4.3-4.1 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /mirror/ /srv/cargo-mirror/
COPY --from=build /out/ /app/
