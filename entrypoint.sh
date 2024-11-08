#!/usr/bin/bash

_term() {
  echo "Entrypoint caught SIGTERM signal"
  kill -TERM "$child" 2>/dev/null
  echo "Waiting for child process to exit"
  wait "$child"
}

trap _term SIGTERM

source /opt/conda/.bashrc
source /config/env-variables

micromamba activate

/opt/conda/bin/gdal_warper.py /config/gdal_warper.yaml &

child=$!

wait "$child"
