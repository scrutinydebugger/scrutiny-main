#!/bin/bash

#    make_wheel_nocli.sh
#        Makes a package wheel file without CLI entry points
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

EXPECTED_NAME=$(./scripts/make_wheel_filename.sh)
NOCLI_BASENAME=$(./scripts/make_wheel_filename.sh NOCLI)

SCRUTINY_ADD_ENTRYPOINTS=0 ./scripts/make_wheel.sh "$OUTPUT_FOLDER"    # Create a wheel without entry points (nocli)
assert_file "$OUTPUT_FOLDER/$EXPECTED_NAME"
mv "$OUTPUT_FOLDER/$EXPECTED_NAME" "$OUTPUT_FOLDER/$NOCLI_BASENAME"   # Rename
assert_file "$OUTPUT_FOLDER/$NOCLI_BASENAME"
