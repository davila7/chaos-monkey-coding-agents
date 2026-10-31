FROM mirror.gcr.io/library/debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git python3 curl && rm -rf /var/lib/apt/lists/*
COPY ca.crt /usr/local/share/ca-certificates/proxy.crt
RUN update-ca-certificates
COPY muse /usr/local/bin/muse
RUN chmod +x /usr/local/bin/muse && echo "0809aac7cb58d18f5022b6d05e02aa1974683c0ec430e5f04d25b60ed17de2da  /usr/local/bin/muse" | sha256sum -c -
ENV MUSE_NO_AUTO_UPDATE=1
WORKDIR /work
