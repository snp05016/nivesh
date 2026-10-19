"""Disclosure content service — compliance/regulatory-style disclosure copy
+ Key Fact Statement (KFS) computation for the loan & FD marketplaces.

Controller-Service-Repository: routers/compliance.py must only validate
HTTP input and call functions here.

DEMO-GRADE / ILLUSTRATIVE CONTENT ONLY
---------------------------------------
Except the privacy_policy / terms_of_use / grievance_officer /
data_sharing_governance notices (REG-12, UX-04: interim wording pending legal
review), every disclosure body below is clearly-labelled placeholder/demo
copy for a portfolio project. It is NOT real legal advice, NOT a real regulatory
filing, and does NOT reference any real SEBI/RBI registration or license
number. Nothing in this module should be treated as compliant legal text
for an actual regulated lending/fintech product.
"""
import hashlib
import json
import os
from decimal import Decimal
from typing import Optional, cast

from database import get_session
from models.db_models import FixedDepositScheme, LoanOffer
from services.finance_calculators import calculate_apr, calculate_emi
from services.product_bounds import check_product_bounds

_MOCK_DISCLAIMER = (
    "MOCK/DEMO CONTENT — illustrative placeholder text for a portfolio "
    "project only. This is NOT real legal advice, NOT a real regulatory "
    "filing, and does not reflect any real SEBI/RBI registration or "
    "license number."
)


def _section(heading: str, text: str) -> dict:
    return {"heading": heading, "text": text}


# FINSEC-04: the real data flow to LLM processors. Interim wording pending
# legal review; must stay in sync with the 'ai_processing' consent gate.
_AI_PROCESSORS_TEXT = (
    "Portfolio-based AI features (morning brief, red-flag summary, macro "
    "impact, daily action, trade-journal patterns, the PDF portfolio review and "
    "Copilot answers about your holdings) run only if you turn on the 'AI "
    "processing' consent in Settings > Account Security > Consents. It is "
    "off by default and you can withdraw it there at any time; without it these "
    "features show non-AI text. With it, the app sends what each feature needs "
    "(stock tickers and company names, day and overall P&L percentages, AI "
    "signals and red flags, your trade-journal notes, and your holdings for "
    "Copilot portfolio questions) to two third-party large-language-model "
    "processors: DeepSeek (servers in the People's Republic of China) and "
    "Anthropic (USA). Text you type into AI features (Copilot chat, the "
    "natural-language screener, idea brainstorming) is also sent to them to be "
    "answered. The app does not add your name, username or contact details to "
    "these requests."
)


# FINSEC-09: version of the privacy policy + terms of use the app shows at
# registration. Bump it whenever either text changes; iOS PolicyVersion.current
# (Models/KYCModels.swift) must match (trust-demo-kyc-ios copies it in the next
# client release; until then shipped builds send an older value, which
# auth_service.ACCEPTED_POLICY_VERSIONS still accepts). The bodies below are
# still interim wording: the owner/legal must supply the final text.
CURRENT_POLICY_VERSION = "2026-10-19"

# FINSEC-09: purpose text stored with every consent row, so each record says
# what the user agreed to. record_consent rejects any type not listed here.
CONSENT_PURPOSES = {
    "credit_check": "Run a credit check before a loan application is approved.",
    "sim_binding": "Check that loan/FD confirmations come from your registered device.",
    "data_sharing": "Share your application details with the loan/FD marketplace partners.",
    "ai_processing": "Send portfolio data to the AI processors named in the Privacy Policy.",
    "privacy_notice": "Acknowledge the Privacy Policy before creating an account.",
    "terms": "Accept the Terms of Use before creating an account.",
    "age_18_plus": "Confirm you are 18 or older before creating an account.",
    "disclaimer": "Acknowledge the not-financial-advice disclaimer.",
}

