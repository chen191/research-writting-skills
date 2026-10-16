# Build-only source for the exact already deployed SJTUTeX class/provenance.
ARG COMPILER_ORIGIN=sha256:b5910a43a1ade7aa32c2175132beafb9c51fcbbe3942d108ab56fdab79514dcb
FROM ${COMPILER_ORIGIN} AS compiler-origin
USER root
COPY collect_toolchain.py /tmp/collect_toolchain.py
RUN python /tmp/collect_toolchain.py
FROM ghcr.io/aygenta-ai/aygenta-runtime-base@sha256:195c008a7cee9e33d042ab2af04da355b801afed412b192fd5c04d0af15d4ee3
USER root
ENV PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=compiler-origin /toolchain-root/ /
# Keep all Debian notices, including fonts and Perl modules copied as trees.
COPY --from=compiler-origin /usr/share/doc/ /opt/aygenta-paper-pdf/third-party-notices/origin-debian-doc/
COPY engine/ /opt/aygenta-paper-pdf/
COPY ORIGIN.json /opt/aygenta-paper-pdf/ORIGIN.json
RUN python3 /opt/aygenta-paper-pdf/cli.py doctor
# Keep the platform's s6/browser runtime entrypoint. PDF is an on-demand command,
# not a service: no EXPOSE, web listener, supervisor entry or extra data volume.
WORKDIR /workspace
