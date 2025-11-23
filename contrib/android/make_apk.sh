#!/bin/bash

set -e

CONTRIB_ANDROID="$(dirname "$(readlink -e "$0")")"
CONTRIB="$CONTRIB_ANDROID"/..
PROJECT_ROOT="$CONTRIB"/..
PACKAGES="$PROJECT_ROOT"/packages/

. "$CONTRIB"/build_tools_util.sh

git -C "$PROJECT_ROOT" rev-parse 2>/dev/null || fail "Building outside a git clone is not supported."



export ELEC_APK_GUI=$1

if [ ! -d "$PACKAGES" ]; then
    "$CONTRIB"/make_packages.sh || fail "make_packages failed"
fi


info "preparing electrum-locale."
(
    "$CONTRIB/locale/build_cleanlocale.sh"

    rm -r "$PROJECT_ROOT/electrum/locale/locale"/*/electrum.po
)

pushd "$CONTRIB_ANDROID"

info "apk building phase starts."











if [ $CI ]; then

    export BUILDOZER_LOG_LEVEL=2
fi

if [[ "$3" == "release" ]] ; then

    TARGET="release"
    export P4A_RELEASE_KEYSTORE_PASSWD="$4"
    export P4A_RELEASE_KEYALIAS_PASSWD="$4"
    export P4A_RELEASE_KEYSTORE=~/.keystore
    export P4A_RELEASE_KEYALIAS=electrum
    if [ -z "$P4A_RELEASE_KEYSTORE_PASSWD" ] || [ -z "$P4A_RELEASE_KEYALIAS_PASSWD" ]; then
        echo "p4a password not defined"
        exit 1
    fi
elif [[ "$3" == "release-unsigned" ]] ; then

    TARGET="release"
elif [[ "$3" == "debug" ]] ; then

    TARGET="apk"
    export P4A_DEBUG_KEYSTORE="$CONTRIB_ANDROID"/android_debug.keystore
    export P4A_DEBUG_KEYSTORE_PASSWD=unsafepassword
    export P4A_DEBUG_KEYALIAS_PASSWD=unsafepassword
    export P4A_DEBUG_KEYALIAS=electrum

    if [ ! -f "$P4A_DEBUG_KEYSTORE" ]; then
        keytool -genkey -v -keystore "$CONTRIB_ANDROID"/android_debug.keystore \
            -alias "$P4A_DEBUG_KEYALIAS" -keyalg RSA -keysize 2048 -validity 10000 \
            -dname "CN=mqttserver.ibm.com, OU=ID, O=IBM, L=Hursley, S=Hants, C=GB" \
            -storepass "$P4A_DEBUG_KEYSTORE_PASSWD" \
            -keypass "$P4A_DEBUG_KEYALIAS_PASSWD"
    fi
    export ELEC_APK_USE_CURRENT_TIME=1
else
    fail "unknown build type"
fi


if [[ "$2" == "all" ]] ; then


    export APP_ANDROID_ARCHS=armeabi-v7a
    export APP_ANDROID_NUMERIC_VERSION=$("$CONTRIB_ANDROID"/get_apk_versioncode.py "$APP_ANDROID_ARCHS")
    "$CONTRIB_ANDROID"/make_barcode_scanner.sh "$APP_ANDROID_ARCHS" || fail "make_barcode_scanner.sh failed"
    make $TARGET

    export APP_ANDROID_ARCHS=arm64-v8a
    export APP_ANDROID_NUMERIC_VERSION=$("$CONTRIB_ANDROID"/get_apk_versioncode.py "$APP_ANDROID_ARCHS")
    "$CONTRIB_ANDROID"/make_barcode_scanner.sh "$APP_ANDROID_ARCHS" || fail "make_barcode_scanner.sh failed"
    make $TARGET

    export APP_ANDROID_ARCHS=x86_64
    export APP_ANDROID_NUMERIC_VERSION=$("$CONTRIB_ANDROID"/get_apk_versioncode.py "$APP_ANDROID_ARCHS")
    "$CONTRIB_ANDROID"/make_barcode_scanner.sh "$APP_ANDROID_ARCHS" || fail "make_barcode_scanner.sh failed"
    make $TARGET
else
    export APP_ANDROID_ARCHS=$2
    export APP_ANDROID_NUMERIC_VERSION=$("$CONTRIB_ANDROID"/get_apk_versioncode.py "$APP_ANDROID_ARCHS")
    "$CONTRIB_ANDROID"/make_barcode_scanner.sh "$APP_ANDROID_ARCHS" || fail "make_barcode_scanner.sh failed"
    make $TARGET
fi

popd


info "done."
ls -la "$PROJECT_ROOT/dist"
sha256sum "$PROJECT_ROOT/dist"/*