# I04: consents a user can grant and withdraw in the app, in display order.
# Acknowledgements (privacy_notice, terms, disclaimer and the age_18_plus
# attestation) are recorded at sign-up and are not toggles. Retired demo
# purposes (credit_check, sim_binding, data_sharing) are never listed.
# product_analytics appears only once platform-events-api adds it to
# CONSENT_PURPOSES.
USER_CONSENTS: dict[str, str] = {
    "ai_processing": "AI processing",
    "product_analytics": "Usage analytics",
}


def withdrawable_purposes() -> list[dict]:
    """GET /api/kyc/consent-purposes: the user-toggleable consents, each with
    the purpose text stored on its consent rows."""
    return [
        {"consent_type": k, "title": t, "purpose": CONSENT_PURPOSES[k]}
        for k, t in USER_CONSENTS.items()
        if k in CONSENT_PURPOSES
    ]

# REG-12: grievance officer contact (DPDP Rules / IT Rules 2021). Read from the
# server .env, which main.py loads before importing services.
_GRIEVANCE_NAME = os.getenv("GRIEVANCE_OFFICER_NAME", "").strip() or "to be published"
_GRIEVANCE_EMAIL = os.getenv("GRIEVANCE_OFFICER_EMAIL", "").strip() or "to be published"
_GRIEVANCE_TEXT = (
    f"Grievance Officer: {_GRIEVANCE_NAME}, email: {_GRIEVANCE_EMAIL}. Write "
    "to this address about your personal data, a consent, a deletion request "
    "or any other complaint about the app. We acknowledge a complaint within "
    "24 hours and aim to resolve it within 15 days. If you are not satisfied "
    "with the outcome, you can complain to the Data Protection Board of India."
)

