#!/usr/bin/env bash

set -e


PYTHON_VERSION=3.12.10
PY_VER_MAJOR="3.12"
PACKAGE=Electrum
GIT_REPO=https://github.com/spesmilo/electrum

export GCC_STRIP_BINARIES="1"
export PYTHONDONTWRITEBYTECODE=1


. "$(dirname "$0")/../build_tools_util.sh"


CONTRIB_OSX="$(dirname "$(realpath "$0")")"
CONTRIB="$CONTRIB_OSX/.."
PROJECT_ROOT="$CONTRIB/.."
CACHEDIR="$CONTRIB_OSX/.cache"
export DLL_TARGET_DIR="$CACHEDIR/dlls"
PIP_CACHE_DIR="$CACHEDIR/pip_cache"

mkdir -p "$CACHEDIR" "$DLL_TARGET_DIR" "$PIP_CACHE_DIR"

cd "$PROJECT_ROOT"

git -C "$PROJECT_ROOT" rev-parse 2>/dev/null || fail "Building outside a git clone is not supported."


which brew > /dev/null 2>&1 || fail "Please install brew from https://brew.sh/ to continue"
which xcodebuild > /dev/null 2>&1 || fail "Please install xcode command line tools to continue"


info "Installing Python $PYTHON_VERSION"
PKG_FILE="python-${PYTHON_VERSION}-macos11.pkg"
if [ ! -f "$CACHEDIR/$PKG_FILE" ]; then
    curl -o "$CACHEDIR/$PKG_FILE" "https://www.python.org/ftp/python/${PYTHON_VERSION}/$PKG_FILE"
fi
echo "8373e58da4ea146b3eb1c1f9834f19a319440b6b679b06050b1f9ee3237aa8e4  $CACHEDIR/$PKG_FILE" | shasum -a 256 -c \
    || fail "python pkg checksum mismatched"
sudo installer -pkg "$CACHEDIR/$PKG_FILE" -target / \
    || fail "failed to install python"


FOUND_PY_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
if [[ "$FOUND_PY_VERSION" != "$PYTHON_VERSION" ]]; then
    fail "python version mismatch: $FOUND_PY_VERSION != $PYTHON_VERSION"
fi

break_legacy_easy_install



VENV_DIR="$CONTRIB_OSX/build-venv"
rm -rf "$VENV_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"





export CFLAGS="-g0"



export ARCHFLAGS="-arch x86_64"

info "Installing build dependencies"








python3 -m pip install --no-build-isolation --no-dependencies --no-warn-script-location \
    --cache-dir "$PIP_CACHE_DIR" -Ir ./contrib/deterministic-build/requirements-build-base.txt \
    || fail "Could not install build dependencies (base)"
python3 -m pip install --no-build-isolation --no-dependencies --no-binary :all: --no-warn-script-location \
    --cache-dir "$PIP_CACHE_DIR" -Ir ./contrib/deterministic-build/requirements-build-mac.txt \
    || fail "Could not install build dependencies (mac)"

info "Installing some build-time deps for compilation..."
brew install autoconf automake libtool gettext coreutils pkgconfig

info "Building PyInstaller."
PYINSTALLER_REPO="https://github.com/pyinstaller/pyinstaller.git"
PYINSTALLER_COMMIT="306d4d92580fea7be7ff2c89ba112cdc6f73fac1"

(
    if [ -f "$CACHEDIR/pyinstaller/PyInstaller/bootloader/Darwin-64bit/runw" ]; then
        info "pyinstaller already built, skipping"
        exit 0
    fi
    cd "$PROJECT_ROOT"
    ELECTRUM_COMMIT_HASH=$(git rev-parse HEAD)
    cd "$CACHEDIR"
    rm -rf pyinstaller
    mkdir pyinstaller
    cd pyinstaller

    git init
    git remote add origin $PYINSTALLER_REPO
    git fetch --depth 1 origin $PYINSTALLER_COMMIT
    git checkout -b pinned "${PYINSTALLER_COMMIT}^{commit}"
    rm -fv PyInstaller/bootloader/Darwin-*/run* || true


    echo "const char *electrum_tag = \"tagged by Electrum@$ELECTRUM_COMMIT_HASH\";" >> ./bootloader/src/pyi_main.c
    pushd bootloader

    python3 ./waf all CFLAGS="-static"
    popd

    [[ -e "PyInstaller/bootloader/Darwin-64bit/runw" ]] || fail "Could not find runw in target dir!"
)
info "Installing PyInstaller."
python3 -m pip install --no-build-isolation --no-dependencies \
    --cache-dir "$PIP_CACHE_DIR" --no-warn-script-location "$CACHEDIR/pyinstaller"

