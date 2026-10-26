FROM docker.io/library/python@sha256:c4634f578a412db396771b61b064c6e546c9d6414c7fb5b1b05d5871f1885f7b
COPY package/vendor/aarch64-unknown-linux-musl/ /opt/codex/
COPY corp-prj-root-ca.pem /usr/local/share/ca-certificates/fettle-corp-prj-root-ca.crt
RUN echo '298d3d73d0bbc1367e58a370df5b6216fe30ce0a92e8b6b0afb0377a958dc335  /opt/codex/bin/codex' | sha256sum -c - \
    && update-ca-certificates \
    && mkdir /agent /work \
    && chown 65534:65534 /agent /work
USER 65534:65534
ENV HOME=/agent CODEX_HOME=/agent PATH=/opt/codex/bin:/opt/codex/codex-path:/usr/local/bin:/usr/bin:/bin
WORKDIR /work
ENTRYPOINT ["/opt/codex/bin/codex", "--ask-for-approval", "on-request", "--sandbox", "read-only"]