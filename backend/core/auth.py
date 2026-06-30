"""Authentication (contract §3.6 Auth).

``POST /api/v1/auth/token`` takes ``{email, password}`` and returns
``{access, refresh}``. Django's default User keys on ``username``, so we
authenticate by email here and issue SimpleJWT tokens.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate, get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Obtain a token pair using email + password instead of username.

    Setting ``username_field`` makes the parent build an ``email`` input field;
    we override ``validate`` to resolve the user by email and authenticate.
    """

    username_field = "email"

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        email = attrs.get("email", "")
        password = attrs.get("password", "")

        user = User.objects.filter(email__iexact=email).first()
        authenticated = authenticate(
            request=self.context.get("request"),
            username=user.get_username() if user else None,
            password=password,
        )
        if authenticated is None or not authenticated.is_active:
            raise AuthenticationFailed("No active account found with the given credentials.")

        refresh = self.get_token(authenticated)
        return {
            "access": str(refresh.access_token),  # type: ignore[attr-defined]
            "refresh": str(refresh),
        }


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    throttle_scope = "auth"  # brute-force protection on login (Phase 1.8)
