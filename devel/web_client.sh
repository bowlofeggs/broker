#! /usr/bin/bash

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"
PARAMS=$@

podman run --rm -it --network=host -v $SRC_DIR:/project:z broker:dev \
	bash -c "python3 /project/web_client.py $PARAMS"
