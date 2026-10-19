# Build order for cluster ai

Build in this order; each package lists the packages it builds on (all earlier in this list).

- ai-flags: Register the cluster's server-side flags (create the flag module only if none exists) (deps: none)
- ai-allowance-be: AI allowance endpoint plus Retry-After and AI_PAUSED codes (deps: ai-flags)
- ai-copilot-be: Copilot v2: computed portfolio answers, history scrub, advice backstop, reply provenance, reply fixtures (deps: ai-allowance-be)
- ai-copilot-ios: Copilot iOS: computed replies kept out of history, open-stock buttons, allowance line, quota copy, no signal chips (deps: ai-allowance-be, ai-copilot-be)
- ai-prose-eval: Offline prose eval harness for the research formatter (deps: none)
- ai-riskflags-be: Risk flags API: post-trade concentration checks (surveillance added later), at most 3 flags (deps: ai-flags)
- ai-riskflags-ios: Risk flags card on the stock Overview; one ASM/GSM source on screen (deps: ai-riskflags-be)
- ai-surveillance-data: CONDITIONAL: NSE REG_IND loader, 6-hourly refresh and ASM/GSM flags (build only after the OPS spike and legal sign-off) (deps: ai-flags, ai-riskflags-be)
- ai-research-race: Fix the on-demand research report insert race (IntegrityError returns 500) (deps: none)
- ai-i21-docs: Document the deferred I21 track record and 'My analyses' preconditions (no code) (deps: none)
