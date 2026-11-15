FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build
COPY gen /gen
RUN python3 -B /gen/build.py /out

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      autoconf=2.71-3 automake=1:1.16.5-1.3 autotools-dev=20220109.1 \
      libtool=2.4.7-7~deb12u1 m4=1.4.19-3 make=4.3-4.1 \
      gcc=4:12.2.0-3 gcc-12=12.2.0-14+deb12u1 cpp-12=12.2.0-14+deb12u1 \
      libc6-dev=2.36-9+deb12u14 binutils=2.40-2 file=1:5.44-3 \
      pkgconf=1.8.1-1 pkgconf-bin=1.8.1-1 libpkgconf3=1.8.1-1 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /out/ /app/
