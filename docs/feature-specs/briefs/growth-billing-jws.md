# Feature package growth-billing-jws: Offline verification of App Store signed transactions (JWS with an x5c chain to Apple Root CA G3)

Cluster: growth (Monetization, growth and bold bets); area: backend
Features covered: 38 I43 Real billing with StoreKit 2

## Files (create or modify)
- backend/services/apple_jws.py
- backend/certs/AppleRootCA-G3.cer
- backend/requirements.txt
- backend/tests/apple_jws_testkit.py
- backend/tests/test_apple_jws.py

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: HUMAN:pro-catalog-decision, HUMAN:engine-stage3-scheduled. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.
- Owner prerequisites (do NOT block on them; build behind the flag and list them in human_actions): HUMAN:pro-catalog-decision, HUMAN:engine-stage3-scheduled

## Description
Wave 2. Start only after HUMAN:pro-catalog-decision (tools sold) and HUMAN:engine-stage3-scheduled.

A pure verifier that adds no package: PyJWT[crypto] (requirements.txt:40) already installs cryptography. It mirrors Apple's app-store-server-library SignedDataVerifier:
- chain length 3;
- leaf OID 1.2.840.113635.100.6.11.1;
- intermediate OID 1.2.840.113635.100.6.2.1;
- certificate validity checked at signedDate;
- no online OCSP.

