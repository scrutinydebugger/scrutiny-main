#!/bin/bash

#    make_wheel.sh
#        Makes a package wheel file
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

# Define the base directories
OUTPUT_FOLDER=$(dir_with_default ${1:-""} "dist_wheel")
PROJECT_ROOT="$(get_project_root)"
cd ${PROJECT_ROOT}

SCRUTINY_VERSION=$(python -m scrutiny version --format short)
assert_scrutiny_version_format "$SCRUTINY_VERSION"

set -x
if [ ! "${SCRUTINY_USER_GUIDE_PREBUILT:-0}" = "1" ]; then
    info "Building user guide"
    ./scripts/build_userguide.sh
else
    info "NOT building the user guide. SCRUTINY_USER_GUIDE_PREBUILT=1"
fi

python -m scrutiny userguide location > /dev/null || fatal "User guide not present"   # Check existence

rm -rf build dist *.egg-info
python -m build -w -o "${OUTPUT_FOLDER}"

EXPECTED_NAME=$(./scripts/make_wheel_filename.sh)
assert_file "$OUTPUT_FOLDER/$EXPECTED_NAME"
