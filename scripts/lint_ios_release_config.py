#!/usr/bin/env python3
"""Release-config lint for the iOS app; runs in iOS CI, stdlib only.

Every check takes (info, sources) and returns a list of problems; any problem
fails the run. Add new checks to CHECKS.
"""
import plistlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "ios" / "StockApp" / "stockme"
INFO_PLIST = APP / "Info.plist"  # GENERATE_INFOPLIST_FILE = NO: this file is the app's Info.plist
SOURCES = APP / "stockme"

# Source pattern -> purpose string iOS requires before that API runs. Without it
# the app is killed on first use and App Store Connect rejects the upload (ITMS-90683).
PURPOSE_STRINGS = [
    (r"\bimport Speech\b|\bSFSpeechRecognizer\b", "NSSpeechRecognitionUsageDescription"),
    (r"\bAVAudioRecorder\b|\.inputNode\b|setCategory\(\s*\.(?:record|playAndRecord)\b|requestRecordPermission",
     "NSMicrophoneUsageDescription"),
    (r"\brequestWriteOnlyAccessToEvents\b", "NSCalendarsWriteOnlyAccessUsageDescription"),
    (r"\brequestFullAccessToEvents\b|requestAccess\(to:\s*\.event\b", "NSCalendarsFullAccessUsageDescription"),
    (r"\bLAContext\b", "NSFaceIDUsageDescription"),
    (r"\bAVCaptureDevice\b", "NSCameraUsageDescription"),
    (r"\bPHPhotoLibrary\b", "NSPhotoLibraryUsageDescription"),
]


def check_purpose_strings(info, sources):
    problems = []
    for pattern, key in PURPOSE_STRINGS:
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            continue
        for path, text in sources:
            match = re.search(pattern, text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{path.relative_to(ROOT)}:{line}: uses {match.group(0)!r} "
                                f"but {INFO_PLIST.relative_to(ROOT)} has no non-empty {key}")
                break
    return problems


ENTITLEMENTS = APP / "stockme.entitlements"
PBXPROJ = APP / "stockme.xcodeproj" / "project.pbxproj"
APP_BUNDLE_ID = "saumypatel.stockme"


def check_push_entitlement(info, sources):
    """registerForRemoteNotifications needs aps-environment, or APNs never issues a
    token (IOSCORE-10). Every app-target build configuration must point at the file."""
    if not any("registerForRemoteNotifications" in text for _, text in sources):
        return []
    rel = ENTITLEMENTS.relative_to(ROOT)
    if not ENTITLEMENTS.is_file():
        return [f"{rel} is missing but the app calls registerForRemoteNotifications"]
    with ENTITLEMENTS.open("rb") as f:
        entitlements = plistlib.load(f)
    problems = []
    if entitlements.get("aps-environment") not in ("development", "production"):
        problems.append(f"{rel} has no aps-environment entitlement")
    # Build-settings blocks of the app target: the ones whose bundle id is exactly the app's.
    blocks = re.findall(r"buildSettings = \{(.*?)\n\t\t\t\};", PBXPROJ.read_text(encoding="utf-8"), re.S)
    app_blocks = [b for b in blocks if re.search(rf"PRODUCT_BUNDLE_IDENTIFIER = {re.escape(APP_BUNDLE_ID)};", b)]
    if not app_blocks:
        problems.append(f"{PBXPROJ.relative_to(ROOT)}: no build configuration for {APP_BUNDLE_ID}")
    for block in app_blocks:
        if not re.search(r'"CODE_SIGN_ENTITLEMENTS\[sdk=iphoneos\*\]" = stockme\.entitlements;', block):
            problems.append(f"{PBXPROJ.relative_to(ROOT)}: a {APP_BUNDLE_ID} build configuration "
                            "does not set CODE_SIGN_ENTITLEMENTS[sdk=iphoneos*] = stockme.entitlements")
            break
    return problems


PRIVACY_MANIFEST = SOURCES / "PrivacyInfo.xcprivacy"  # synchronized folder group: bundled without a pbxproj entry
USER_DEFAULTS_REASONS = {"CA92.1", "1C8F.1", "C56D.1", "AC6B.1"}  # Apple's approved UserDefaults reasons


