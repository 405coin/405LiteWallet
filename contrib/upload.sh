#!/bin/bash






set -ex

PROJECT_ROOT="$(dirname "$(readlink -e "$0")")/.."
CONTRIB="$PROJECT_ROOT/contrib"

if [ -z "$SSHUSER" ]; then
    SSHUSER=thomasv
fi

cd "$PROJECT_ROOT"

VERSION=$("$CONTRIB"/print_electrum_version.py)
echo "$VERSION"

if [ -z "$ELECBUILD_UPLOADFROM" ]; then
    cd "$PROJECT_ROOT/dist"
else
    cd "$ELECBUILD_UPLOADFROM"
fi





sftp -oBatchMode=no -b - "$SSHUSER@uploadserver" << !
   cd electrum-downloads-airlock
   -mkdir "$VERSION"
   -chmod 777 "$VERSION"
   cd "$VERSION"
   -mput *
   -chmod 444 *
   bye
!

"$CONTRIB/trigger_deploy.sh" "$SSHUSER" "$VERSION"
