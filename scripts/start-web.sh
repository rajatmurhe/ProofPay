#!/bin/sh
set -eu
cd "$(dirname "$0")/../apps/web"
exec node node_modules/next/dist/bin/next dev --webpack --hostname 127.0.0.1 --port 3017
