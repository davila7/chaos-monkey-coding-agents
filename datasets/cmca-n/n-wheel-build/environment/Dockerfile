FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build
COPY gen /gen
RUN python3 /gen/build.py /out

FROM debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3=3.11.2-1+b1 python3.11=3.11.2-6+deb12u9 python-is-python3=3.11.2-1+deb12u1 \
      python3-venv=3.11.2-1+b1 python3.11-venv=3.11.2-6+deb12u9 python3-pip=23.0.1+dfsg-1 \
      python3-setuptools=66.1.1-1+deb12u2 python3-wheel=0.38.4-2 python3-build=0.9.0-1 \
      ca-certificates=20250419~deb12u2 netbase=6.4 \
 && rm -rf /var/lib/apt/lists/*
ENV PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY --from=build /out/ /app/