STATIC_DISCLOSURES = {
    # REG-12: real notice (DPDP Act s.5, Apple 5.1.1(i)). Interim wording until
    # legal review; bump CURRENT_POLICY_VERSION whenever it changes.
    "privacy_policy": {
        "title": "Privacy Policy",
        "version": CURRENT_POLICY_VERSION,
        "body": (
            "This notice explains what personal data Nivesh collects, why, who "
            "receives it, how long it is kept, and how you can use your rights. "
            "You must be 18 or older to create an account."
        ),
        "sections": [
            _section(
                "What we collect",
                "Account: username, display name and a hashed password (never "
                "the password itself). What you enter: portfolio holdings and "
                "transactions, watchlists, price alerts, finance-tracker "
                "entries, forum posts and votes, and Copilot or other AI-feature "
                "questions. Technical data: the Apple push-notification token "
                "if you allow notifications, your IP address in consent records and "
                "rate-limit checks, and the app version. Each consent record "
                "stores the policy version, its purpose and the time. We do not "
                "collect government ID, bank or card details, or biometric data.",
            ),
            _section(
                "Why we use it",
                "To run your account and sign-in; to show your portfolio, "
                "watchlist, alerts and analysis; to answer AI-feature requests; "
                "to send the notifications you turned on; to run the forum and "
                "moderate it; and to keep the service secure (rate limits "
                "and audit logs). We do not sell your data, show "
                "ads or build advertising profiles.",
            ),
            _section("AI processors", _AI_PROCESSORS_TEXT),
            _section(
                "Other recipients",
                "Apple Push Notification service (USA) receives your device "
                "token and the alert text when a notification is sent. Our "
                "hosting provider stores the data on our servers. Market data, "
                "news and YouTube videos are fetched from public sources; no "
                "personal data is sent to them.",
            ),
            _section(
                "How long we keep it",
                "We keep your data while your account exists. To delete your "
                "account, use Settings > Account > Delete Account, or write to "
                "the Grievance Officer below with the username on your account. "
                "Your account is then erased "
                "after a 7-day grace period in which you can cancel: holdings, "
                "transactions, watchlists, alerts, journal entries, preferences "
                "and device tokens are deleted, past stock analyses are kept "
                "only without a link to you, and your username and display name "
                "are replaced. Forum posts stay under a deleted-account label, "
                "and consent and audit records are kept, with the IP address "
                "removed, as evidence of what was agreed to.",
            ),
            _section(
                "Your rights",
                "You can see and correct your data in the app. You can "
                "withdraw the AI-processing consent in Settings > Account "
                "Security > Consents; withdrawing is as easy as giving consent, and "
                "features that need that consent stop using your data. You can "
                "delete your account in Settings > Account > Delete Account. To "
                "ask for deletion by email, to get a summary of your data, or to nominate "
                "someone to exercise these rights for you, write to the "
                "Grievance Officer below.",
            ),
            _section("Grievance Officer", _GRIEVANCE_TEXT),
        ],
    },
    "terms_of_use": {
        "title": "Terms of Use",
        "version": CURRENT_POLICY_VERSION,
        "body": (
            "These terms apply to your use of Nivesh. By creating an account "
            "you confirm that you are 18 or older and agree to them."
        ),
        "sections": [
            _section(
                "Educational use only",
                "Nivesh shows market data, analysis and AI-generated text for "
                "educational purposes only. Nothing in the app is investment, "
                "tax or legal advice, and AI predictions are speculative. "
                "Nivesh is not registered with SEBI as an investment adviser or "
                "research analyst. Consult a SEBI-registered adviser before you "
                "invest; you alone are responsible for your investment decisions.",
            ),
            _section(
                "No trading",
                "The app does not place orders or hold funds.",
            ),
            _section(
                "Your account",
                "You must be 18 or older. Keep your password private. You can "
                "withdraw consents in Settings and ask for account deletion as "
                "described in the Privacy Policy.",
            ),
            _section(
                "Forum and acceptable use",
                "Do not post stock tips for payment, pump-and-dump or other "
                "market-manipulation content, other people's personal data, or "
                "unlawful, abusive or infringing material. Do not attack or "
                "scrape the service. We may remove content and suspend accounts "
                "that break these rules.",
            ),
            _section(
                "Data accuracy and liability",
                "Market data can be delayed or wrong. The app is provided as is, "
                "and we are not liable for losses arising from decisions based "
                "on it, to the extent the law allows.",
            ),
            _section("Grievances", _GRIEVANCE_TEXT),
        ],
    },
    "grievance_officer": {
        "title": "Contact & Grievance Officer",
        "version": CURRENT_POLICY_VERSION,
        "body": _GRIEVANCE_TEXT,
        "sections": [],
    },
    "data_sharing_governance": {
        "title": "Third-Party Data Sharing",
        "body": (
            "This page lists every third party that receives data from your "
            "account and why. See the Privacy Policy for what we collect."
        ),
        "sections": [
            _section(
                "Who receives your data",
                "Nivesh does not sell user data and does not use any data "
                "broker, ad network, or analytics reseller. Market data (prices, "
                "fundamentals) is fetched from public market-data sources for "
                "display purposes only. Apart from the hosting and Apple "
                "push-notification services needed to run the app (device token "
                "and alert text for price alerts), the third parties that receive "
                "data derived from your account are the AI processors below.",
            ),
            _section("AI processors", _AI_PROCESSORS_TEXT),
            _section(
                "Demo loan and FD marketplaces",
                "Lender and issuer names in the demo loan and FD marketplaces "
                "(for example 'Demo Lender A (fictional)') are fictional labels "
                "on illustrative offers. No application, booking or other data "
                "is shared with any real bank or NBFC, and no lending or deposit "
                "partnership exists.",
            ),
            _section(
                "Consent",
                "Sharing with a lending or deposit partner would need the 'data "
                "sharing' consent in Settings > Account Security > KYC Consents, "
                "which you can withdraw there at any time.",
            ),
        ],
    },
    "digital_lending_compliance": {
        "title": "RBI Digital Lending Guidelines — Illustrative Compliance Notes (Demo)",
        "body": _MOCK_DISCLAIMER,
        "sections": [
            "This demo app's mock loan marketplace illustrates several "
            "concepts from RBI's Digital Lending Guidelines for demo/portfolio "
            "purposes: upfront Key Fact Statement disclosure (see "
            "GET /api/v1/compliance/key-fact-statement), explicit consent "
            "capture before underwriting (services/kyc_consent_service.py), "
            "and no automatic recurring/undisclosed charges.",
            "This is NOT a real RBI-regulated digital lending product and "
            "carries no real Lending Service Provider (LSP) or NBFC "
            "registration. See also the 'lending_service_provider' disclosure.",
        ],
    },
    "lending_service_provider": {
        "title": "Lending Service Provider (LSP) Role — Illustrative Notes (Demo)",
        "body": _MOCK_DISCLAIMER,
        "sections": [
            _section(
                "Illustrative LSP role",
                "In this demo, the app plays the illustrative role of a "
                "'Lending Service Provider' — a marketplace surface that lists "
                "mock NBFC loan offers and mock FD schemes — without itself "
                "being the lender.",
            ),
            _section(
                "No real LSP registration",
                "There is no real LSP registration, no real co-lending "
                "agreement, and no real NBFC partnership backing this demo. "
                "All 'nbfc_name' / 'issuer_name' values in loan_offers and "
                "fixed_deposit_schemes are MOCK DATA.",
            ),
        ],
    },
    "apr_disclosure": {
        "title": "How APR Is Calculated In This App (Demo)",
        "body": _MOCK_DISCLAIMER,
        "sections": [
            _section(
                "Formula used",
                "For loan offers, the APR is the internal rate of return of the "
                "monthly EMIs against the net amount disbursed (loan amount "
                "minus the upfront processing fee), expressed as a nominal "
                "annual rate (monthly rate x 12), following the RBI Key Fact "
                "Statement method. It is computed for the amount and tenure you "
                "choose; the shortest tenure gives the highest APR, which is the "
                "'Max APR' shown on each offer and used to rank offers.",
            ),
            _section(
                "Fixed deposits",
                "For FD schemes, no fees are charged, so the disclosed APR "
                "equals the scheme's nominal annual interest_rate_pct.",
            ),
            _section(
                "Where this is used",
                "See GET /api/v1/compliance/key-fact-statement for the computed, "
                "per-offer/per-scheme breakdown (loan_amount, interest_rate, "
                "all_fees, apr, emi, net_disbursed_amount, total_repayable, tenure).",
            ),
        ],
    },
    "sim_binding_fraud_prevention": {
        "title": "SIM/Device-Binding Fraud Prevention — Illustrative Notes (Demo)",
        "body": _MOCK_DISCLAIMER,
        "sections": [
            _section(
                "This is a MOCK check",
                "The 'sim_binding' / device-binding check used to gate loan "
                "and FD confirmations (see services/kyc_consent_service.py:"
                "verify_device_binding()) is a MOCK DATA check — simulated for "
                "demo purposes — that only compares a submitted device_id "
                "against rows this app stored itself.",
            ),
            _section(
                "Not real telecom fraud detection",
                "There is no real telecom carrier integration, no real "
                "SIM-swap-detection API, and no real signal-based fraud "
                "scoring anywhere in this app. This disclosure exists so the "
                "demo does not misrepresent the strength of this control.",
            ),
        ],
    },
}


