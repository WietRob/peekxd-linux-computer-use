#!/usr/bin/env bash
# peekxd for Linux — Installation Script
# Usage: ./install.sh [--system] [--user]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_MODE="${1:---user}"
PYTHON="${PYTHON:-python3}"

echo "=== peekxd for Linux — Installation ==="
echo ""

# --- Detect distro ---
DETECTED_DISTRO="unknown"
if command -v apt-get &>/dev/null; then
    DETECTED_DISTRO="debian"
elif command -v dnf &>/dev/null; then
    DETECTED_DISTRO="fedora"
elif command -v pacman &>/dev/null; then
    DETECTED_DISTRO="arch"
elif command -v zypper &>/dev/null; then
    DETECTED_DISTRO="suse"
fi

echo "Detected distro family: $DETECTED_DISTRO"

# --- Install system dependencies ---
install_system_deps() {
    echo ""
    echo "Installing system dependencies..."
    case "$DETECTED_DISTRO" in
        debian)
            sudo apt-get update -qq
            sudo apt-get install -y -qq \
                xdotool imagemagick \
                grim slurp \
                ydotool \
                python3-pyatspi2 \
                at-spi2-core \
                dbus-x11
            ;;
        fedora)
            sudo dnf install -y \
                xdotool ImageMagick \
                grim slurp \
                ydotool \
                pyatspi2 \
                at-spi2-core
            ;;
        arch)
            sudo pacman -S --noconfirm --needed \
                xdotool imagemagick \
                grim slurp \
                ydotool \
                python-atspi \
                at-spi2-core
            ;;
        suse)
            sudo zypper install -y \
                xdotool ImageMagick \
                grim slurp \
                ydotool \
                python3-pyatspi2 \
                at-spi2-core
            ;;
        *)
            echo "WARNING: Unknown distro. Please install manually:"
            echo "  xdotool, imagemagick, grim, ydotool, python3-pyatspi2"
            ;;
    esac
}

# --- Install Python package ---
install_python_pkg() {
    echo ""
    echo "Installing Python package..."
    cd "$SCRIPT_DIR"

    if [[ "$INSTALL_MODE" == "--system" ]]; then
        $PYTHON -m pip install ".[all]"
    else
        $PYTHON -m pip install --user ".[all]"
    fi
}

# --- Setup ydotoold service (Wayland) ---
setup_ydotool() {
    if command -v ydotoold &>/dev/null; then
        echo ""
        echo "Setting up ydotoold service..."
        if command -v systemctl &>/dev/null; then
            # Try user service first
            if systemctl --user daemon-reload 2>/dev/null; then
                cat > "$HOME/.config/systemd/user/ydotoold.service" << 'EOF'
[Unit]
Description=ydotool daemon

[Service]
Type=simple
ExecStart=/usr/bin/ydotoold
Restart=always

[Install]
WantedBy=default.target
EOF
                systemctl --user daemon-reload
                systemctl --user enable ydotoold.service 2>/dev/null || true
                systemctl --user start ydotoold.service 2>/dev/null || true
                echo "ydotoold user service configured."
            fi
        fi
    fi
}

# --- Verify installation ---
verify() {
    echo ""
    echo "Verifying installation..."

    if ! command -v peekxd &>/dev/null; then
        echo "WARNING: 'peekxd' not found in PATH."
        echo "  You may need to add Python user bin to PATH:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        return
    fi

    echo "peekxd version: $(peekxd version)"
    echo ""
    echo "Checking providers..."
    peekxd permissions
}

# --- Main ---
main() {
    read -p "Install system dependencies? (requires sudo) [Y/n]: " ans
    if [[ "${ans:-Y}" =~ ^[Yy] ]]; then
        install_system_deps
    fi

    install_python_pkg
    setup_ydotool
    verify

    echo ""
    echo "=== Installation complete ==="
    echo ""
    echo "Next steps:"
    echo "  1. Set API keys for vision:"
    echo "     export OPENAI_API_KEY='sk-...'"
    echo "     export ANTHROPIC_API_KEY='sk-ant-...'"
    echo "  2. Or start Ollama for local vision:"
    echo "     ollama run llava:latest"
    echo "  3. Run self-test:"
    echo "     ./selftest.sh"
    echo ""
}

main
