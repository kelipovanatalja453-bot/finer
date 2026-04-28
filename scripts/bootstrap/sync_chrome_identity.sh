#!/bin/bash

# ==============================================================================
# 🎭 Chrome Identity Sync Script (Shadow Clone Mode)
# Purpose: Syncs essential login data from Main Profile to Shadow Profile.
# ==============================================================================

SOURCE_DIR="$HOME/Library/Application Support/Google/Chrome/Default"
SHADOW_DIR="/Users/zhouhongyuan/Desktop/finer/.agents/scratch/chrome_shadow_profile/Default"

echo "🔐 Starting Identity Synchronization..."

# 1. Prepare Shadow Directory structure
mkdir -p "$SHADOW_DIR/Network"

# 2. Sync Essential Login Files
# We use -f to force overwrite and skip locks if possible.
echo "📥 Cloning Cookies & Login Data..."
cp -f "$SOURCE_DIR/Cookies" "$SHADOW_DIR/" 2>/dev/null || true
cp -f "$SOURCE_DIR/Login Data" "$SHADOW_DIR/" 2>/dev/null || true
cp -f "$SOURCE_DIR/Network/Cookies" "$SHADOW_DIR/Network/" 2>/dev/null || true

# 3. Sync Local Storage (Essential for modern web apps)
echo "📥 Cloning Local Storage..."
cp -rf "$SOURCE_DIR/Local Storage" "$SHADOW_DIR/" 2>/dev/null || true

# 4. Cleanup Singleton Locks in Shadow to ensure it can start
rm -f "/Users/zhouhongyuan/Desktop/finer/.agents/scratch/chrome_shadow_profile/SingletonLock" 2>/dev/null || true

echo "✅ Identity Sync Complete. Ready to launch Shadow Chrome."
