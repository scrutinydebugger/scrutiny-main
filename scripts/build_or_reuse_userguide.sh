#!/bin/bash

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh
PROJECT_ROOT="$(get_project_root)"
cd "${PROJECT_ROOT}"

# User Guide
if [ ! "${SCRUTINY_USER_GUIDE_PREBUILT:-0}" = "1" ]; then
    info "Building user guide"
    ./scripts/build_userguide.sh
else
    info "Reusing existing user guide (SCRUTINY_USER_GUIDE_PREBUILT=1)"
fi

python -m scrutiny userguide location > /dev/null || fatal "User guide not present"   # Check existence
