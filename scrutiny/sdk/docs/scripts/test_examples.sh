#!/bin/bash
set -eEuo pipefail
DOC_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd -P )"
EXAMPLES_ROOT="$DOC_ROOT/source/_static/code-examples"

tempdir=$(mktemp -d)
trap  "echo 'Error. Exiting' && rm -rf ${tempdir}" ERR

set -x

echo -e "\nTesting example code..."

cd $tempdir
MYPY_OPTIONS="--no-warn-redundant-casts --strict --cache-dir $tempdir"

# HIL testing
cd $EXAMPLES_ROOT/hil_testing
outfile="$tempdir/hil_testing.cpp"
cat *.cpp > $outfile
g++ -c "$outfile" -o "$tempdir/hil_testing.o"
g++ -c "$outfile" -o "$tempdir/hil_testing.o" -DENABLE_HIL_TESTING 
python3 -m mypy hil_testing_1_powerup_check.py $MYPY_OPTIONS

# EOL Config
cd $EXAMPLES_ROOT/eol_config
outfile="$tempdir/eol_config.cpp"
cat *.cpp > $outfile
g++ -c "$outfile" -o $tempdir/eol_config.o
g++ -c "$outfile" -o $tempdir/eol_config.o -DENABLE_EOL_CONFIGURATOR
python3 -m mypy eol_config_assembly_header.py $MYPY_OPTIONS
python3 -m mypy eol_config_dump_eeprom.py $MYPY_OPTIONS

# Calibration
cd $EXAMPLES_ROOT/calibration
outfile="$tempdir/calibration.cpp"
cat *.cpp > $outfile
g++ -c "$outfile" -o $tempdir/calibration.o
g++ -c "$outfile" -o $tempdir/calibration.o -DENABLE_TUNNING
python3 -m mypy calibration_1_pi_graph.py $MYPY_OPTIONS


# Event looping
cd $EXAMPLES_ROOT/event_looping
python3 -m mypy event_looping.py $MYPY_OPTIONS

# SFD upload/download
cd $EXAMPLES_ROOT/sfd_upload_download
python3 -m mypy download_sfd.py $MYPY_OPTIONS
python3 -m mypy upload_sfd.py $MYPY_OPTIONS

rm -rf $tempdir
