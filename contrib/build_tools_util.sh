#!/usr/bin/env bash

set -e


umask 0022

RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m'
function info {
    printf "\r💬 ${BLUE}INFO:${NC}  ${1}\n"
}
function fail {
    printf "\r🗯 ${RED}ERROR:${NC} ${1}\n"
    exit 1
}
function warn {
    printf "\r⚠️  ${YELLOW}WARNING:${NC}  ${1}\n"
}



function verify_signature() {
    local file=$1 keyring=$2 out=
    if out=$(gpg --no-default-keyring --keyring "$keyring" --status-fd 1 --verify "$file" 2>/dev/null) &&
        echo "$out" | grep -qs "^\[GNUPG:\] VALIDSIG "; then
        return 0
    else
        echo "$out" >&2
        exit 1
    fi
}

function verify_hash() {
    local file=$1 expected_hash=$2
    actual_hash=$(sha256sum "$file" | awk '{print $1}')
    if [ "$actual_hash" == "$expected_hash" ]; then
        return 0
    else
        echo "$file $actual_hash (unexpected hash)" >&2
        rm "$file"
        exit 1
    fi
}

function download_if_not_exist() {
    local file_name=$1 url=$2
    if [ ! -e "$file_name" ] ; then
        wget -O "$file_name" "$url"
    fi
}


clone_or_update_repo() {
    local repo_url=$1
    local commit_hash=$2
    local repo_dir=$3

    if [ -z "$repo_url" ] || [ -z "$commit_hash" ] || [ -z "$repo_dir" ]; then
        fail "clone_or_update_repo: invalid arguments: repo_url='$repo_url', commit_hash='$commit_hash', repo_dir='$repo_dir'"
    fi

    if [ -d "$repo_dir" ]; then
        info "Repository $repo_url exists in $repo_dir, updating..."
        git -C "$repo_dir" clean -ffxd >/dev/null 2>&1 || fail "Failed to clean repository $repo_dir"
        git -C "$repo_dir" fetch --all >/dev/null 2>&1 || fail "Failed to fetch from repository"
        git -C "$repo_dir" reset --hard "$commit_hash^{commit}" >/dev/null 2>&1 || fail "Failed to reset to commit $commit_hash"
    else
        info "Cloning repository: $repo_url to $repo_dir"
        git clone "$repo_url" "$repo_dir" >/dev/null 2>&1 || fail "Failed to clone repository $repo_url"
        git -C "$repo_dir" checkout "$commit_hash^{commit}" >/dev/null 2>&1 || fail "Failed to checkout commit $commit_hash"
    fi
}

apply_patch() {
    local patch=$1
    local path=$2

    if [ -z "$patch" ] || [ -z "$path" ]; then
        fail "apply_patch: invalid arguments: patch='$patch', path='$path'"
    fi

    if [ -d "$path" ]; then
        info "Patching: $patch"
        cd "$path"
        patch -p1 <"$patch"
        cd -
    else
        fail "apply_patch: path='$path' not found"
    fi
}


function retry() {
    local result=0
    local count=1
    while [ $count -le 3 ]; do
        [ $result -ne 0 ] && {
            echo -e "\nThe command \"$@\" failed. Retrying, $count of 3.\n" >&2
        }
        ! { "$@"; result=$?; }
        [ $result -eq 0 ] && break
        count=$(($count + 1))
        sleep 1
    done

    [ $count -gt 3 ] && {
        echo -e "\nThe command \"$@\" failed 3 times.\n" >&2
    }

    return $result
}

function gcc_with_triplet()
{
    TRIPLET="$1"
    CMD="$2"
    shift 2
    if [ -n "$TRIPLET" ] ; then
        "$TRIPLET-$CMD" "$@"
    else
        "$CMD" "$@"
    fi
}

function gcc_host()
{
    gcc_with_triplet "$GCC_TRIPLET_HOST" "$@"
}

function gcc_build()
{
    gcc_with_triplet "$GCC_TRIPLET_BUILD" "$@"
}

function host_strip()
{
    if [ "$GCC_STRIP_BINARIES" -ne "0" ] ; then
        case "$BUILD_TYPE" in
            linux|wine)
                gcc_host strip "$@"
                ;;
            darwin)

                ;;
        esac
    fi
}


if ! [ -x "$(command -v realpath)" ]; then
    function realpath() {
        [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"
    }
fi


export SOURCE_DATE_EPOCH=1530212462
export ZERO_AR_DATE=1
export PYTHONHASHSEED=22

export BUILD_TYPE="${BUILD_TYPE:-$(uname | tr '[:upper:]' '[:lower:]')}"

if [ -n "$GCC_TRIPLET_HOST" ] ; then
    export AUTOCONF_FLAGS="$AUTOCONF_FLAGS --host=$GCC_TRIPLET_HOST"
fi
if [ -n "$GCC_TRIPLET_BUILD" ] ; then
    export AUTOCONF_FLAGS="$AUTOCONF_FLAGS --build=$GCC_TRIPLET_BUILD"
fi

export GCC_STRIP_BINARIES="${GCC_STRIP_BINARIES:-0}"

if [ -n "$CIRRUS_CPU" ] ; then

    export CPU_COUNT="$CIRRUS_CPU"
else
    export CPU_COUNT="$(nproc 2> /dev/null || sysctl -n hw.ncpu)"
fi
info "Found $CPU_COUNT CPUs, which we might use for building."


function break_legacy_easy_install() {





    info "Intentionally breaking legacy easy_install."
    DISTUTILS_CFG="${HOME}/.pydistutils.cfg"
    DISTUTILS_CFG_BAK="${HOME}/.pydistutils.cfg.orig"

    if [ -e "$DISTUTILS_CFG" ] && [ ! -e "$DISTUTILS_CFG_BAK" ]; then
        warn "Overwriting python distutils config file at '$DISTUTILS_CFG'. A copy will be saved at '$DISTUTILS_CFG_BAK'."
        mv "$DISTUTILS_CFG" "$DISTUTILS_CFG_BAK"
    fi
    cat <<EOF > "$DISTUTILS_CFG"
[easy_install]
index_url = ''
find_links = ''
EOF
}

