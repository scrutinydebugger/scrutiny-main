#!/bin/bash

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

# Find project root
PROJECT_ROOT="$(get_project_root)"
cd "${PROJECT_ROOT}"

SCRUTINY_VERSION=$(python -m scrutiny version --format short)

assert_scrutiny_version_format "$SCRUTINY_VERSION"
USERGUIDE_NAME="scrutinydebugger_v${SCRUTINY_VERSION}_user_guide"
echo ${USERGUIDE_NAME}
