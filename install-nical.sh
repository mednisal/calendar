#!/usr/bin/env bash
set -euo pipefail

# 1. DISTRO DETECTION
detect_distro() {
    local id="" id_like=""
    [[ -f /etc/os-release ]] && {
        id=$(. /etc/os-release && echo "$ID")
        id_like=$(. /etc/os-release && echo "$ID_LIKE")
    }
    
    case "$id" in
        arch|manjaro|endeavouros|cachyos|artix)      echo "arch" ;;
        fedora|rhel|centos|rocky|almalinux|nobara)   echo "fedora" ;;
        debian|ubuntu|pop|linuxmint|kali|zorin|elementary) echo "debian" ;;
        *)                                           echo "unknown" ;;
    esac
}

DISTRO=$(detect_distro)
echo "🔍 Detected: $DISTRO"

# 2. DISTRO-SPECIFIC CONFIG
case "$DISTRO" in
    arch)
        PKG_CMD="sudo pacman -S --needed --noconfirm"
        CACHE_CLEAN="rm -rf ~/.cache/rofi-* ~/.cache/wofi-* ~/.cache/fuzzel-*"
        TERMINAL_HINT="kitty | alacritty | foot"
        ;;
    fedora)
        PKG_CMD="sudo dnf install -y"
        CACHE_CLEAN="rm -rf ~/.cache/rofi-* ~/.cache/wofi-*"
        TERMINAL_HINT="gnome-terminal | konsole | alacritty"
        ;;
    debian)
        PKG_CMD="sudo apt install -y"
        CACHE_CLEAN="rm -rf ~/.cache/rofi-* ~/.cache/wofi-* ~/.cache/xfce4*"
        TERMINAL_HINT="gnome-terminal | xfce4-terminal | alacritty"
        ;;
    *)
        PKG_CMD="echo '⚠️  Unknown distro. Install desktop-file-utils manually.'"
        CACHE_CLEAN="echo '⚠️  Clear your launcher cache manually.'"
        TERMINAL_HINT="your-preferred-terminal"
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_PY="$SCRIPT_DIR/nical.py"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/nical.desktop"

# 3. VALIDATE & PREP
[[ -f "$TARGET_PY" ]] || { echo "❌ nical.py not found in $SCRIPT_DIR"; exit 1; }

# Ensure desktop-file-utils exists
if ! command -v update-desktop-database &>/dev/null; then
    echo "📦 Installing desktop-file-utils ($DISTRO)..."
    $PKG_CMD desktop-file-utils
fi

echo "⚙️  Preparing nical.py..."
chmod +x "$TARGET_PY"
grep -qE '^#!.*python' "$TARGET_PY" 2>/dev/null || sed -i '1i\#!/usr/bin/env python3' "$TARGET_PY"

mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Nical
Exec=$TARGET_PY
Path=$SCRIPT_DIR
Icon=utilities-terminal
Terminal=true
Categories=Utility;
NoDisplay=false
EOF

# 4. REFRESH & DISTRO-SPECIFIC CLEANUP
echo "🔄 Refreshing desktop database..."
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "🧹 Clearing launcher cache ($DISTRO)..."
eval "$CACHE_CLEAN" 2>/dev/null || true

echo "✅ nical.desktop installed. Reopen Hyprlauncher."
echo "💡 If it still doesn't appear, restart your launcher or run: hyprctl reload"
