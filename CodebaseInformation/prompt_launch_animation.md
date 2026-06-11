# NIVESH — LAUNCH ANIMATION PROMPT

---

```xml
<system>

<identity>
You are implementing the Nivesh launch animation — the first 5.8 seconds every user experiences.
This is not a splash screen. It is a statement. Premium Indian financial intelligence, presented
like a Reserve Bank document being authenticated. Every frame is intentional. Nothing bounces.
Nothing is cute. It is weighted and deliberate.
</identity>

<animation_timeline>

TOTAL DURATION: 5.8 seconds. Phases overlap intentionally — do not play them sequentially.

────────────────────────────────────────────────────────────
PHASE 0 — Void                            0.0s → 0.4s
────────────────────────────────────────────────────────────
Deep black background. Nothing visible. 0.4 seconds of pure darkness.
This silence is intentional — it makes Phase 1 land harder.

────────────────────────────────────────────────────────────
PHASE 1 — Guilloche Emergence             0.4s → 2.2s
────────────────────────────────────────────────────────────
Three overlapping sine-wave paths materialise from the screen center outward.
Each wave is offset 120° from the others. They expand horizontally as if being
engraved in real time — the drawing progress animates 0 → 1 over 1.8s, easeInOut.
At full progress the pattern spans the full screen width, roughly 120pt tall,
vertically centred.
Color: securityGold at 18% opacity. This is the security-pattern-on-a-banknote moment.

────────────────────────────────────────────────────────────
PHASE 2 — Security Thread Sweep          1.6s → 2.4s
────────────────────────────────────────────────────────────
A 1.5pt vertical line in securityGold sweeps from the left edge to the right edge
of the screen over 0.8s, easeInOut.
As the line passes the horizontal center, a 40pt-wide vertical band behind it
briefly pulses securityGold at 4% opacity — a flash of light catching the thread —
then fades over 0.2s. This overlaps with the guilloche still drawing.

────────────────────────────────────────────────────────────
PHASE 3 — Wordmark                       2.2s → 2.9s
────────────────────────────────────────────────────────────
"NIVESH" appears at screen center. No scale. No bounce. It resolves into existence
like a stamp pressing paper — opacity 0 → 1 over 0.4s, easeOut.
Font: officialStamp style, size 42, letter-spacing 8, heaviest available weight.
Color: inkPrimary (warm white in dark mode).

At 2.4s: "निवेश" appears directly below in the hindi font, size 16, inkSecondary.
Opacity 0 → 1 over 0.35s, easeOut. Sits 6pt below the wordmark baseline.

────────────────────────────────────────────────────────────
PHASE 4 — Subtitle Stamp                 2.9s → 3.7s
────────────────────────────────────────────────────────────
"RESERVE BANK OF INTELLIGENCE" appears below the hindi subtitle.
Font: officialStamp style, size 8, letter-spacing starts at 6 and collapses to 2
simultaneously as opacity goes 0 → 1 over 0.5s, easeOut.
Color: inkTertiary (faded). Gap from hindi subtitle: 8pt.
The collapsing letter-spacing makes it feel like a stamp pressing down.

────────────────────────────────────────────────────────────
PHASE 5 — Gold Underline Draw            3.5s → 4.2s
────────────────────────────────────────────────────────────
A 0.75pt horizontal line in securityGold draws left to right beneath the "NIVESH"
wordmark (12pt below its baseline). Width animates from 0 → exact wordmark width
over 0.6s, easeInOut. The line expands from the leading edge only.

────────────────────────────────────────────────────────────
PHASE 6 — Hold                           4.2s → 5.0s
────────────────────────────────────────────────────────────
Everything stationary. 0.8 seconds of the complete composition at rest.
"RESERVE BANK OF INTELLIGENCE" should feel true by the time this ends.

────────────────────────────────────────────────────────────
PHASE 7 — Dissolution                    5.0s → 5.8s
────────────────────────────────────────────────────────────
The entire animation view fades to black over 0.6s, easeIn.
The app's home screen is revealed beneath it — not a cut, not a push.
It simply was not visible. Now it is.
</animation_timeline>

<visual_spec>
Background: Theme.canvas — deep near-black in dark mode. The launch animation is always
presented in dark mode regardless of the device's system setting. It is a branded moment.

Color palette used (Theme tokens only — no raw values):
  - Theme.canvas          Background
  - Theme.inkPrimary      "NIVESH" wordmark
  - Theme.inkSecondary    "निवेश" hindi subtitle
  - Theme.inkTertiary     "RESERVE BANK OF INTELLIGENCE"
  - Theme.securityGold    Guilloche waves, security thread, underline

All monetary output anywhere in the animation: IndianFormatter only. No "Million", no "Billion".

Typography rules (AGENTS.md §2.4):
  - "NIVESH": officialStampFont, size 42, tracking 8, heaviest weight
  - "निवेश": hindiFont, size 16
  - "RESERVE BANK OF INTELLIGENCE": officialStampFont, size 8, tracking animates 6 → 2
  - No .system(size:) fonts anywhere
</visual_spec>

<success_criteria>
  ✓ Total duration is 5.8 seconds from first frame to screen clear
  ✓ Guilloche pattern expands from center — not a static texture, it draws live
  ✓ Security thread sweep and guilloche drawing overlap (thread at 1.6s, guilloche 0.4–2.2s)
  ✓ "NIVESH" never scales or bounces — opacity only, it stamps in
  ✓ Underline width matches the wordmark width exactly on all screen sizes
  ✓ Subtitle letter-spacing collapse is visible and feels like a stamp
  ✓ 0.8s hold feels deliberate, not like a bug
  ✓ Dissolution is a clean fade — no jump cut, no flash
  ✓ The home screen initialises DURING the animation, not after it ends
  ✓ No raw hex colors, no magic numbers — all Theme.* and Theme.Spacing.* tokens
  ✓ Runs at 60fps on a real device — no dropped frames during Canvas drawing
  ✓ Plays exactly once per launch — does not replay on app foreground re-entry
  ✓ Centred composition holds correctly on iPhone SE (375pt) and Pro Max (430pt)
</success_criteria>

<absolute_constraint>
The home screen must be initialised and loading data DURING the animation — never blocked by it.
By the time dissolution completes the user should land on a screen with data, not a spinner.
No raw colors. No magic spacing. No system fonts. All Theme.* tokens throughout.
The animation plays once. It fires onComplete() at 5.6s. It is never called again.
</absolute_constraint>

</system>
```

---

## Timeline at a glance

```
0.0 ──── 0.4 ───────────────── 2.2 ── 2.4 ── 2.9 ── 3.5 ── 4.2 ────── 5.0 ── 5.8
│ VOID  │ GUILLOCHE DRAWS       │WORDS │HINDI │STAMP │LINE  │  HOLD   │FADE  │ END
│       │ (3 sine waves expand) │      │      │      │draws │         │      │
│               THREAD SWEEPS 1.6s──2.4s                              │      │
```

## Optional enhancements

- Add `HapticManager.impact(.medium)` at 2.2s (wordmark) and `HapticManager.success()` at 4.2s (underline complete) for tactility.
- Add a low-opacity `₹` symbol (size ~280pt, securityGold at 4%) centred as a background watermark, fading in with the guilloche at Phase 1.
- For a shorter 4.5s version: trim Phase 6 (hold) from 0.8s → 0.3s and move dissolution to 4.3s.
