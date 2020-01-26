#! /usr/bin/bash

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"

podman build --pull -t broker:dev -v $SRC_DIR:/project:z --force-rm=true \
	-f devel/Dockerfile
