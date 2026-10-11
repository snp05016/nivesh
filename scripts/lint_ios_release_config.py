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


CHECKS = [check_purpose_strings]


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
