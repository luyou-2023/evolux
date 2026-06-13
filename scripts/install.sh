#!/bin/bash
# ============================================================================
# Evolux Installer (Hermes-compatible curl install)
# ============================================================================
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/luyou-2023/evolux/main/scripts/install.sh | bash
#
# Options:
#   --skip-setup       Skip evolux setup wizard
#   --skip-migrate     Skip Hermes auto-migration prompt
#   --branch NAME      Git branch (default: main)
#   --dir PATH         Install checkout directory
#   --evolux-home PATH Data directory (default: ~/.evolux)
# ============================================================================

set -e

if [ -n "${PYTHONPATH:-}" ]; then
    echo "⚠ Ignoring inherited PYTHONPATH during install"
    unset PYTHONPATH
fi
if [ -n "${PYTHONHOME:-}" ]; then
    echo "⚠ Ignoring inherited PYTHONHOME during install"
    unset PYTHONHOME
fi

REPO_URL="https://github.com/luyou-2023/evolux.git"
EVOLUX_HOME="${EVOLUX_HOME:-$HOME/.evolux}"
INSTALL_DIR="${EVOLUX_INSTALL_DIR:-$EVOLUX_HOME/evolux}"
BRANCH="main"
RUN_SETUP=true
RUN_MIGRATE=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-setup) RUN_SETUP=false; shift ;;
        --skip-migrate) RUN_MIGRATE=false; shift ;;
        --branch) BRANCH="$2"; shift 2 ;;
        --dir) INSTALL_DIR="$2"; shift 2 ;;
        --evolux-home) EVOLUX_HOME="$2"; shift 2 ;;
        -h|--help)
            sed -n '1,20p' "$0" | tail -n +2
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

log_info() { echo "→ $1"; }
log_ok() { echo "✓ $1"; }
log_warn() { echo "⚠ $1"; }

print_banner() {
    echo ""
    echo "┌──────────────────────────────────────────────┐"
    echo "│           Evolux Agent Installer             │"
    echo "│  Orchestrator + persistent domain subagents  │"
    echo "└──────────────────────────────────────────────┘"
    echo ""
}

require_python() {
    if command -v python3 >/dev/null 2>&1; then
        PY=python3
    elif command -v python >/dev/null 2>&1; then
        PY=python
    else
        echo "✗ Python 3.10+ is required"
        exit 1
    fi
    "$PY" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
    if [ $? -ne 0 ]; then
        echo "✗ Python 3.10+ is required"
        exit 1
    fi
    log_ok "Python: $($PY --version)"
}

clone_or_update() {
    mkdir -p "$(dirname "$INSTALL_DIR")"
    if [ -d "$INSTALL_DIR/.git" ]; then
        log_info "Updating existing checkout: $INSTALL_DIR"
        git -C "$INSTALL_DIR" fetch origin "$BRANCH"
        git -C "$INSTALL_DIR" checkout "$BRANCH"
        git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH" || true
    else
        log_info "Cloning Evolux into $INSTALL_DIR"
        git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    fi
}

install_package() {
    log_info "Installing evolux package"
    "$PY" -m pip install --upgrade pip >/dev/null
    "$PY" -m pip install -e "$INSTALL_DIR[dev,gateway]"
    log_ok "Package installed"
}

write_wrapper() {
    local bin_dir="$HOME/.local/bin"
    mkdir -p "$bin_dir"
    cat > "$bin_dir/evolux" <<EOF
#!/usr/bin/env bash
export EVOLUX_HOME="${EVOLUX_HOME}"
exec "${PY}" -m cli.main "\$@"
EOF
    chmod +x "$bin_dir/evolux"
    log_ok "CLI wrapper: $bin_dir/evolux"
}

ensure_path() {
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) log_ok "~/.local/bin already on PATH" ;;
        *)
            SHELL_RC=""
            case "$(basename "${SHELL:-bash}")" in
                zsh) SHELL_RC="$HOME/.zshrc" ;;
                bash) SHELL_RC="$HOME/.bashrc" ;;
            esac
            if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
                if ! grep -q '# Evolux' "$SHELL_RC" 2>/dev/null; then
                    {
                        echo ""
                        echo "# Evolux"
                        echo 'export PATH="$HOME/.local/bin:$PATH"'
                    } >> "$SHELL_RC"
                    log_ok "Added ~/.local/bin to PATH in $SHELL_RC"
                fi
            else
                log_warn "Add ~/.local/bin to your PATH manually"
            fi
            ;;
    esac
}

run_setup() {
    if [ "$RUN_SETUP" != true ]; then
        log_warn "Setup skipped (--skip-setup)"
        return
    fi
    export EVOLUX_HOME
    if [ "$RUN_MIGRATE" = true ]; then
        log_info "Running evolux setup (auto-detect Hermes)..."
        "$PY" -m cli.main setup --from-hermes || "$PY" -m cli.main setup
    else
        "$PY" -m cli.main setup --skip-hermes
    fi
}

print_banner
require_python
clone_or_update
install_package
write_wrapper
ensure_path
run_setup

echo ""
log_ok "Evolux installed"
echo "  evolux chat          # interactive CLI; /exit saves session and stops"
echo "  evolux setup"
echo "  evolux migrate detect"
echo "  EVOLUX_HOME=$EVOLUX_HOME"
