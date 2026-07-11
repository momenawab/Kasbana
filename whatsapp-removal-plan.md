# Plan — remove the dormant WhatsApp messaging channel (Phase F)

> Owner decided to **delete** (not revive) the WhatsApp *channel*. This is the
> full surgical removal. See [[whatsapp-fawry-delete-decision]].

## Keep (NOT WhatsApp channel — do not touch)

- **Merchant WhatsApp contact number** on the wallet pass — `accounts.MerchantSettings.whatsapp`
  → `wa.me` link (`wallets/contact.py`, passdata, google builders). A real contact feature.
- **`notif_whatsapp`** notification preference on settings.
- Free **wallet push** messaging (the surviving channel).

## Remove (the dormant paid channel + its plumbing)

### Backend

- `messaging/whatsapp.py` — delete (WhatsAppClient).
- `messaging/metering.py` — delete (WhatsApp quota metering).
- `messaging/models.py` — delete `WhatsAppUsage`; drop `channel` from `Campaign` +
  `Automation` (only PUSH remained → vestigial).
- `messaging/enums.py` — delete `MessageChannel` (PUSH-only is meaningless).
- `messaging/tasks.py` — delete `send_whatsapp`; the campaign send loop pushes only.
- `messaging/automation.py` — drop the WhatsApp branch + `_within_quota`; push only.
- `messaging/serializers.py`, `messaging/views.py` — drop `channel` in/out.
- `billing/plans.py` — drop `whatsapp` + `whatsapp_quota` from every plan and from
  `ENTITLEMENT_FLAGS`.
- `billing/entitlements.py` — drop `whatsapp` flag + `whatsapp_used`/`whatsapp_quota`
  (and the `messaging.metering` import).
- `billing/serializers.py` — drop `whatsapp_used`/`whatsapp_quota`.
- `billing/models.py` `Plan` — drop `whatsapp` + `whatsapp_quota` columns; update
  `as_limits()`.
- `console/serializers_plans.py` — drop `whatsapp`/`whatsapp_quota`.
- `config/settings/base.py` — drop the `MESSAGING.WHATSAPP` block.

### Migrations

- `messaging/` — drop `WhatsAppUsage`; remove `channel` from `Campaign`/`Automation`
  (a plain column drop — existing WHATSAPP/BOTH values are discarded with the column).
- `billing/` — drop `Plan.whatsapp` + `Plan.whatsapp_quota` (prod catalog columns;
  values are all False/0 per seed, so no data loss of meaning).

### Frontend

- **dashboard**: remove the campaign/automation **channel picker** (PUSH is implicit)
  and any WhatsApp quota display driven by `whatsapp_used`/`whatsapp_quota`.
- **admin**: remove `whatsapp` + `whatsapp_quota` from the plan editor.

### Tests

Update `test_messaging.py` (drop WhatsApp send/metering/channel cases; keep push),
`test_entitlements.py` (drop whatsapp flag/quota), `test_console_plans.py` /
`test_billing_http.py` (drop whatsapp_quota assertions). Keep the accounts
contact/notif tests untouched.

## Contract note

The entitlements response loses `whatsapp`/`whatsapp_used`/`whatsapp_quota`, and
campaign/automation lose `channel`. openapi regenerated; both frontends updated in
the same change so nothing reads a removed field.

## Gate / DoD

Full backend gate (ruff/black/mypy/check_openapi/pytest) + both frontend gates
(eslint/vitest/build) green. Bundle-promote with the Fawry removal on approval.
