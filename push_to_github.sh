#!/usr/bin/env bash
# Push this repo to GitHub once the empty "ROV-Overlay" repo exists and the
# Abacus GitHub App has access to it. Run from inside /home/ubuntu/ROV_Overlay.
set -e

TOKEN=$(python3 -c "import json;print(json.load(open('/home/ubuntu/.config/abacusai_auth_secrets.json'))['githubuser']['secrets']['access_token']['value'])")
USERNAME="Ibrahimadel-stack"
REPO="ROV-Overlay"

git config user.email "rov@deeptech.com"
git config user.name "DeepTech ROV"

# Push using an inline token URL (not stored in config)
git push "https://${TOKEN}@github.com/${USERNAME}/${REPO}.git" main:main -u

echo ""
echo "Done. Actions build: https://github.com/${USERNAME}/${REPO}/actions"
