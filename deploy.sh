#!/bin/bash
set -euo pipefail
TARGET="deploy@10.1.0.245"
SSH="ssh -o StrictHostKeyChecking=no"
# Build
cd assault/src
make
cd -
# Deploy binary
scp -o StrictHostKeyChecking=no assault/src/ack $TARGET:/opt/mud/src/assault/src/ack
# Restart service
$SSH $TARGET "sudo systemctl restart mud"
echo "Deployed to Assault3.0"
