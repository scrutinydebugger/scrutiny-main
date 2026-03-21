#!/bin/bash
set -euo pipefail

APP_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"


DOCKER_TAG="scrutiny-main-ci"

set -x

docker build \
    --progress plain \
    -t $DOCKER_TAG \
    $APP_ROOT

exec docker run -t --rm \
    -i \
    --user `id -u`:`id -g` -e HOME=/tmp \
    -v $APP_ROOT:$APP_ROOT \
    -w $APP_ROOT \
    --cpuset-cpus 0 \
    $DOCKER_TAG \
    "$@"
