# Rotating an integration token

Workspace administrators can create and revoke integration tokens in
**Workspace settings > Integrations**. Before revoking a token, create its
replacement and update the external integration. This avoids an interruption
to ticket ingestion.

Tokens are shown only once when created. Store them in an approved secret
manager, not in ticket comments, email, browser notes, or source code.

If a token may have been exposed, revoke it immediately, create a replacement,
and review the integration activity log for unexpected requests.