1. backend/services/apple_jws.py.
- Constants:
  - APPLE_ROOT_CA_G3_SHA256 = '63343abfb89a6a03ebb57e9b3f5fa7be7c4f5c756f3017b3a8c488c3653e9179' (from Apple's root-certificate lists);
  - LEAF_OID and INTERMEDIATE_OID, as above;
  - DEFAULT_ROOT_PATH = Path(__file__).resolve().parent.parent / 'certs' / 'AppleRootCA-G3.cer'.
- class InvalidJWS(ValueError).
- load_root_der(path=None, *, expected_sha256=APPLE_ROOT_CA_G3_SHA256) -> bytes:
  - reads DER from path, else from env APPLE_ROOT_CA_PATH, else from DEFAULT_ROOT_PATH;
  - raises InvalidJWS('root CA missing') if the file is absent;
  - raises InvalidJWS('root CA fingerprint mismatch') when the hashlib.sha256 digest differs;
  - expected_sha256=None skips the check (tests only);
  - no caching here; callers read it per call.
- verify_signed_payload(jws: str, *, root_der: bytes, now: datetime | None = None) -> dict:
  (a) header = jwt.get_unverified_header(jws). Require alg == 'ES256' and x5c to be a list of exactly 3 strings.
  (b) Load the leaf and intermediate from standard-base64 DER with cryptography.x509.load_der_x509_certificate, and the root from root_der. Ignore x5c[2], as Apple's library does.
  (c) Call leaf.verify_directly_issued_by(intermediate) and intermediate.verify_directly_issued_by(root). These need cryptography >= 40.
  (d) The leaf must carry LEAF_OID and the intermediate INTERMEDIATE_OID, checked with extensions.get_extension_for_oid(ObjectIdentifier(...)). ExtensionNotFound becomes InvalidJWS.
  (e) payload = json.loads(jwt.PyJWS().decode(jws, key=leaf.public_key(), algorithms=['ES256'])).
  (f) The effective time is signedDate (ms epoch) when present, else now. All three certificates must satisfy not_valid_before <= effective <= not_valid_after; use the *_utc properties when present, else set tzinfo to UTC. Reject a signedDate more than 300 s after now.
  - Every failure (jwt, cryptography, binascii or json exceptions) is re-raised as InvalidJWS with a short reason that never includes the token.
  - The payload dict is returned unchanged.

2. backend/certs/AppleRootCA-G3.cer.
- Download https://www.apple.com/certificateauthority/AppleRootCA-G3.cer and confirm that shasum -a 256 equals the constant.
- With no network, leave the file out and report it. Billing then reports apple_root_ca_invalid and stays unavailable, which fails closed.

3. backend/requirements.txt: add 'cryptography>=42.0  # imported directly by services/apple_jws.py; already installed via PyJWT[crypto]'. This adds no new package.

4. backend/tests/apple_jws_testkit.py. pytest does not collect it, because it has no test_ prefix.
- make_chain(leaf_oid=True, intermediate_oid=True, leaf_valid_from=None, leaf_valid_to=None) uses x509.CertificateBuilder and EC P-256 keys to build:
  - a self-signed CA root;
  - an intermediate CA carrying x509.UnrecognizedExtension(ObjectIdentifier(INTERMEDIATE_OID)) whose value is the two bytes 05 00 (a DER NULL);
  - a leaf carrying the LEAF_OID extension.
  It returns a dataclass with root_der, intermediate_der, leaf_der and leaf_key.
- sign(payload, chain, alg='ES256', x5c=None) = jwt.encode(payload, chain.leaf_key, algorithm=alg, headers={'x5c': x5c or [b64(leaf), b64(intermediate), b64(root)]}).
- transaction_payload(**overrides) returns a valid auto-renewable transaction:
  - bundleId 'test.bundle';
  - productId 'test.pro.monthly';
  - transactionId and originalTransactionId '2000000001';
  - type 'Auto-Renewable Subscription';
  - environment 'Sandbox';
  - appAccountToken absent unless overridden;
  - purchaseDate, originalPurchaseDate and signedDate = now, and expiresDate = now + 30 days, all as ms ints;
  - inAppOwnershipType 'PURCHASED'.

## Acceptance checks
1. PYPARSE and PYRIGHT are clean.
2. backend/tests/test_apple_jws.py checks:
- a valid chain returns the exact payload;
- a tampered payload segment raises InvalidJWS;
- a leaf from an unrelated chain raises InvalidJWS;
- a leaf without the OID raises InvalidJWS;
- an intermediate without the OID raises InvalidJWS;
- an x5c of length 2 raises InvalidJWS;
- an HS256 header raises InvalidJWS;
- a signedDate after the leaf's validity raises InvalidJWS;
- a signedDate 1 hour in the future raises InvalidJWS;
- load_root_der with a wrong fingerprint raises InvalidJWS;
- when backend/certs/AppleRootCA-G3.cer exists, its sha256 equals APPLE_ROOT_CA_G3_SHA256 (otherwise pytest.skip).
3. The tests use no network and run in CI.

## Cluster spec
docs/feature-specs/spec_growth.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

## Constraints (hard rules)
- Fix track and engine: the audit-fix track and the Research Engine are integrated (or integrating) on the same line. Build on their code; never re-implement what they already do. If a dependency is not in the code yet, do not stub or duplicate it: build your part against the documented interface behind the feature flag, and report it.
- Research Engine decisions win: every number is computed by validated code; DeepSeek only phrases computed facts behind the grounding validator; no buy/sell/hold, price targets or stock-level probabilities; English-only v1; legacy analysis routes are retired (410); track record and cohort display only when RESEARCH_SEBI_RA_REG_NO is set. Where a feature conflicts, the engine decision is the default and the feature sits behind a flag that is off.
- Compliance: no advice, recommendations, ratings or targets; no performance claims in marketing or share content; never claim SEBI registration; DPDP Act 2023 / Rules 2025 (consent, purpose limitation, erasure, export, breach logging); App Store rules (5.1.1 account deletion, StoreKit for digital goods, privacy manifest).
- Engineering: ORM models only in backend/models/db_models.py; schema changes only via a new Alembic revision with a RANDOM 12-hex id chained to the current single head; DB access through get_session(); thin routers, logic in services/; Lakhs/Crores; iOS colours only Theme.* tokens, stripEmoji on AI text, no GeometryReader inside ScrollView/HStack, no nested NavigationStack, ViewBuilder helpers over 5 lines become View structs; free, terms-respecting data sources only (AMFI NAV files, NSE/BSE public files, yfinance) with an honest User-Agent (contact https://github.com/snp05016/nivesh); no new third-party dependency unless the brief names one; every new surface behind a server-side feature flag (reuse the project's flag mechanism) that degrades gracefully; every feature with tests.
- Backend code cannot be executed here: static checks plus hermetic tests that are correct by construction. iOS: swiftc -parse only. ml-engine code can be executed and its tests must pass.

## Local test commands
- ml-engine: cd <your worktree>/ml-engine && PYTHONDONTWRITEBYTECODE=1 backend/venv/bin/python -m pytest -p no:cacheprovider -q <tests>
- backend: static checks only (pycheck, pyright_delta); tests hermetic and correct by construction.
- iOS: swiftc -parse only; verify every symbol you use by grepping its declaration.
