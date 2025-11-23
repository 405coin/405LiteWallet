#!/bin/bash

set -e

PROJECT_ROOT="$(dirname "$(readlink -e "$0")")/../../.."
CONTRIB="$PROJECT_ROOT/contrib"
CONTRIB_APPIMAGE="$CONTRIB/build-linux/appimage"
DISTDIR="$PROJECT_ROOT/dist"
BUILDDIR="$CONTRIB_APPIMAGE/build/appimage"
APPDIR="$BUILDDIR/electrum.AppDir"
CACHEDIR="$CONTRIB_APPIMAGE/.cache/appimage"
TYPE2_RUNTIME_REPO_DIR="$CACHEDIR/type2-runtime"
export DLL_TARGET_DIR="$CACHEDIR/dlls"
PIP_CACHE_DIR="$CONTRIB_APPIMAGE/.cache/pip_cache"

. "$CONTRIB"/build_tools_util.sh

git -C "$PROJECT_ROOT" rev-parse 2>/dev/null || fail "Building outside a git clone is not supported."

export GCC_STRIP_BINARIES="1"


PYTHON_VERSION=3.12.11
PY_VER_MAJOR="3.12"
PKG2APPIMAGE_COMMIT="a9c85b7e61a3a883f4a35c41c5decb5af88b6b5d"

VERSION=$(git describe --tags --dirty --always)
APPIMAGE="$DISTDIR/electrum-$VERSION-x86_64.AppImage"

rm -rf "$BUILDDIR"
mkdir -p "$APPDIR" "$CACHEDIR" "$PIP_CACHE_DIR" "$DISTDIR" "$DLL_TARGET_DIR"


rm -rf "$PROJECT_ROOT/build"


info "downloading some dependencies."
download_if_not_exist "$CACHEDIR/functions.sh" "https://raw.githubusercontent.com/AppImage/pkg2appimage/$PKG2APPIMAGE_COMMIT/functions.sh"
verify_hash "$CACHEDIR/functions.sh" "8f67711a28635b07ce539a9b083b8c12d5488c00003d6d726c7b134e553220ed"

download_if_not_exist "$CACHEDIR/appimagetool" "https://github.com/AppImage/appimagetool/releases/download/1.9.0/appimagetool-x86_64.AppImage"
verify_hash "$CACHEDIR/appimagetool" "46fdd785094c7f6e545b61afcfb0f3d98d8eab243f644b4b17698c01d06083d1"



download_if_not_exist "$CACHEDIR/Python-$PYTHON_VERSION.tar.xz" "https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tar.xz"
verify_hash "$CACHEDIR/Python-$PYTHON_VERSION.tar.xz" "c30bb24b7f1e9a19b11b55a546434f74e739bb4c271a3e3a80ff4380d49f7adb"



info "building python."
tar xf "$CACHEDIR/Python-$PYTHON_VERSION.tar.xz" -C "$CACHEDIR"
(
    if [ -f "$CACHEDIR/Python-$PYTHON_VERSION/python" ]; then
        info "python already built, skipping"
        exit 0
    fi
    cd "$CACHEDIR/Python-$PYTHON_VERSION"
    LC_ALL=C export BUILD_DATE=$(date -u -d "@$SOURCE_DATE_EPOCH" "+%b %d %Y")
    LC_ALL=C export BUILD_TIME=$(date -u -d "@$SOURCE_DATE_EPOCH" "+%H:%M:%S")

    patch -p1 < "$CONTRIB_APPIMAGE/patches/python-3.11-reproducible-buildinfo.diff"
    ./configure \
        --cache-file="$CACHEDIR/python.config.cache" \
        --prefix="$APPDIR/usr" \
        --enable-ipv6 \
        --enable-shared \
        -q
    make "-j$CPU_COUNT" -s || fail "Could not build Python"
)
info "installing python."
(
    cd "$CACHEDIR/Python-$PYTHON_VERSION"
    make -s install > /dev/null || fail "Could not install Python"





    sed -i -e 's/\.exe//g' "${APPDIR}/usr/lib/python${PY_VER_MAJOR}"/_sysconfigdata*
)


if ls "$DLL_TARGET_DIR"/libsecp256k1.so.* 1> /dev/null 2>&1; then
    info "libsecp256k1 already built, skipping"
else
    "$CONTRIB"/make_libsecp256k1.sh || fail "Could not build libsecp"
fi
cp -f "$DLL_TARGET_DIR"/libsecp256k1.so.* "$APPDIR/usr/lib/" || fail "Could not copy libsecp to its destination"


