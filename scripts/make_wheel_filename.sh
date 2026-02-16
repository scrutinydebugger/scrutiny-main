#!/bin/bash

#    make_wheel_filename.sh
#        Generate a filename for the wheel file. Used by other scripts
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh
PROJECT_ROOT="$(get_project_root)"
cd ${PROJECT_ROOT}

VARIANT=${1:-""}

SCRUTINY_VERSION=$(python -m scrutiny version --format short)
assert_scrutiny_version_format "$SCRUTINY_VERSION"

if [[ $VARIANT = '' ]]; then
    echo "scrutinydebugger-${SCRUTINY_VERSION}-py3-none-any.whl"
elif [[ $VARIANT = 'NOCLI' ]]; then
    echo "scrutinydebugger-nocli-${SCRUTINY_VERSION}-py3-none-any.whl"
else
    error "Unknown name variant"
fi
