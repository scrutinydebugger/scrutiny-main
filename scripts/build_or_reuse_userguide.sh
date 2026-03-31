#!/bin/bash

#    build_or_reuse_userguide.sh
#        Script that either build the user guide or check for its existence if the proper
#        environment variable is set. Meant to be called by a build process
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

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