def check_privacy_manifest(info, sources):
    """App Store Connect rejects uploads whose required-reason API use is undeclared
    (ITMS-91053); UserDefaults is one of those APIs (IOSCORE-26)."""
    rel = PRIVACY_MANIFEST.relative_to(ROOT)
    if not PRIVACY_MANIFEST.is_file():
        return [f"{rel} is missing"]
    try:
        with PRIVACY_MANIFEST.open("rb") as f:
            manifest = plistlib.load(f)
    except Exception as exc:
        return [f"{rel} is not a valid plist: {exc}"]
    problems = []
    if manifest.get("NSPrivacyTracking") is not False:
        problems.append(f"{rel}: NSPrivacyTracking must be false")
    if any("UserDefaults" in text for _, text in sources):
        reasons = {r for entry in manifest.get("NSPrivacyAccessedAPITypes", [])
                   if entry.get("NSPrivacyAccessedAPIType") == "NSPrivacyAccessedAPICategoryUserDefaults"
                   for r in entry.get("NSPrivacyAccessedAPITypeReasons", [])}
        if not reasons & USER_DEFAULTS_REASONS:
            problems.append(f"{rel}: the app uses UserDefaults but declares no "
                            "NSPrivacyAccessedAPICategoryUserDefaults reason")
    return problems


def check_export_compliance(info, sources):
    """Without ITSAppUsesNonExemptEncryption every upload stalls on the export-compliance
    question in App Store Connect (IOSCORE-26)."""
    if not isinstance(info.get("ITSAppUsesNonExemptEncryption"), bool):
        return [f"{INFO_PLIST.relative_to(ROOT)} has no boolean ITSAppUsesNonExemptEncryption"]
    return []


def check_iphone_portrait_only(info, sources):
    """Layouts size from UIScreen.main.bounds, which is only the window size on a
    full-screen iPhone in portrait (UX-26). Re-adding iPad, Vision or landscape
    needs adaptive layouts first."""
    problems = []
    rel = INFO_PLIST.relative_to(ROOT)
    if info.get("UISupportedInterfaceOrientations~iphone") != ["UIInterfaceOrientationPortrait"]:
        problems.append(f"{rel}: UISupportedInterfaceOrientations~iphone must be portrait only")
    if "UISupportedInterfaceOrientations~ipad" in info:
        problems.append(f"{rel}: the app is iPhone-only; remove UISupportedInterfaceOrientations~ipad")
    blocks = re.findall(r"buildSettings = \{(.*?)\n\t\t\t\};", PBXPROJ.read_text(encoding="utf-8"), re.S)
    for block in blocks:
        if not re.search(rf"PRODUCT_BUNDLE_IDENTIFIER = {re.escape(APP_BUNDLE_ID)}(?:Tests|UITests)?;", block):
            continue
        if not re.search(r"TARGETED_DEVICE_FAMILY = 1;", block):
            problems.append(f"{PBXPROJ.relative_to(ROOT)}: a stockme build configuration "
                            "sets TARGETED_DEVICE_FAMILY other than 1 (iPhone only)")
            break
        if re.search(r"SUPPORTED_PLATFORMS = [^;]*xros", block):
            problems.append(f"{PBXPROJ.relative_to(ROOT)}: a stockme build configuration lists visionOS "
                            "in SUPPORTED_PLATFORMS, but UIScreen.main does not exist there")
            break
    return problems


CHECKS = [check_purpose_strings, check_push_entitlement, check_privacy_manifest, check_export_compliance,
          check_iphone_portrait_only]


def main():
    with INFO_PLIST.open("rb") as f:
        info = plistlib.load(f)
    sources = [(p, p.read_text(encoding="utf-8")) for p in sorted(SOURCES.rglob("*.swift"))]
    if not sources:
        print(f"no Swift sources under {SOURCES.relative_to(ROOT)}")
        return 1
    problems = [problem for check in CHECKS for problem in check(info, sources)]
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(f"lint_ios_release_config: OK ({len(CHECKS)} check(s), {len(sources)} Swift files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
