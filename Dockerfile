FROM registry.access.redhat.com/ubi9/ubi-minimal AS builder

ENV MAMBA_ROOT_PREFIX=/opt/conda
ENV MAMBA_DISABLE_LOCKFILE=TRUE

RUN microdnf -y update && \
    microdnf -y install tar bzip2 && \
    microdnf -y clean all

COPY gdal_warper.py /tmp
COPY environment.yaml /tmp

RUN     curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj -C /usr/bin/ --strip-components=1 bin/micromamba
RUN mkdir /opt/conda && \
    micromamba shell init -s bash && \
    mv /root/.bashrc /opt/conda/.bashrc && \
    source /opt/conda/.bashrc && \
    micromamba activate && \
    micromamba install -y -f /tmp/environment.yaml && \
    rm /tmp/environment.yaml && \
    micromamba clean -af -y && \
    mv /tmp/gdal_warper.py /opt/conda/bin/ && \
    pip cache purge && \
    # Remove git with all its dependencies
    micromamba remove -y git && \
    # Remove pip, leave dependencies intact
    micromamba remove --force -y pip && \
    mkdir /config/ && \
    chgrp -R 0 /opt/conda && \
    chmod -R g=u /opt/conda
# Remove unnecessary packages
RUN source /opt/conda/.bashrc && \
    micromamba activate && \
    micromamba remove --force -y \
        cairo \
        font-ttf-dejavu-sans-mono \
        font-ttf-inconsolata \
        font-ttf-source-code-pro \
        krb5 \
        libarchive \
        libblas \
        libboost-headers \
        libgfortran5 \
        libgfortran-ng \
        libgrpc \
        libopenblas \
        libprotobuf \
        numpy \
        postgresql \
        sqlite \
        xorg-kbproto \
        xorg-libice \
        xorg-libsm \
        xorg-libx11 \
        xorg-libxau \
        xorg-libxdmcp \
        xorg-libxext \
        xorg-libxrender \
        xorg-renderproto \
        xorg-xextproto \
        xorg-xproto

FROM registry.access.redhat.com/ubi9/ubi-minimal

COPY --from=builder /opt/conda /opt/conda
COPY --from=builder /usr/bin/micromamba /usr/bin/
COPY --from=builder /config /config
COPY entrypoint.sh /usr/bin/

USER 1001

ENTRYPOINT ["/usr/bin/entrypoint.sh"]
