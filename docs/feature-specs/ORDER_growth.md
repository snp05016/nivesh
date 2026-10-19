# Build order for cluster growth

Build in this order; each package lists the packages it builds on (all earlier in this list).

- growth-predictions-admin: Make the legacy QuantLab calibration dashboards admin-only and drop advanced_analysis from the PRO catalog (deps: none)
- growth-tiering-be: Honest tiering: PRO limited to the three enforced tools, an entitled_tier seam that defaults to the stored tier, honest beta copy (deps: growth-predictions-admin)
- growth-billing-mock-removal: Delete the mock upgrade and cancel routes and functions (deps: none)
- growth-share-card-ios: Delete the legacy 'Share as Image' export of AI analyses (deps: none)
- growth-docs: Billing runbook with the decision record, SEBI RA decision memo, B2B pilot playbook, share-card re-entry spec (deps: none)
- growth-billing-db: Billing schema: App Store columns on user_subscriptions and an append-only subscription_events table (deps: growth-docs)
- growth-billing-jws: Offline verification of App Store signed transactions (JWS with an x5c chain to Apple Root CA G3) (deps: none)
- growth-billing-be: Billing service and routes: launch flag, verified entitlement, status, signed-transaction verification with revoked-replay protection, health (deps: growth-billing-db, growth-billing-jws, growth-billing-mock-removal, growth-tiering-be)
- growth-billing-ios-core: iOS StoreKit 2 core: BillingManager, billing API client, models, launch and login wiring, privacy manifest (deps: growth-billing-be)
- growth-billing-ios-ui: iOS paywall on SubscriptionStoreView, subscription management, runtime upsell and deletion notice (deps: growth-billing-ios-core, growth-billing-mock-removal, growth-tiering-be)
