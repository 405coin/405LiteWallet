#!/bin/bash

NAME_ROOT=electrum
PROJECT_ROOT="$WINEPREFIX/drive_c/electrum"

export PYTHONDONTWRITEBYTECODE=1



set -e

. "$CONTRIB"/build_tools_util.sh

pushd "$PROJECT_ROOT"

VERSION=$(git describe --tags --dirty --always)
info "Last commit: $VERSION"

info "preparing electrum-locale."
(
    "$CONTRIB/locale/build_cleanlocale.sh"

    rm -r "$PROJECT_ROOT/electrum/locale/locale"/*/electrum.po
)

find -exec touch -h -d '2000-11-11T11:11:11+00:00' {} +
popd



export AIOHTTP_NO_EXTENSIONS=1
export YARL_NO_EXTENSIONS=1
export MULTIDICT_NO_EXTENSIONS=1
export FROZENLIST_NO_EXTENSIONS=1
export PROPCACHE_NO_EXTENSIONS=1
export ELECTRUM_ECC_DONT_COMPILE=1

info "Installing requirements..."
$WINE_PYTHON -m pip install --no-build-isolation --no-dependencies --no-binary :all: --no-warn-script-location \
    --cache-dir "$WINE_PIP_CACHE_DIR" -r "$CONTRIB"/deterministic-build/requirements.txt
info "Installing dependencies specific to binaries..."

$WINE_PYTHON -m pip install --no-build-isolation --no-dependencies --no-warn-script-location \
    --no-binary :all: --only-binary cffi,cryptography,PyQt6,PyQt6-Qt6,PyQt6-sip \
    --cache-dir "$WINE_PIP_CACHE_DIR" -r "$CONTRIB"/deterministic-build/requirements-binaries.txt
info "Installing hardware wallet requirements..."
$WINE_PYTHON -m pip install --no-build-isolation --no-dependencies --no-warn-script-location \
    --no-binary :all: --only-binary cffi,cryptography,hidapi \
    --cache-dir "$WINE_PIP_CACHE_DIR" -r "$CONTRIB"/deterministic-build/requirements-hw.txt

pushd "$PROJECT_ROOT"

info "Pip installing Electrum. This might take a long time if the project folder is large."
$WINE_PYTHON -m pip install --no-build-isolation --no-dependencies --no-warn-script-location .


cp electrum/libsecp256k1-*.dll "$WINEPREFIX/drive_c/python3/Lib/site-packages/electrum_ecc/"
popd


rm -rf dist/


info "Running pyinstaller..."
ELECTRUM_CMDLINE_NAME="$NAME_ROOT-$VERSION" wine "$WINE_PYHOME/scripts/pyinstaller.exe" --noconfirm --clean pyinstaller.spec


pushd dist
find -exec touch -h -d '2000-11-11T11:11:11+00:00' {} +
popd

info "building NSIS installer"

makensis -DPRODUCT_VERSION=$VERSION electrum.nsi

cd dist
mv electrum-setup.exe $NAME_ROOT-$VERSION-setup.exe
cd ..

info "Padding binaries to 8-byte boundaries, and fixing COFF image checksum in PE header"


(
    cd dist
    for binary_file in ./*.exe; do
        info ">> fixing $binary_file..."

        python3 <<EOF
pe_file = "$binary_file"
with open(pe_file, "rb") as f:
    binary = bytearray(f.read())
pe_offset = int.from_bytes(binary[0x3c:0x3c+4], byteorder="little")
checksum_offset = pe_offset + 88
checksum = 0


remainder = len(binary) % 8
binary += bytes(8 - remainder)

for i in range(len(binary) // 4):
    if i == checksum_offset // 4:
        continue
    dword = int.from_bytes(binary[i*4:i*4+4], byteorder="little")
    checksum = (checksum & 0xffffffff) + dword + (checksum >> 32)
    if checksum > 2 ** 32:
        checksum = (checksum & 0xffffffff) + (checksum >> 32)

checksum = (checksum & 0xffff) + (checksum >> 16)
checksum = (checksum) + (checksum >> 16)
checksum = checksum & 0xffff
checksum += len(binary)


binary[checksum_offset : checksum_offset + 4] = int.to_bytes(checksum, byteorder="little", length=4)

with open(pe_file, "wb") as f:
    f.write(binary)
EOF
    done
)

sha256sum dist/electrum*.exe
