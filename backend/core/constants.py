# core/constants.py — single home for tunables both phases rely on.
# Frozen in Phase 1.0 (contract §3.3).

# Anti-fraud (used by loyalty/, enforced server-side via core/ledger.py)
STAMP_COOLDOWN_SECONDS = 30  # min seconds between stamps on one card
MAX_STAMPS_PER_CARD_PER_DAY = 12
MAX_STAMPS_PER_STAFF_PER_MIN = 20

# Tokens
AUTH_TOKEN_BYTES = 24  # CustomerCard.auth_token entropy
ENROLL_TOKEN_BYTES = 16

# Enrollment
ENROLL_TOKEN_TTL_DAYS = None  # None = never expires

# Wallet
PASS_BARCODE_PREFIX = "WLA"  # barcode payload prefix

# Referrals — bonus stamps granted to referrer + referee when a referral converts.
REFERRAL_BONUS_STAMPS = 1

# Pagination
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
