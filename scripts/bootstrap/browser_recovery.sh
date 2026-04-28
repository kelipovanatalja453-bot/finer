# ==============================================================================
# 🚀 Browser Recovery 2.0 (Deep Healing)
# ==============================================================================

set -e

echo "🚀 Starting Browser Recovery Process..."

# 0. Check System Memory State
echo "📊 Checking system resources..."
MEMORY_REPORT=$(memory_pressure | grep "System-wide memory free percentage" || echo "N/A")
echo "Memory State: $MEMORY_REPORT"

# 1. Kill potentially hanging processes
echo "🛑 Terminating stalling browser processes..."
# Kill Google Chrome and related drivers
for proc in "Google Chrome" "chromedriver" "playwright" "node"; do
    if pgrep -f "$proc" > /dev/null; then
        echo "Killing $proc..."
        pkill -9 -f "$proc" || true
    fi
done

# 2. Cleanup stale lock files (Critical for Profile Inheritance)
echo "🧹 Cleaning up stale session files & Profile locks..."
rm -rf /tmp/playwright* || true
rm -rf /tmp/puppeteer* || true
# Explicitly remove Chrome's SingletonLock which prevents automation takeover
rm -f "$HOME/Library/Application Support/Google/Chrome/SingletonLock" || true
rm -f "$HOME/Library/Application Support/Google/Chrome/Default/SingletonLock" || true
# IMPORTANT: Remove shadow profile locks
SHADOW_PROFILE_DIR="/Users/zhouhongyuan/Desktop/finer/.agents/scratch/chrome_shadow_profile"
rm -f "$SHADOW_PROFILE_DIR/SingletonLock" || true
rm -f "$SHADOW_PROFILE_DIR/Default/SingletonLock" || true
rm -f "$SHADOW_PROFILE_DIR/Network/Cookies-journal" || true

# 3. Verify AppleScript Automation Permissions
echo "🧪 Verifying macOS Automation Permissions..."
OSASCRIPT_TEST=$(osascript -e 'try' -e 'tell application "System Events" to get name of first process whose background only is false' -e 'return "SUCCESS"' -e 'on error' -e 'return "FAILED"' -e 'end try' 2>/dev/null)

if [ "$OSASCRIPT_TEST" == "SUCCESS" ]; then
    echo "✅ Automation Permissions: OK"
else
    echo "⚠️  Automation Permissions: FAILED (System Events restricted)"
fi

# 4. Wait for OS to release resources
sleep 2

echo "✨ Browser environment has been reset and IQ-cleansed."
echo "💡 Reminder: Ensure your desktop Google Chrome is CLOSED if you intend to reuse the profile."

