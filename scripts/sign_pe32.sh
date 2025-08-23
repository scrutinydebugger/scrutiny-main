#!/bin/bash

set -euo pipefail

ENDPOINT=$1
INPUT_FILE=$2
OUTPUT_FILE=$3

file_type=$(file "${INPUT_FILE}")
if [[ "${file_type}" !=  *"PE32+ executable"* ]]; then
    echo "input file must be a PE32. Got: ${file_type}"
    exit 1
fi

TEMP_DIR=$(mktemp -d)
TEMP_FILE="${TEMP_DIR}/tempbin"
rm -f "${OUTPUT_FILE}"

curl --fail -X POST -F "file=@${INPUT_FILE}" -F "auth_token=$AUTH_TOKEN" "${ENDPOINT}" -o "${TEMP_FILE}"

file_type=$(file "${TEMP_FILE}")
if [[ "${file_type}" !=  *"PE32+ executable"* ]]; then
    echo "Did not download PE32. Got: ${file_type}"
    rm -rf "${TEMP_DIR}"
    exit 1
fi

mv "${TEMP_FILE}" "${OUTPUT_FILE}"
echo "Success: Binary signed at ${OUTPUT_FILE}"
rm -rf "${TEMP_DIR}"
