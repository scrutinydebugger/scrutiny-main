#!/bin/bash

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh
PROJECT_ROOT="$(get_project_root)"
cd "${PROJECT_ROOT}"

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"
info "Building SDK documentation"

SPHINXOPTS=-W make -C docs/sdk html
