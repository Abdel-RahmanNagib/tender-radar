#!/usr/bin/env bash
# Opens the app on the running Android emulator the way a person does, and writes to the job summary whether it
# stays open. If it closes, Android's own crash report (the reason) is copied into the summary.
# Used by .github/workflows/android.yml:  bash android/test-on-phone.sh <apk> "<phone name>"
set -u
APK="$1"
PHONE="$2"
PKG=com.cecegypt.tenderradar
SUM="${GITHUB_STEP_SUMMARY:-/dev/stdout}"
failed=0

say() { printf '%s\n' "$*" >> "$SUM"; }

check() {  # $1 = what was just done
  local log pid focus screen
  log=$(adb logcat -d -v brief 2>/dev/null)
  pid=$(adb shell pidof "$PKG" 2>/dev/null | tr -d '\r')
  focus=$(adb shell dumpsys window 2>/dev/null | grep -m1 -E 'mCurrentFocus' | tr -d '\r' | sed 's/^ *//')
  if printf '%s\n' "$log" | grep -q -E "FATAL EXCEPTION|ANR in $PKG|AwBrowserTerminator|Process: $PKG"; then
    failed=1
    say "#### ❌ $PHONE – $1: the app closed"
    say '```'
    printf '%s\n' "$log" | grep -A 40 -E "FATAL EXCEPTION|ANR in $PKG|AwBrowserTerminator" | head -90 >> "$SUM"
    say '```'
  elif [ -z "$pid" ]; then
    failed=1
    say "#### ❌ $PHONE – $1: the app is not running (Android gave no crash report)"
    say '```'
    printf '%s\n' "$log" | grep -E "$PKG|ActivityManager|ActivityTaskManager" | tail -40 >> "$SUM"
    say '```'
  else
    say "#### ✅ $PHONE – $1: the app is open"
    say "On screen: $focus"
    adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
    screen=$(adb shell cat /sdcard/ui.xml 2>/dev/null | grep -o 'text="[^"]\+"' | sed 's/^text="//; s/"$//' | head -14 | tr '\n' '|')
    say "Text on screen: ${screen:-(none read)}"
  fi
  say ""
  adb logcat -c
}

say "### $PHONE"
say "WebView: $(adb shell dumpsys webviewupdate 2>/dev/null | grep -m1 -E 'Current WebView package' | tr -d '\r' | sed 's/^ *//')"
if ! adb install -r "$APK" >/tmp/install.txt 2>&1; then
  say "#### ❌ install failed"; say '```'; cat /tmp/install.txt >> "$SUM"; say '```'; exit 1
fi
adb logcat -c

adb shell am start -W -n "$PKG/.MainActivity" >/dev/null 2>&1
sleep 30
check "first start after installing"

# Android 13 and later ask about notifications: answer yes, then open the app again
adb shell pm grant "$PKG" android.permission.POST_NOTIFICATIONS >/dev/null 2>&1 || true
adb shell am force-stop "$PKG"
sleep 2
adb logcat -c
adb shell am start -W -n "$PKG/.MainActivity" >/dev/null 2>&1
sleep 25
check "second start"

adb shell cmd jobscheduler run -f "$PKG" 4711 >/dev/null 2>&1 || true
sleep 25
check "hourly check for new tenders (in the background)"

adb shell am start -W -n "$PKG/.MainActivity" --es tender test >/dev/null 2>&1
sleep 10
check "opening a tender from a notification"

# a fresh install with notifications already allowed: the welcome notification is posted right away
adb uninstall "$PKG" >/dev/null 2>&1
adb install -g "$APK" >/dev/null 2>&1
adb logcat -c
adb shell am start -W -n "$PKG/.MainActivity" >/dev/null 2>&1
sleep 25
check "fresh install with notifications allowed (welcome notification)"
say "Notifications from the app on the phone: $(adb shell dumpsys notification --noredact 2>/dev/null | grep -c "pkg=$PKG")"

exit $failed
