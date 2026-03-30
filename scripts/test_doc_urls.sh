#!/bin/bash

#    test_doc_urls.sh
#        Script that checks the validaity of every .rst documentation external links found
#        in the given folder
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

set -euo pipefail

source $(dirname ${BASH_SOURCE[0]})/common.sh
PROJECT_ROOT="$(get_project_root)"
FOLDER=$1
cd ${PROJECT_ROOT}

ALL_URLS=$(python ./scripts/extract_doc_external_links.py "$FOLDER")
pids=()
USERAGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
for url in $ALL_URLS; do
    info "Testing URL: $url"
    wget "${url}" \
        --tries=3 \
        --spider \
        --no-dns-cache \
        --quiet \
        --user-agent="$USERAGENT" \
         || fatal "The following URL does not return a success code: $url" &
    pids+=($!)
done

for pid in "${pids[@]}"; do
    wait $pid
done
