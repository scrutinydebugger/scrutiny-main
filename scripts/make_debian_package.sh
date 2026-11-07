#!/bin/bash

#    make_debian_package.sh
#        Create a debian/Ubuntu package from the Nuitka compiler output
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

set -euo pipefail
source $(dirname ${BASH_SOURCE[0]})/common.sh

# Find project root
NUITKA_OUTPUT=$(dir_with_default ${1:-""} "nuitka_build")
PROJECT_ROOT="$(get_project_root)"
SOURCE_DIR="${NUITKA_OUTPUT}/scrutiny.dist"
OUTPUT_FOLDER=$(dir_with_default ${2:-""} "${NUITKA_OUTPUT}/installer")
RELEASE_DATE="${3:-$(date +%Y-%m-%d)}"

cd ${PROJECT_ROOT}

# Check Folders exists
info "Source directory: $SOURCE_DIR"

assert_dir "$SOURCE_DIR"

# Get verion and validate
SCRUTINY_VERSION=$( ${SOURCE_DIR}/scrutiny.bin version --format short )
assert_scrutiny_version_format "$SCRUTINY_VERSION"
info "Scrutiny version: $SCRUTINY_VERSION"

# Prepare package
ARCH="$(dpkg-architecture -qDEB_BUILD_ARCH)"
TEMP_FOLDER="$(mktemp -d)"
trap 'rm -rf "${TEMP_FOLDER}"' EXIT
PKG_NAME="scrutinydebugger_${SCRUTINY_VERSION}_${ARCH}"

PKG_FOLDER="${TEMP_FOLDER}/${PKG_NAME}"
info "Creating debian package: ${PKG_NAME}"
info "Work folder: ${PKG_FOLDER}"

mkdir -p "${PKG_FOLDER}"
mkdir -p "${PKG_FOLDER}/DEBIAN" "${PKG_FOLDER}/opt" "${PKG_FOLDER}/usr/local/bin/" "${PKG_FOLDER}/usr/share/applications"

cp "${PROJECT_ROOT}/deploy/debian/control" "${PKG_FOLDER}/DEBIAN/control"   # Copy the template
sed -i "s/<VERSION>/${SCRUTINY_VERSION}/g"  "${PKG_FOLDER}/DEBIAN/control"  # Set the version in the control file
sed -i "s/<ARCH>/$ARCH/g"  "${PKG_FOLDER}/DEBIAN/control"                     # Set the arch in the control file
cp "${PROJECT_ROOT}/deploy/debian/postinst" "${PKG_FOLDER}/DEBIAN/postinst"
chmod 755 "${PKG_FOLDER}/DEBIAN/postinst"
cp "${PROJECT_ROOT}/deploy/debian/postrm" "${PKG_FOLDER}/DEBIAN/postrm"
chmod 755 "${PKG_FOLDER}/DEBIAN/postrm"

cp -r "${SOURCE_DIR}" "${PKG_FOLDER}/opt/scrutinydebugger"                  # The program
cp  "${PROJECT_ROOT}/deploy/debian/scrutiny.gui.desktop" "${PKG_FOLDER}/usr/share/applications/"                 # Desktop Icon : Scrutiny GUI
cp  "${PROJECT_ROOT}/deploy/debian/scrutiny.gui.local-server.desktop" "${PKG_FOLDER}/usr/share/applications/"   # Desktop Icon : Scrutiny GUI (Local)

mkdir -p "${PKG_FOLDER}/usr/share/icons/hicolor/512x512/apps" "${PKG_FOLDER}/usr/share/doc/scrutinydebugger" "${PKG_FOLDER}/usr/share/metainfo"
cp "${PROJECT_ROOT}/deploy/scrutiny-icon.png" "${PKG_FOLDER}/usr/share/icons/hicolor/512x512/apps/scrutinydebugger.png"
cp "${PROJECT_ROOT}/deploy/debian/copyright" "${PKG_FOLDER}/usr/share/doc/scrutinydebugger/copyright"
sed -i "s/<YEAR>/$(date +%Y)/g" "${PKG_FOLDER}/usr/share/doc/scrutinydebugger/copyright"
cp "${PROJECT_ROOT}/deploy/debian/scrutiny.gui.metainfo.xml" "${PKG_FOLDER}/usr/share/metainfo/"
sed -i "s/<VERSION>/${SCRUTINY_VERSION}/g" "${PKG_FOLDER}/usr/share/metainfo/scrutiny.gui.metainfo.xml"
sed -i "s/<DATE>/${RELEASE_DATE}/g"        "${PKG_FOLDER}/usr/share/metainfo/scrutiny.gui.metainfo.xml"

ln -s "/opt/scrutinydebugger/scrutiny.bin" "${PKG_FOLDER}/usr/local/bin/scrutiny"   # CLI launcher

INSTALLED_SIZE=$(du -sk --exclude="DEBIAN" "${PKG_FOLDER}" | cut -f1)
sed -i "s/<INSTALLED_SIZE>/${INSTALLED_SIZE}/g" "${PKG_FOLDER}/DEBIAN/control"

dpkg-deb --root-owner-group --build "${PKG_FOLDER}"                                 # Pack

# Move the package in the wanted output folder
mkdir -p "${OUTPUT_FOLDER}"
OUTFILE="${OUTPUT_FOLDER}/${PKG_NAME}.deb"
cp "${TEMP_FOLDER}/${PKG_NAME}.deb" "${OUTFILE}"

assert_file "${OUTFILE}"
success "File ${OUTFILE} has been created!"

# Cleanup
rm -rf "${TEMP_FOLDER}"
