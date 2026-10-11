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


CHECKS = [check_purpose_strings, check_push_entitlement]


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
