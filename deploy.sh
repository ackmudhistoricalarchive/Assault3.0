#!/bin/bash
set -euo pipefail
TARGET="deploy@10.1.0.245"
SSH="ssh -o StrictHostKeyChecking=no"
# Build
cd assault/src
make
cd -
# Stop service, deploy binary, restart
$SSH $TARGET "sudo systemctl stop mud"
scp -o StrictHostKeyChecking=no assault/src/ack $TARGET:/opt/mud/src/assault/src/ack
$SSH $TARGET "sudo systemctl start mud"
echo "Deployed to Assault3.0"
