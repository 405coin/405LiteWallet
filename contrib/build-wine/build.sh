#!/bin/bash





set -e

PROJECT_ROOT="$(dirname "$(readlink -e "$0")")/../.."
PROJECT_ROOT_OR_FRESHCLONE_ROOT="$PROJECT_ROOT"
CONTRIB="$PROJECT_ROOT/contrib"
CONTRIB_WINE="$CONTRIB/build-wine"
BUILD_UID=$(/usr/bin/stat -c %u "$PROJECT_ROOT")

. "$CONTRIB"/build_tools_util.sh

info "Clearing $CONTRIB_WINE/dist..."
rm -rf "$CONTRIB_WINE"/dist/*


DOCKER_BUILD_FLAGS=""
if [ ! -z "$ELECBUILD_NOCACHE" ] ; then
    info "ELECBUILD_NOCACHE is set. forcing rebuild of docker image."
    DOCKER_BUILD_FLAGS="--pull --no-cache"
fi

if [ -z "$ELECBUILD_COMMIT" ] ; then
    DOCKER_BUILD_FLAGS="$DOCKER_BUILD_FLAGS --build-arg UID=$BUILD_UID"
fi

info "building docker image."
docker build \
    $DOCKER_BUILD_FLAGS \
    -t electrum-wine-builder-img \
    "$CONTRIB_WINE"


if [ ! -z "$ELECBUILD_COMMIT" ] ; then
    info "ELECBUILD_COMMIT=$ELECBUILD_COMMIT. doing fresh clone and git checkout."
    FRESH_CLONE="/tmp/electrum_build/windows/fresh_clone/electrum"
    rm -rf "$FRESH_CLONE" 2>/dev/null || ( info "we need sudo to rm prev FRESH_CLONE." && sudo rm -rf "$FRESH_CLONE" )
    umask 0022
    git clone "$PROJECT_ROOT" "$FRESH_CLONE"
    cd "$FRESH_CLONE"
    git checkout "$ELECBUILD_COMMIT"
    PROJECT_ROOT_OR_FRESHCLONE_ROOT="$FRESH_CLONE"
else
    info "not doing fresh clone."
fi

DOCKER_RUN_FLAGS=""
if [ -t 0 ] && [ -t 1 ]; then
    info "interactive TTY detected; running docker with -it"
    DOCKER_RUN_FLAGS="-it"
else
    info "no interactive TTY detected; running docker without -it"
fi

info "building binary..."

if [ ! -z "$ELECBUILD_COMMIT" ] ; then
    if [ $(id -u) != "1000" ] || [ $(id -g) != "1000" ] ; then
        info "need to chown -R FRESH_CLONE dir. prompting for sudo."
        sudo chown -R 1000:1000 "$FRESH_CLONE"
    fi
fi
docker run $DOCKER_RUN_FLAGS \
    --name electrum-wine-builder-cont \
    -v "$PROJECT_ROOT_OR_FRESHCLONE_ROOT":/opt/wine64/drive_c/electrum \
    --rm \
    --workdir /opt/wine64/drive_c/electrum/contrib/build-wine \
    electrum-wine-builder-img \
    ./make_win.sh


if [ ! -z "$ELECBUILD_COMMIT" ] ; then
    mkdir --parents "$PROJECT_ROOT/contrib/build-wine/dist/"
    cp -f "$FRESH_CLONE/contrib/build-wine/dist"/*.exe "$PROJECT_ROOT/contrib/build-wine/dist/"
fi
