#!/bin/bash

#    activate-venv.sh
#        Activate the virtual environment. Entry point mainly for CI
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

set -uo pipefail

source $(dirname ${BASH_SOURCE[0]})/common.sh
set -e

PROJECT_ROOT="$(get_project_root)"
PY_MODULE_ROOT="$PROJECT_ROOT"

SCRUTINY_VENV_DIR="${SCRUTINY_VENV_DIR:-venv}"
SCRUTINY_VENV_ROOT="${SCRUTINY_VENV_DIR:-$PROJECT_ROOT/$SCRUTINY_VENV_DIR}"

if [ ! -d "$SCRUTINY_VENV_ROOT" ]; then
    info "Missing venv. Creating..."
    for PYTHON3_RUNTIME in $(which -a python3.13 python3.12 python3.11 python3.10 python3); do
        [ -e "$PYTHON3_RUNTIME" ] && break || unset PYTHON3_RUNTIME
    done
    [ -e "$PYTHON3_RUNTIME" ] || fatal No python3 interpreter found
    info "Found $PYTHON3_RUNTIME"
    trace_run "$PYTHON3_RUNTIME" -m venv --prompt venv "$SCRUTINY_VENV_ROOT"
fi

source "$SCRUTINY_VENV_ROOT/bin/activate"


MODULE_FEATURE="[dev]"
if ! [[ -z "${BUILD_CONTEXT+x}" ]]; then
    if [[ "$BUILD_CONTEXT" == "ci" ]]; then
        MODULE_FEATURE="[test]" # Will cause testing tools to be installed.
        export PIP_CACHE_DIR=$SCRUTINY_VENV_ROOT/pip_cache   # Avoid concurrent cache access issue on CI
    fi
fi

trace_run pip3 cache info

if ! pip3 show wheel >/dev/null 2>&1; then
    info "Installing wheel..."
    trace_run pip3 install wheel
    info "Upgrading pip..."
    trace_run pip3 install --upgrade pip
    info "Upgrading setuptools..."
    trace_run pip3 install --upgrade setuptools
fi

if ! diff "$PY_MODULE_ROOT/setup.py" "$SCRUTINY_VENV_ROOT/cache/setup.py" 2>&1 >/dev/null; then
    info "Install scrutiny inside venv"
    trace_run pip3 install -e "${PY_MODULE_ROOT}${MODULE_FEATURE}"
    trace_run mkdir -p "$SCRUTINY_VENV_ROOT/cache/"
    trace_run cp "$PY_MODULE_ROOT/setup.py" "$SCRUTINY_VENV_ROOT/cache/setup.py"
fi

set +e