info "Using these versions for building $PACKAGE:"
sw_vers
python3 --version
echo -n "Pyinstaller "
pyinstaller --version

rm -rf ./dist

info "resetting git submodules."


git submodule update --init --force

info "preparing electrum-locale."
(
    if ! which msgfmt > /dev/null 2>&1; then
        brew install gettext
        brew link --force gettext
    fi
    "$CONTRIB/locale/build_cleanlocale.sh"

    rm -r "$PROJECT_ROOT/electrum/locale/locale"/*/electrum.po
)


if ls "$DLL_TARGET_DIR"/libsecp256k1.*.dylib 1> /dev/null 2>&1; then
    info "libsecp256k1 already built, skipping"
else
    info "Building libsecp256k1 dylib..."
    "$CONTRIB"/make_libsecp256k1.sh || fail "Could not build libsecp"
fi
cp -f "$DLL_TARGET_DIR"/libsecp256k1.*.dylib "$PROJECT_ROOT/electrum" || fail "Could not copy libsecp256k1 dylib"

if [ ! -f "$DLL_TARGET_DIR/libzbar.0.dylib" ]; then
    info "Building ZBar dylib..."
    "$CONTRIB"/make_zbar.sh || fail "Could not build ZBar dylib"
else
    info "Skipping ZBar build: reusing already built dylib."
fi
cp -f "$DLL_TARGET_DIR/libzbar.0.dylib" "$PROJECT_ROOT/electrum/" || fail "Could not copy ZBar dylib"

if [ ! -f "$DLL_TARGET_DIR/libusb-1.0.dylib" ]; then
    info "Building libusb dylib..."
    "$CONTRIB"/make_libusb.sh || fail "Could not build libusb dylib"
else
    info "Skipping libusb build: reusing already built dylib."
fi
cp -f "$DLL_TARGET_DIR/libusb-1.0.dylib" "$PROJECT_ROOT/electrum/" || fail "Could not copy libusb dylib"



export YARL_NO_EXTENSIONS=1
export PROPCACHE_NO_EXTENSIONS=1

export ELECTRUM_ECC_DONT_COMPILE=1

info "Installing requirements..."
python3 -m pip install --no-build-isolation --no-dependencies --no-binary :all: \
    --cache-dir "$PIP_CACHE_DIR" --no-warn-script-location \
    -Ir ./contrib/deterministic-build/requirements.txt \
    || fail "Could not install requirements"

info "Installing hardware wallet requirements..."
python3 -m pip install --no-build-isolation --no-dependencies --no-binary :all: --only-binary cryptography \
    --cache-dir "$PIP_CACHE_DIR" --no-warn-script-location \
    -Ir ./contrib/deterministic-build/requirements-hw.txt \
    || fail "Could not install hardware wallet requirements"

info "Installing dependencies specific to binaries..."
python3 -m pip install --no-build-isolation --no-dependencies --no-binary :all: --only-binary PyQt6,PyQt6-Qt6,cryptography \
    --cache-dir "$PIP_CACHE_DIR" --no-warn-script-location \
    -Ir ./contrib/deterministic-build/requirements-binaries-mac.txt \
    || fail "Could not install dependencies specific to binaries"

info "Building $PACKAGE..."
python3 -m pip install --no-build-isolation --no-dependencies \
    --cache-dir "$PIP_CACHE_DIR" --no-warn-script-location . > /dev/null || fail "Could not build $PACKAGE"


cp "$DLL_TARGET_DIR"/libsecp256k1.*.dylib "$VENV_DIR/lib/python$PY_VER_MAJOR/site-packages/electrum_ecc/"



find "$VENV_DIR/lib/python$PY_VER_MAJOR/site-packages/" -type f -name '*.so' -print0 \
    | xargs -0 -t strip -x

info "Faking timestamps..."
find . -exec touch -t '200101220000' {} + || true


VERSION=$(git describe --tags --always)

info "Building binary"
ELECTRUM_VERSION=$VERSION pyinstaller --noconfirm --clean contrib/osx/pyinstaller.spec || fail "Could not build binary"

info "Finished building unsigned dist/${PACKAGE}.app. This hash should be reproducible:"
find "dist/${PACKAGE}.app" -type f -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256

info "Creating unsigned .DMG"
hdiutil create -fs HFS+ -volname $PACKAGE -srcfolder dist/$PACKAGE.app dist/electrum-$VERSION-unsigned.dmg || fail "Could not create .DMG"

info "App was built successfully but was not code signed. Users may get security warnings from macOS."
info "Now you also need to run sign_osx.sh to codesign/notarize the binary."
