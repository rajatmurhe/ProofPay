#!/bin/sh
set -eu
curl --fail --silent --show-error -X POST http://127.0.0.1:8017/demo
