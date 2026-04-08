#!/usr/bin/env bash
# =============================================================================
# S360 Self-Assessment — Deploy Script
# Usage: ./scripts/deploy.sh --connection <name> [options]
#
# Options:
#   --connection  <name>   Snowflake CLI connection name (required)
#   --database    <name>   Target database        (default: DEMOS)
#   --schema      <name>   Target schema          (default: S360_SELF_ASSESS)
#   --warehouse   <name>   Warehouse to create    (default: S360_WH)
#   --skip-setup           Skip infrastructure setup (re-deploy only)
#   --prune                Remove stale files from stage
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CONNECTION=""
DATABASE="DEMOS"
SCHEMA="S360_SELF_ASSESS"
WAREHOUSE="S360_WH"
SKIP_SETUP=false
PRUNE_FLAG=""

# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --connection)  CONNECTION="$2";  shift 2 ;;
        --database)    DATABASE="$2";    shift 2 ;;
        --schema)      SCHEMA="$2";      shift 2 ;;
        --warehouse)   WAREHOUSE="$2";   shift 2 ;;
        --skip-setup)  SKIP_SETUP=true;  shift   ;;
        --prune)       PRUNE_FLAG="--prune"; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$CONNECTION" ]]; then
    echo "Error: --connection is required."
    echo "Usage: ./scripts/deploy.sh --connection <name> [--database <db>] [--schema <schema>] [--warehouse <wh>]"
    exit 1
fi

echo ""
echo "=============================================="
echo "  S360 Self-Assessment — Deployment"
echo "=============================================="
echo "  Connection : $CONNECTION"
echo "  Database   : $DATABASE"
echo "  Schema     : $SCHEMA"
echo "  Warehouse  : $WAREHOUSE"
echo "=============================================="
echo ""

# ---------------------------------------------------------------------------
# 1. Infrastructure setup
# ---------------------------------------------------------------------------
if [[ "$SKIP_SETUP" == false ]]; then
    echo "→ [1/3] Setting up infrastructure..."
    snow sql \
        --connection "$CONNECTION" \
        --filename "$SCRIPT_DIR/setup.sql" \
        --variable "database=$DATABASE" \
        --variable "schema=$SCHEMA" \
        --variable "warehouse=$WAREHOUSE"
    echo "  ✓ Infrastructure ready."
else
    echo "→ [1/3] Skipping infrastructure setup (--skip-setup)."
fi

echo ""

# ---------------------------------------------------------------------------
# 2. Generate snowflake.yml from template
# ---------------------------------------------------------------------------
echo "→ [2/3] Configuring snowflake.yml..."
sed \
    -e "s|__DATABASE__|$DATABASE|g" \
    -e "s|__SCHEMA__|$SCHEMA|g" \
    -e "s|__WAREHOUSE__|$WAREHOUSE|g" \
    "$REPO_ROOT/snowflake.yml.template" > "$REPO_ROOT/snowflake.yml"
echo "  ✓ snowflake.yml written."

echo ""

# ---------------------------------------------------------------------------
# 3. Deploy Streamlit app
# ---------------------------------------------------------------------------
echo "→ [3/3] Deploying Streamlit app..."
snow streamlit deploy \
    --connection "$CONNECTION" \
    --replace \
    $PRUNE_FLAG
echo "  ✓ Deployed."

echo ""
echo "=============================================="
echo "  Done. Open the app in Snowsight:"
APP_URL="https://app.snowflake.com/$(snow connection show "$CONNECTION" 2>/dev/null | grep -i organizationname | awk '{print $2}' || echo '<org>')/$(snow connection show "$CONNECTION" 2>/dev/null | grep -i accountname | awk '{print $2}' || echo '<account>')/#/streamlit-apps/${DATABASE}.${SCHEMA}.S360_SELF_ASSESSMENT"
echo "  $APP_URL"
echo "=============================================="
echo ""
