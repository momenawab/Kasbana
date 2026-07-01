"""Merchant JWT authentication — SimpleJWT plus the impersonation guard (Phase 6).

For a normal merchant token this behaves exactly like the stock
``JWTAuthentication``. A token minted by ``console.impersonation`` additionally
carries ``impersonation_id``, and for those we enforce, on every request:

- the ``Impersonation`` row is still active (an admin "end" or its expiry kills
  the token server-side, refresh-proof because none is ever issued);
- billing endpoints are off-limits (impersonation is never for billing actions);
- every mutating request is tagged into the admin audit log, so anything the
  admin does *as* the merchant stays attributable to the admin.
"""

from __future__ import annotations

from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication

from console.impersonation import IMPERSONATION_ID_CLAIM

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
BILLING_PREFIX = "/api/v1/billing"


class MerchantJWTAuthentication(JWTAuthentication):
    def authenticate(self, request: Request):  # type: ignore[override]
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result

        imp_id = token.get(IMPERSONATION_ID_CLAIM)
        if imp_id:
            # Local import: console is the admin app; keep the merchant auth
            # path import-light for the non-impersonated 99% of requests.
            from console.models import AdminAuditLog, Impersonation

            imp = Impersonation.objects.filter(id=imp_id).select_related("admin").first()
            if imp is None or not imp.is_active():
                raise AuthenticationFailed("Impersonation session has ended.")
            if request.path.startswith(BILLING_PREFIX):
                raise PermissionDenied("Impersonated sessions cannot access billing.")
            # /me surfaces it -> dashboard banner (dynamic attr; not on Request's type)
            request.impersonation = imp  # type: ignore[attr-defined]
            if request.method not in SAFE_METHODS:
                AdminAuditLog.objects.create(
                    actor=imp.admin,
                    actor_email=imp.admin_email,
                    action="impersonation.request",
                    target_type="merchant",
                    target_id=str(imp.merchant_id),
                    metadata={"method": request.method, "path": request.path},
                    ip=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:256],
                )
        return user, token
