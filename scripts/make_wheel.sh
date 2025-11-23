#!/bin/bash

#    make_wheel.sh
#        Makes a package wheel file
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

# Define the base directories
OUTPUT_FOLDER=$(dir_with_default ${1:-""} "dist_wheel")
PROJECT_ROOT="$(get_project_root)"
cd ${PROJECT_ROOT}

SCRUTINY_VERSION=$(python -m scrutiny version --format short)
assert_scrutiny_version_format "$SCRUTINY_VERSION"

rm -rf build dist *.egg-info 
python -m build -w -o "${OUTPUT_FOLDER}"

EXPECTED_NAME=$(./scripts/make_wheel_filename.sh)
assert_file "$OUTPUT_FOLDER/$EXPECTED_NAME"
