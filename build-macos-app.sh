#!/bin/bash
# Build a downloadable macOS launcher app + .dmg for Odysseus.
#
#   ./build-macos-app.sh
#
# Produces:
#   dist/Odysseus.app   — double-click: asks for dev/nonprod/prod, switches to
#                         that branch, starts the local services, and opens UI.
#   dist/Odysseus.dmg   — drag-to-Applications disk image (the downloadable).
#
# This is a *launcher* wrapper: it drives the local launch agents and repo
# checkout. The install path is baked into the app at build time, so rebuild if
# you move the repo. Override the port with ODYSSEUS_PORT.
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="Odysseus"
INSTALL_DIR="$REPO_DIR"
OLLAMA_DIR="${OLLAMA_DIR:-$HOME/Projects/ollama}"
PORT="${ODYSSEUS_PORT:-7860}"
DIST="$REPO_DIR/dist"
APP="$DIST/$APP_NAME.app"
LAUNCHER_TEMPLATE="$REPO_DIR/scripts/macos/odysseus-launcher.applescript"
GENERATED_LAUNCHER="$DIST/odysseus-launcher.generated.applescript"
ICON_FILE="$DIST/odysseus.icns"

echo "Building $APP_NAME.app"
echo "  install dir: $INSTALL_DIR"
echo "  ollama dir:  $OLLAMA_DIR"
echo "  port:        $PORT"

rm -rf "$APP"
mkdir -p "$DIST"

plist_set() {
  local plist="$1"
  local key="$2"
  local type="$3"
  local value="${4:-}"

  if [ "$type" = "bool" ]; then
    /usr/libexec/PlistBuddy -c "Set :$key $value" "$plist" >/dev/null 2>&1 ||
      /usr/libexec/PlistBuddy -c "Add :$key bool $value" "$plist" >/dev/null
  else
    /usr/libexec/PlistBuddy -c "Set :$key $value" "$plist" >/dev/null 2>&1 ||
      /usr/libexec/PlistBuddy -c "Add :$key $type $value" "$plist" >/dev/null
  fi
}

# ── Icon (best effort) — center-crop docs/odysseus.png to a square .icns ──
rm -f "$ICON_FILE"
if [ -f "$REPO_DIR/docs/odysseus.png" ] && command -v sips >/dev/null 2>&1; then
  TMPIMG="$(mktemp -d)"
  # Center-crop to a square, scale to 512 (sips' icns encoder caps at 512), and
  # let sips emit the .icns directly — more robust across macOS versions than
  # building an .iconset by hand.
  sips -c 720 720 "$REPO_DIR/docs/odysseus.png" --out "$TMPIMG/sq.png" >/dev/null 2>&1 || cp "$REPO_DIR/docs/odysseus.png" "$TMPIMG/sq.png"
  sips -z 512 512 "$TMPIMG/sq.png" --out "$TMPIMG/icon.png" >/dev/null 2>&1
  if sips -s format icns "$TMPIMG/icon.png" --out "$ICON_FILE" >/dev/null 2>&1; then
    echo "  icon:        odysseus.icns"
  else
    echo "  icon:        (skipped — conversion failed)"
  fi
  rm -rf "$TMPIMG"
else
  echo "  icon:        (skipped — no docs/odysseus.png)"
fi

# ── Launcher applet ──
sed \
  -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
  -e "s|__OLLAMA_DIR__|$OLLAMA_DIR|g" \
  -e "s|__PORT__|$PORT|g" \
  "$LAUNCHER_TEMPLATE" > "$GENERATED_LAUNCHER"

osacompile -o "$APP" "$GENERATED_LAUNCHER"
rm -f "$GENERATED_LAUNCHER"

if [ -f "$ICON_FILE" ]; then
  cp "$ICON_FILE" "$APP/Contents/Resources/odysseus.icns"
fi

PLIST="$APP/Contents/Info.plist"
plist_set "$PLIST" CFBundleName string "$APP_NAME"
plist_set "$PLIST" CFBundleDisplayName string "$APP_NAME"
plist_set "$PLIST" CFBundleIdentifier string "com.odysseus.launcher"
plist_set "$PLIST" CFBundleVersion string "1.0"
plist_set "$PLIST" CFBundleShortVersionString string "1.0"
plist_set "$PLIST" CFBundleIconFile string "odysseus"
plist_set "$PLIST" CFBundleIconName string "odysseus"
plist_set "$PLIST" LSMinimumSystemVersion string "11.0"
plist_set "$PLIST" NSHighResolutionCapable bool true
plist_set "$PLIST" LSUIElement bool false
plist_set "$PLIST" OSAAppletStayOpen bool true
plist_set "$PLIST" OSAAppletShowStartupScreen bool false

# Refresh Finder's icon cache for the new bundle.
touch "$APP"

# ── .dmg (drag-to-Applications) ──
echo "Packaging dist/$APP_NAME.dmg"
STAGE="$(mktemp -d)/dmg"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DIST/$APP_NAME.dmg"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" -ov -format UDZO "$DIST/$APP_NAME.dmg" >/dev/null
rm -rf "$STAGE"

echo ""
echo "Done:"
echo "  $APP"
echo "  $DIST/$APP_NAME.dmg"
echo ""
echo "Run it:        open '$APP'"
echo "Install:       open '$DIST/$APP_NAME.dmg'  (drag Odysseus to Applications)"