if [ -f "$DLL_TARGET_DIR/libzbar.so.0" ]; then
    info "libzbar already built, skipping"
else

    "$CONTRIB"/make_zbar.sh || fail "Could not build zbar"
fi
cp -f "$DLL_TARGET_DIR/libzbar.so.0" "$APPDIR/usr/lib/" || fail "Could not copy libzbar to its destination"


appdir_python() {
    env \
        PYTHONNOUSERSITE=1 \
        LD_LIBRARY_PATH="$APPDIR/usr/lib:$APPDIR/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH+:$LD_LIBRARY_PATH}" \
        "$APPDIR/usr/bin/python${PY_VER_MAJOR}" "$@"
}

python='appdir_python'


info "installing pip."
"$python" -m ensurepip

break_legacy_easy_install


info "preparing electrum-locale."
(
    "$CONTRIB/locale/build_cleanlocale.sh"

    rm -r "$PROJECT_ROOT/electrum/locale/locale"/*/electrum.po
)


info "Installing build dependencies."








"$python" -m pip install --no-build-isolation --no-dependencies --no-warn-script-location \
    --cache-dir "$PIP_CACHE_DIR" -r "$CONTRIB/deterministic-build/requirements-build-base.txt"
"$python" -m pip install --no-build-isolation --no-dependencies --no-binary :all: --no-warn-script-location \
    --cache-dir "$PIP_CACHE_DIR" -r "$CONTRIB/deterministic-build/requirements-build-appimage.txt"



export YARL_NO_EXTENSIONS=1
export FROZENLIST_NO_EXTENSIONS=1

export ELECTRUM_ECC_DONT_COMPILE=1

info "installing electrum and its dependencies."
"$python" -m pip install --no-build-isolation --no-dependencies --no-binary :all: --no-warn-script-location \
    --cache-dir "$PIP_CACHE_DIR" -r "$CONTRIB/deterministic-build/requirements.txt"
"$python" -m pip install --no-build-isolation --no-dependencies --no-binary :all: --only-binary PyQt6,PyQt6-Qt6,cryptography --no-warn-script-location \
    --cache-dir "$PIP_CACHE_DIR" -r "$CONTRIB/deterministic-build/requirements-binaries.txt"
"$python" -m pip install --no-build-isolation --no-dependencies --no-binary :all: --no-warn-script-location \
    --cache-dir "$PIP_CACHE_DIR" -r "$CONTRIB/deterministic-build/requirements-hw.txt"

"$python" -m pip install --no-build-isolation --no-dependencies --no-warn-script-location \
    --cache-dir "$PIP_CACHE_DIR" "$PROJECT_ROOT"


"$python" -m pip uninstall -y Cython


info "desktop integration."
cp "$PROJECT_ROOT/405litewallet.desktop" "$APPDIR/405litewallet.desktop"
cp "$PROJECT_ROOT/electrum/gui/icons/405litewallet.png" "$APPDIR/405litewallet.png"



cp "$CONTRIB_APPIMAGE/apprun.sh" "$APPDIR/AppRun"

info "finalizing AppDir."
(
    export PKG2AICOMMIT="$PKG2APPIMAGE_COMMIT"
    . "$CACHEDIR/functions.sh"

    cd "$APPDIR"

    copy_deps; copy_deps; copy_deps
    move_lib



    mv usr/include usr/include.tmp
    delete_blacklisted
    mv usr/include.tmp usr/include
)

info "Copying additional libraries"
(

    cp -f /usr/lib/x86_64-linux-gnu/libusb-1.0.so "$APPDIR/usr/lib/libusb-1.0.so" || fail "Could not copy libusb"

    cp -f /usr/lib/x86_64-linux-gnu/libxkbcommon-x11.so.0 "$APPDIR"/usr/lib/x86_64-linux-gnu || fail "Could not copy libxkbcommon-x11"

    cp -f /usr/lib/x86_64-linux-gnu/libxcb-* "$APPDIR"/usr/lib/x86_64-linux-gnu || fail "Could not copy libxcb"
)

info "stripping binaries from debug symbols."


strip_binaries()
{
    chmod u+w -R "$APPDIR"
    {
        printf '%s\0' "$APPDIR/usr/bin/python${PY_VER_MAJOR}"
        find "$APPDIR" -type f -regex '.*\.so\(\.[0-9.]+\)?$' -print0
    } | xargs -0 --no-run-if-empty --verbose strip -R .note.gnu.build-id -R .comment
}
strip_binaries

remove_emptydirs()
{
    find "$APPDIR" -type d -empty -print0 | xargs -0 --no-run-if-empty rmdir -vp --ignore-fail-on-non-empty
}
remove_emptydirs


info "removing some unneeded stuff to decrease binary size."
rm -rf "$APPDIR"/usr/{share,include}
PYDIR="$APPDIR/usr/lib/python${PY_VER_MAJOR}"
rm -rf "$PYDIR"/{test,ensurepip,lib2to3,idlelib,turtledemo}
rm -rf "$PYDIR"/{ctypes,sqlite3,tkinter,unittest}/test
rm -rf "$PYDIR"/distutils/{command,tests}
rm -rf "$PYDIR"/config-3.*-x86_64-linux-gnu
rm -rf "$PYDIR"/site-packages/{opt,pip,setuptools,wheel}
rm -rf "$PYDIR"/site-packages/Cryptodome/SelfTest
rm -rf "$PYDIR"/site-packages/{psutil,qrcode,websocket}/tests

for component in connectivity declarative help location multimedia quickcontrols2 serialport webengine websockets xmlpatterns ; do
    rm -rf "$PYDIR"/site-packages/PyQt6/Qt6/translations/qt${component}_*
    rm -rf "$PYDIR"/site-packages/PyQt6/Qt6/resources/qt${component}_*
done
rm -rf "$PYDIR"/site-packages/PyQt6/Qt6/{qml,libexec}
rm -rf "$PYDIR"/site-packages/PyQt6/{pyrcc*.so,pylupdate*.so,uic}
rm -rf "$PYDIR"/site-packages/PyQt6/Qt6/plugins/{bearer,gamepads,geometryloaders,geoservices,playlistformats,position,renderplugins,sceneparsers,sensors,sqldrivers,texttospeech,webview}
for component in Bluetooth Concurrent Designer Help Location NetworkAuth Nfc Positioning PositioningQuick Qml Quick Sensors SerialPort Sql Test Web Xml Labs ShaderTools SpatialAudio ; do
    rm -rf "$PYDIR"/site-packages/PyQt6/Qt6/lib/libQt6${component}*
    rm -rf "$PYDIR"/site-packages/PyQt6/Qt${component}*
    rm -rf "$PYDIR"/site-packages/PyQt6/bindings/Qt${component}*
done
for component in Qml Quick ; do
    rm -rf "$PYDIR"/site-packages/PyQt6/Qt6/lib/libQt6*${component}.so*
done
rm -rf "$PYDIR"/site-packages/PyQt6/Qt.so


find "$APPDIR" -path '*/__pycache__*' -delete


for f in "$PYDIR"/site-packages/slip10-*.dist-info; do mv "$f" "$(echo "$f" | sed s/\.dist-info/\.dist-info2/)"; done
rm -rf "$PYDIR"/site-packages/*.dist-info/
rm -rf "$PYDIR"/site-packages/*.egg-info/
for f in "$PYDIR"/site-packages/slip10-*.dist-info2; do mv "$f" "$(echo "$f" | sed s/\.dist-info2/\.dist-info/)"; done


find -exec touch -h -d '2000-11-11T11:11:11+00:00' {} +


info "creating the AppImage."
(
    cd "$BUILDDIR"
    cp "$CACHEDIR/appimagetool" "$CACHEDIR/appimagetool_copy"

    sed -i 's|AI\x02|\x00\x00\x00|' "$CACHEDIR/appimagetool_copy"
    chmod +x "$CACHEDIR/appimagetool_copy"
    "$CACHEDIR/appimagetool_copy" --appimage-extract


    mv "$BUILDDIR/squashfs-root/usr/bin/mksquashfs" "$BUILDDIR/squashfs-root/usr/bin/mksquashfs_orig"
    cat > "$BUILDDIR/squashfs-root/usr/bin/mksquashfs" << EOF

args=\$(echo "\$@" | sed -e 's/-mkfs-time 0//')
"$BUILDDIR/squashfs-root/usr/bin/mksquashfs_orig" \$args
EOF
    chmod +x "$BUILDDIR/squashfs-root/usr/bin/mksquashfs"
    env VERSION="$VERSION" ARCH=x86_64 ./squashfs-root/AppRun --runtime-file "$TYPE2_RUNTIME_REPO_DIR/runtime-x86_64" --no-appstream --verbose "$APPDIR" "$APPIMAGE"
)


info "done."
ls -la "$DISTDIR"
sha256sum "$DISTDIR"/*
