#!/bin/bash


set -e

venv_dir=~/.electrum-venv
contrib="$(dirname "$0")"


if [[ ! "$SYSTEM_PYTHON" ]] ; then
    SYSTEM_PYTHON=$(which python3.10) || printf ""
else
    SYSTEM_PYTHON=$(which "$SYSTEM_PYTHON") || printf ""
fi
if [[ ! "$SYSTEM_PYTHON" ]] ; then
    echo "Please specify which python to use in \$SYSTEM_PYTHON" && exit 1
fi

which virtualenv > /dev/null 2>&1 || { echo "Please install virtualenv" && exit 1; }

"${SYSTEM_PYTHON}" -m hashin -h > /dev/null 2>&1 || { "${SYSTEM_PYTHON}" -m pip install hashin; }

for suffix in '' '-hw' '-binaries' '-binaries-mac' '-build-wine' '-build-mac' '-build-base' '-build-appimage' '-build-android'; do
    reqfile="requirements${suffix}.txt"

    rm -rf "$venv_dir"
    virtualenv -p "${SYSTEM_PYTHON}" "$venv_dir"

    source "$venv_dir/bin/activate"

    echo "Installing dependencies... (${reqfile})"





    python -m pip install --upgrade pip setuptools wheel

    python -m pip install -r "$contrib/requirements/${reqfile}" --upgrade

    echo "OK."

    requirements=$(pip freeze --all)

    restricted=$(echo $requirements | ${SYSTEM_PYTHON} "$contrib/deterministic-build/find_restricted_dependencies.py")
    if [ ! -z "$restricted" ]; then
        python -m pip install $restricted
        requirements=$(pip freeze --all)
    fi

    echo "Generating package hashes... (${reqfile})"
    rm -f "$contrib/deterministic-build/${reqfile}"
    touch "$contrib/deterministic-build/${reqfile}"



    HASHIN_FLAGS=""
    if [[
        "${suffix}" == "" ||
        "${suffix}" == "-build-wine" ||
        "${suffix}" == "-build-mac" ||
        "${suffix}" == "-build-appimage" ||
        "${suffix}" == "-build-android" ||
        "0" == "1"
        ]] ;
    then
        HASHIN_FLAGS="--python-version source"
    fi

    echo -e "\r  Hashing requirements for $reqfile..."
    ${SYSTEM_PYTHON} -m hashin $HASHIN_FLAGS -r "$contrib/deterministic-build/${reqfile}" $requirements

    echo "OK."
done

echo "Done. Updated requirements"
