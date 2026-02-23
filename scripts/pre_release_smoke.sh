#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/pre_release_smoke.sh --version X.Y.Z [options]

Options:
  --python VERSION       Python version for wheel smoke venv (default: 3.12)
  --allow-dirty          Skip clean working tree enforcement in preflight
  --allow-existing-tag   Skip local tag-availability enforcement in preflight
  --skip-release-md      Skip RELEASE.md version-title check in preflight
  --with-git             Also smoke-test GitHub install via uvx --from git+...
  --git-ref REF          Git ref for --with-git (default: main)
  --with-testpypi        Also smoke-test TestPyPI install for this version
  -h, --help             Show this help text
EOF
}

VERSION=""
PYTHON_VERSION="3.12"
ALLOW_DIRTY=0
ALLOW_EXISTING_TAG=0
SKIP_RELEASE_MD=0
WITH_GIT=0
GIT_REF="main"
WITH_TESTPYPI=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --python)
      PYTHON_VERSION="${2:-}"
      shift 2
      ;;
    --allow-dirty)
      ALLOW_DIRTY=1
      shift
      ;;
    --allow-existing-tag)
      ALLOW_EXISTING_TAG=1
      shift
      ;;
    --skip-release-md)
      SKIP_RELEASE_MD=1
      shift
      ;;
    --with-git)
      WITH_GIT=1
      shift
      ;;
    --git-ref)
      GIT_REF="${2:-}"
      shift 2
      ;;
    --with-testpypi)
      WITH_TESTPYPI=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$VERSION" ]]; then
  echo "ERROR: --version is required" >&2
  usage >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PREFLIGHT_ARGS=(--version "$VERSION")
if [[ "$ALLOW_DIRTY" -eq 1 ]]; then
  PREFLIGHT_ARGS+=(--allow-dirty)
fi
if [[ "$ALLOW_EXISTING_TAG" -eq 1 ]]; then
  PREFLIGHT_ARGS+=(--allow-existing-tag)
fi
if [[ "$SKIP_RELEASE_MD" -eq 1 ]]; then
  PREFLIGHT_ARGS+=(--skip-release-md)
fi

echo "==> Release preflight checklist"
uv run python scripts/release_preflight.py "${PREFLIGHT_ARGS[@]}"

echo "==> Local entrypoint smoke (project env)"
uv run zulipchat-mcp --version
uv run zulipchat-mcp-setup --version
uv run zulipchat-mcp-integrate --version
uv run zulipchat-mcp-integrate list

echo "==> Build package artifacts"
uv build

SMOKE_VENV=".release-smoke-venv"
SMOKE_TMP_DIR="$(mktemp -d /tmp/zulipchat-mcp-smoke-XXXXXX)"
cleanup() {
  rm -rf "$SMOKE_TMP_DIR"
}
trap cleanup EXIT
SMOKE_VENV="$SMOKE_TMP_DIR/venv"
uv venv "$SMOKE_VENV" --python "$PYTHON_VERSION"

WHEEL_PATH="dist/zulipchat_mcp-${VERSION}-py3-none-any.whl"
if [[ ! -f "$WHEEL_PATH" ]]; then
  echo "ERROR: Expected wheel not found: $WHEEL_PATH" >&2
  exit 1
fi
uv pip install --python "$SMOKE_VENV/bin/python" "$WHEEL_PATH"

echo "==> Installed-wheel entrypoint smoke"
"$SMOKE_VENV/bin/zulipchat-mcp" --version
"$SMOKE_VENV/bin/zulipchat-mcp-setup" --version
"$SMOKE_VENV/bin/zulipchat-mcp-integrate" --version
"$SMOKE_VENV/bin/zulipchat-mcp-integrate" list

if [[ "$WITH_GIT" -eq 1 ]]; then
  echo "==> GitHub install smoke (ref: $GIT_REF)"
  uvx --from "git+https://github.com/akougkas/zulipchat-mcp.git@${GIT_REF}" zulipchat-mcp --version
  uvx --from "git+https://github.com/akougkas/zulipchat-mcp.git@${GIT_REF}" zulipchat-mcp-setup --version
  uvx --from "git+https://github.com/akougkas/zulipchat-mcp.git@${GIT_REF}" zulipchat-mcp-integrate --version
fi

if [[ "$WITH_TESTPYPI" -eq 1 ]]; then
  echo "==> TestPyPI install smoke (version: $VERSION)"
  uvx \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    "zulipchat-mcp==${VERSION}" \
    --version
fi

echo "==> Pre-release smoke completed"
