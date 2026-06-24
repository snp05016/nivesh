# Pull Request Description Template

## Summary
[Briefly describe the purpose of this PR. Which of the 5 phases of the fundamentals expansion does it cover?]

**Resolves Issues:** #[Issue_Number], #[Issue_Number]

## Changes Included
- **Backend Endpoints Added/Modified**:
  - `GET /api/v1/...`
- **iOS Files Added/Modified**:
  - `...View.swift`
- **Screenshots / Videos**:
  - [Required: Add visual proof of the UI implementation here]

## Risk Areas
- [e.g., Modifying StockProfileView layout, potential schema mismatch]

## Rollback Plan
- [e.g., Revert this PR, remove the tabs from the segmented control]

## Developer Checklist
- [ ] Code passes incremental verification locally.
- [ ] Ran `gitnexus_detect_changes()` to assess blast radius.
- [ ] Used `get_session()` for DB operations (Backend).
- [ ] No western scales (Million/Billion) used. Indian numbering strictly applied.
- [ ] UI strictly follows Banknote Aesthetic tokens (`Theme.bullGreen`, `Theme.Spacing.card`, etc.).
- [ ] All interactive elements trigger `HapticManager`.
- [ ] Tests executed and passing.
