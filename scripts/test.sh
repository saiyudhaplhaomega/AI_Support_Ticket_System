#!/usr/bin/env sh
# Run from the repository root. These checks are credential-free and safe offline.
set -eu
./scripts/verify-baseline.sh
python3 -m pytest services/frontend/tests
(cd services/classification && python3 -m pytest)
node --test services/frontend/tests/browser.test.mjs
