#!/usr/bin/bash

source /opt/conda/.bashrc
source /config/env-variables

micromamba activate

/opt/conda/bin/gdal_warper.py /config/gdal_warper.yaml
