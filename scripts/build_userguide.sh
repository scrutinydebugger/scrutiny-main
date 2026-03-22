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

OUTPUT_DIR="$PROJECT_ROOT/docs/user_guide/build/latex"
USER_GUIDE_PDF_DST=$(python -m scrutiny userguide location --nocheck)
USER_GUIDE_PDF_SRC="$OUTPUT_DIR/$(basename "$USER_GUIDE_PDF_DST")"
assert_file "$USER_GUIDE_PDF_SRC"
rm -f $USER_GUIDE_PDF_DST
cp "$USER_GUIDE_PDF_SRC" "$USER_GUIDE_PDF_DST"

python -m scrutiny userguide location > /dev/null   # Check existence
info "User guide copied to $USER_GUIDE_PDF_DST"
