#!/bin/bash

#    build_sdk_doc.sh
#        A script that builds the Python SDK HTML documentation
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh
PROJECT_ROOT="$(get_project_root)"
cd "${PROJECT_ROOT}"

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"
info "Building SDK documentation"

SPHINXOPTS=-W make -C docs/sdk html