def get_disclosure(key: str) -> Optional[dict]:
    """Returns the static disclosure content dict for `key`, or None if the
    key is unknown."""
    content = STATIC_DISCLOSURES.get(key)
    if content is None:
        return None
    return {"key": key, **content}


def notice_hash(key: str) -> str:
    """sha256 hex of the disclosure content for `key`, stored on consent rows
    so a record can be matched to the exact notice text (FINSEC-09)."""
    return hashlib.sha256(
        json.dumps(STATIC_DISCLOSURES[key], sort_keys=True).encode("utf-8")
    ).hexdigest()


def _to_float(value) -> float:
    if value is None:
        raise ValueError("expected a non-null numeric field for KFS/APR computation")
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def irr_apr_pct(amount: float, fees: float, annual_rate_pct: float, months: int) -> tuple[float, float]:
    """(APR %, EMI): APR = 12 x the monthly IRR of the net disbursal (amount - fees)
    against `months` EMIs on the full amount (RBI KFS convention)."""
    fee_pct = fees / amount * 100 if amount else 0.0
    return (
        calculate_apr(amount, annual_rate_pct, months, fee_pct),
        round(calculate_emi(amount, annual_rate_pct, months), 2),
    )


def compute_key_fact_statement(
    loan_offer_id: Optional[int] = None,
    scheme_id: Optional[int] = None,
    amount: Optional[float] = None,
    tenure_months: Optional[int] = None,
) -> Optional[dict]:
    """Computes a structured Key Fact Statement (KFS) breakdown
    (loan_amount, interest_rate, all_fees, apr, emi, tenure) from real
    LoanOffer or FixedDepositScheme data.

    Exactly one of loan_offer_id / scheme_id must be provided by the
    caller (routers/compliance.py enforces this). `amount` and
    `tenure_months` are optional overrides within the offer/scheme's
    allowed range; when omitted, the offer/scheme's minimum amount and
    minimum tenure are used as representative illustrative figures.

    Returns None if the referenced offer/scheme is not found. Raises
    ProductBoundsError when an override is outside the offer/scheme range
    (or the product is inactive).
    """
    if loan_offer_id is not None:
        with get_session() as session:
            offer = session.query(LoanOffer).filter(LoanOffer.id == loan_offer_id).first()
            if offer is None:
                return None

            chosen_amount = amount if amount is not None else _to_float(offer.min_amount)
            chosen_tenure = tenure_months if tenure_months is not None else offer.min_tenure_months
            if amount is not None or tenure_months is not None:
                check_product_bounds(offer, chosen_amount, cast(int, chosen_tenure), "loan offer")
            chosen_tenure = max(1, cast(int, chosen_tenure))

            interest_rate_pct = _to_float(offer.interest_rate_pct)
            processing_fee_pct = _to_float(offer.processing_fee_pct)
            all_fees = round(chosen_amount * processing_fee_pct / 100, 2)

            # REG-05: IRR on the net disbursal, for the requested terms.
            apr = calculate_apr(chosen_amount, interest_rate_pct, chosen_tenure, processing_fee_pct)
            emi = calculate_emi(chosen_amount, interest_rate_pct, chosen_tenure)

            return {
                "source": "loan_offer",
                "loan_offer_id": offer.id,
                "nbfc_name": offer.nbfc_name,
                "loan_type": offer.loan_type,
                "loan_amount": chosen_amount,
                "interest_rate": interest_rate_pct,
                "all_fees": all_fees,
                "apr": apr,
                "apr_method": "irr_monthly_x12",
                "emi": round(emi, 2),
                "net_disbursed_amount": round(chosen_amount - all_fees, 2),
                "total_repayable": round(emi * chosen_tenure + all_fees, 2),
                "tenure_months": chosen_tenure,
                "disclaimer": _MOCK_DISCLAIMER,
            }

    if scheme_id is not None:
        with get_session() as session:
            scheme = (
                session.query(FixedDepositScheme).filter(FixedDepositScheme.id == scheme_id).first()
            )
            if scheme is None:
                return None

            chosen_amount = amount if amount is not None else _to_float(scheme.min_amount)
            chosen_tenure = tenure_months if tenure_months is not None else scheme.min_tenure_months
            if amount is not None or tenure_months is not None:
                check_product_bounds(scheme, chosen_amount, cast(int, chosen_tenure), "FD scheme")
            chosen_tenure = max(1, chosen_tenure)

            interest_rate_pct = _to_float(scheme.interest_rate_pct)
            # FD schemes charge no fees in this demo marketplace.
            all_fees = 0.0
            apr = interest_rate_pct

            return {
                "source": "fixed_deposit_scheme",
                "scheme_id": scheme.id,
                "issuer_name": scheme.issuer_name,
                "loan_amount": chosen_amount,
                "interest_rate": interest_rate_pct,
                "all_fees": all_fees,
                "apr": apr,
                "tenure_months": chosen_tenure,
                "disclaimer": _MOCK_DISCLAIMER,
            }

    return None
