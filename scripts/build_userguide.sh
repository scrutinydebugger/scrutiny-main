#!/bin/bash

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh
PROJECT_ROOT="$(get_project_root)"
FILENAME=${1:-""}
cd "${PROJECT_ROOT}"

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"
if [ ! -z FILENAME ]; then
    export SCRUTINY_USER_GUIDE_FILENAME="$FILENAME"
fi
info "Building $FILENAME.pdf"

make -C docs/user_guide latexpdf
