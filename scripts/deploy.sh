# Copyright 2026 Snowflake, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#!/usr/bin/env bash
# =============================================================================
# S360 Self-Assessment — Deploy Script
# Usage: ./scripts/deploy.sh --connection <name> [options]
#
# Options:
#   --connection  <name>   Snowflake CLI connection name  (required)
#   --database    <name>   Target database                (default: DEMOS)
#   --schema      <name>   Target schema                  (default: S360_SELF_ASSESS)
#   --warehouse   <name>   Warehouse to create/use        (default: S360_WH)
#   --role        <name>   Role for setup + deploy        (default: ACCOUNTADMIN)
#   --skip-setup           Skip infrastructure setup (re-deploy code only)
#   --prune                Remove stale files from stage after deploy
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CONNECTION=""
DATABASE="DEMOS"
SCHEMA="S360_SELF_ASSESS"
WAREHOUSE="S360_WH"
ROLE="ACCOUNTADMIN"
SKIP_SETUP=false
PRUNE_FLAG=""

# ── Arg parsing ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --connection)  CONNECTION="$2";  shift 2 ;;
        --database)    DATABASE="$2";    shift 2 ;;
        --schema)      SCHEMA="$2";      shift 2 ;;
        --warehouse)   WAREHOUSE="$2";   shift 2 ;;
        --role)        ROLE="$2";        shift 2 ;;
        --skip-setup)  SKIP_SETUP=true;  shift   ;;
        --prune)       PRUNE_FLAG="--prune"; shift ;;
        -h|--help)
            sed -n '2,14p' "$0"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$CONNECTION" ]]; then
    echo "Error: --connection is required."
    echo "Run ./scripts/deploy.sh --help for usage."
    exit 1
fi

echo ""
echo "=============================================="
echo "  S360 Self-Assessment — Deployment"
echo "=============================================="
echo "  Connection : $CONNECTION"
echo "  Role       : $ROLE"
echo "  Database   : $DATABASE"
echo "  Schema     : $SCHEMA"
echo "  Warehouse  : $WAREHOUSE"
echo "=============================================="
echo ""

# ── 1. Infrastructure setup ───────────────────────────────────────────────────
if [[ "$SKIP_SETUP" == false ]]; then
    echo "→ [1/3] Setting up infrastructure..."
    snow sql \
        --connection "$CONNECTION" \
        --filename "$SCRIPT_DIR/setup.sql" \
        --variable "database=$DATABASE" \
        --variable "schema=$SCHEMA" \
        --variable "warehouse=$WAREHOUSE" \
        --variable "role=$ROLE"
    echo "  ✓ Infrastructure ready."
else
    echo "→ [1/3] Skipping infrastructure setup (--skip-setup)."
fi

echo ""

# ── 2. Generate snowflake.yml ─────────────────────────────────────────────────
echo "→ [2/3] Configuring snowflake.yml..."
sed \
    -e "s|__DATABASE__|$DATABASE|g" \
    -e "s|__SCHEMA__|$SCHEMA|g" \
    -e "s|__WAREHOUSE__|$WAREHOUSE|g" \
    "$REPO_ROOT/snowflake.yml.template" > "$REPO_ROOT/snowflake.yml"
echo "  ✓ snowflake.yml written (database=$DATABASE, schema=$SCHEMA, warehouse=$WAREHOUSE)."

echo ""

# ── 3. Deploy Streamlit app ───────────────────────────────────────────────────
echo "→ [3/3] Deploying Streamlit app..."
snow streamlit deploy \
    --connection "$CONNECTION" \
    --replace \
    $PRUNE_FLAG
echo "  ✓ Deployed."

echo ""
echo "=============================================="
echo "  Done!"
echo ""
echo "  Open the app in Snowsight:"
echo "  Snowsight → Streamlit Apps → S360_SELF_ASSESSMENT"
echo "=============================================="
echo ""
