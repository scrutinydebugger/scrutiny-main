#!/bin/bash

#    build_userguide.sh
#        A script that builds the user guide PDF and writes it into the python module where
#        ``python -m scrutiny userguide location`` dictates
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
USER_GUIDE_PDF_DST=$(python -m scrutiny userguide location --nocheck)
DOC_FOLDER=docs/user_guide

info "Testing for dead links"
./scripts/test_doc_urls.sh "$DOC_FOLDER"


info "Building $(basename "$USER_GUIDE_PDF_DST").pdf"

SPHINXOPTS=-W make -C $DOC_FOLDER latexpdf

OUTPUT_DIR="$DOC_FOLDER/build/latex"
USER_GUIDE_PDF_SRC="$OUTPUT_DIR/$(basename "$USER_GUIDE_PDF_DST")"
assert_file "$USER_GUIDE_PDF_SRC"
rm -f $USER_GUIDE_PDF_DST
cp "$USER_GUIDE_PDF_SRC" "$USER_GUIDE_PDF_DST"

python -m scrutiny userguide location > /dev/null   # Check existence
info "User guide copied to $USER_GUIDE_PDF_DST"
