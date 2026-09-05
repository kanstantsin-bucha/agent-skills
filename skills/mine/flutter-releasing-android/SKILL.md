---
name: flutter-releasing-android
description: Use when building, signing, or uploading the Android release of this app to Google Play, when asked to "make a release", "bump the version", "upload to Play Store", or when the release build fails (strip debug symbols error, keystore/signing errors, Java runtime not found).
---

# Releasing Android to Google Play

## Overview

Release builds are made with `make build-prod`, which signs with the upload keystore and stamps a CalVer version. The only artifact to upload is the `.aab` bundle.

## Versioning (CalVer)

- **Version name:** `YYYY.MM.DD` (build date, dots)
- **Build number:** `year*100000 + month*1000 + day*10 + REV` (e.g. 2026.07.09 → `202607090`)
- `REV` (0–9) allows up to 10 releases per day. First release of the day: plain `make build-prod` (REV defaults to 0); second release: `make build-prod REV=1`, and so on.
- Never edit `version:` in pubspec.yaml — the Makefile overrides it.

## Release Steps

1. Verify signing secrets exist (they are gitignored, NOT in the repo):
   - `android/upload-keystore.jks` and `android/key.properties`
   - If missing, restore from the owner's password manager. Never regenerate silently — a new key breaks Play uploads.
2. Build: `make build-prod` (or `REV=n` for a same-day re-release).
3. Confirm output: `✓ Built build/app/outputs/bundle/release/app-release.aab`.
4. Upload that `.aab` in Play Console → Testing/Production → Create new release.
   Package name: `com.aethelix.resist.buying.android`. Play App Signing is enabled; the local key is only the upload key.
5. Upload-key SHA-256 fingerprint (when Play Console asks for it):
   ```bash
   "/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/keytool" \
     -list -v -keystore android/upload-keystore.jks -alias upload
   ```
   Password is in `android/key.properties`.

## Toolchain Requirements

No system Java is installed; everything uses Android Studio's bundled JDK
(`/Applications/Android Studio.app/Contents/jbr/Contents/Home`, set via `fvm flutter config --jdk-dir`).
SDK lives at `~/Library/Android/sdk` and must include: platform, NDK, CMake, **cmdline-tools** (needed for `apkanalyzer` and licenses).

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| "Release app bundle failed to strip debug symbols" | Usually NOT a strip failure: Flutter verifies stripping with `apkanalyzer` from SDK cmdline-tools. Install cmdline-tools + accept licenses (`yes \| fvm flutter doctor --android-licenses`), rebuild. |
| "Unable to locate a Java Runtime" | Use Android Studio's bundled JDK (path above) for keytool/Gradle. |
| Gradle can't find SDK / wrong SDK | Check `android/local.properties` `sdk.dir=` points to `~/Library/Android/sdk` (it once pointed to the platform-tools Homebrew cask). |
| "IconData can't be extended … final class" | An abandoned icon package. Icons come from `lucide_icons_flutter` (NOT `lucide_icons` — it's dead and won't compile). |
| Play rejects bundle: wrong signature | Bundle must be signed by the upload key. Compare `keytool -printcert -jarfile app-release.aab` fingerprint with the keystore's. |

## Red Flags

- Regenerating the keystore when it "seems missing" — stop, ask the owner.
- Editing `versionCode`/`versionName` in Gradle or pubspec — versioning only flows through the Makefile.
- Uploading an APK — Play requires the `.aab`.
