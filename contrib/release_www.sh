#!/bin/bash








set -e

PROJECT_ROOT="$(dirname "$(readlink -e "$0")")/.."
CONTRIB="$PROJECT_ROOT/contrib"

cd "$PROJECT_ROOT"

. "$CONTRIB"/build_tools_util.sh


echo -n "Remember to run add_cosigner to add any additional sigs.  Continue (y/n)? "
read answer
if [ "$answer" != "y" ]; then
    echo "exit"
    exit 1
fi


if [ -z "$WWW_DIR" ] ; then
    WWW_DIR=/opt/electrum-web
fi

if [ -z "$ELECTRUM_SIGNING_WALLET" ] || [ -z "$ELECTRUM_SIGNING_ADDRESS" ]; then
    echo "You need to set env vars ELECTRUM_SIGNING_WALLET and ELECTRUM_SIGNING_ADDRESS!"
    exit 1
fi

VERSION=$("$CONTRIB"/print_electrum_version.py)
info "VERSION: $VERSION"

ANDROID_VERSIONCODE_NULLARCH=$("$CONTRIB"/android/get_apk_versioncode.py "null")

info "ANDROID_VERSIONCODE_NULLARCH: $ANDROID_VERSIONCODE_NULLARCH"

set -x

info "updating www repo"
./contrib/make_download "$WWW_DIR"
info "signing the version announcement file"
sig=$(./run_405litewallet -o signmessage $ELECTRUM_SIGNING_ADDRESS $VERSION -w $ELECTRUM_SIGNING_WALLET)



cat <<EOF > "$WWW_DIR"/version
{
    "version": "$VERSION",
    "signatures": {"$ELECTRUM_SIGNING_ADDRESS": "$sig"},
    "extradata": {
        "android_versioncode_nullarch": $ANDROID_VERSIONCODE_NULLARCH
    }
}
EOF


pushd "$WWW_DIR"
git diff
git commit -a -m "version $VERSION"
git push
popd


info "release_www.sh finished successfully."
info "now you should run WWW_DIR/publish.sh to sign the website commit and upload signature"
