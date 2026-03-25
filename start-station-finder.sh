#!/bin/sh
cd /Users/yoshidanaoya/Documents/station-finder
exec /opt/homebrew/bin/node ./node_modules/next/dist/bin/next dev --port "${PORT:-3000}"
