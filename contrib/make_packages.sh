#!/bin/bash


set -e

CONTRIB="$(dirname "$(readlink -e "$0")")"
PROJECT_ROOT="$CONTRIB"/..
PACKAGES="$PROJECT_ROOT"/packages/

test -n "$CONTRIB" -a -d "$CONTRIB" || exit
cd "$CONTRIB"

if [ -d "$PACKAGES" ]; then
    rm -r "$PACKAGES"
fi



venv_dir="$CONTRIB/.venv_make_packages/"
rm -rf "$venv_dir"
python3 -m venv "$venv_dir"
source "$venv_dir"/bin/activate


python3 -m pip install --no-build-isolation --no-dependencies --no-warn-script-location \
    -r "$CONTRIB"/deterministic-build/requirements-build-base.txt


export AIOHTTP_NO_EXTENSIONS=1
export YARL_NO_EXTENSIONS=1
export MULTIDICT_NO_EXTENSIONS=1
export FROZENLIST_NO_EXTENSIONS=1
export PROPCACHE_NO_EXTENSIONS=1

export ELECTRUM_ECC_DONT_COMPILE=1


export BUILD_EXTENSION="no"



export LC_ALL=C
export TZ=UTC
export SOURCE_DATE_EPOCH="$(git log -1 --pretty=%ct 2>/dev/null || printf 1530212462)"
export PYTHONHASHSEED="$SOURCE_DATE_EPOCH"
export BUILD_DATE="$(LC_ALL=C TZ=UTC date +'%b %e %Y' -d @$SOURCE_DATE_EPOCH)"
export BUILD_TIME="$(LC_ALL=C TZ=UTC date +'%H:%M:%S' -d @$SOURCE_DATE_EPOCH)"










python3 -m pip install --no-build-isolation --no-compile --no-dependencies --no-binary :all: \
    -r "$CONTRIB"/deterministic-build/requirements.txt -t "$PACKAGES"

echo "Pure-python dependencies have been placed into $PACKAGES"
