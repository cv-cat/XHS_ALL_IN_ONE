# Rednote PC account and collection support

This integration adds a separate `rednote_pc` account type for users of the
international Rednote web application. The separation is deliberate: a Rednote
session must never fall back to the China-site adapter or host.

## Supported

- Import a Cookie string from your own existing Rednote Web login.
- Validate the session against `https://webapi.rednote.com` only.
- Require the expected Rednote user ID before storing a new account.
- Store the account as `rednote_pc`, separate from China-site PC accounts.
- Run manual and scheduled health checks with the Rednote adapter.
- Mark the account as `risk` instead of silently rebinding it if the authenticated
  user ID changes.
- Keep signing, transport, and unclassified runtime failures in `unknown` as
  temporarily unavailable; reserve `expired` and expiry notifications for a
  confirmed invalid session.
- Use an active, identity-anchored Rednote account to save a public profile's
  note list to the content library.
- Collect and save public note details from one or more
  `rednote.com/explore/...` links.
- Stop the current batch and demote the account from `active` when Rednote asks
  for verification, redirects to authentication, expires the session, or
  temporarily rejects the request.

Profile collection saves the public list entries returned by the profile
endpoint. It does not silently turn every entry into a full-detail or comment
crawl; use the direct-note flow when a full note response is required. The
direct-note flow saves each successful detail response to the content library.
Each successful detail is committed before the next URL is requested, so a
later verification or session failure does not discard the earlier results; the
crawler reports the partial saved count and refreshes the account status. A
metadata-only Rednote refresh preserves existing locally downloaded asset
associations, removes stale remote-only associations, and records the account
used for the latest refresh.
Rednote media URLs may be retained as note metadata, but this integration does
not automatically download those remote media files on the server.

## Not supported

- QR-code or SMS login for Rednote.
- Creator-account synchronization.
- Rednote search, comment-body collection, monitoring, publishing, or automated
  operations.
- Any guarantee that an unofficial web endpoint will remain stable.

Only use an account and session that you are authorized to access. Stop using
the integration if Rednote requests verification or if local law, the platform
terms, or your organization policy do not permit the intended use.

## Reproduce locally

1. Start the backend and frontend as described in the main README.
2. Open **账号矩阵 → 绑定账号 → Rednote PC → Cookie**.
3. Paste the Cookie string from your own already-authenticated Rednote Web
   session. The current adapter requires both `a1` and `web_session`.
4. Enter the expected user ID for that same login. It is normally the value
   after `/user/profile/` in your own Rednote profile URL. Optionally enter the
   expected nickname as a second identity check.
5. Select **校验并导入**, then use **检查** on the account card. Collection is
   blocked until the account is active and retains its verified user ID.
6. Open **数据抓取**, choose the Rednote collection account, then select either
   **采集公开主页笔记列表** or **采集单篇 Rednote 笔记详情** and provide your own
   public Rednote URL.

The import is rejected before persistence when the returned identity does not
match the expected ID or nickname. Later checks keep the original account ID and
set status to `risk` if the authenticated identity changes.

### Local API

The UI uses the authenticated local endpoints under `/api/xhs/crawl/`. The
profile-list contract lives at `/user-notes`; direct note details use `/data`
with `mode="note_urls"` and comments disabled. Unsupported Rednote modes fail
before the collection adapter is created.

Account binding is also available through the authenticated local API. Replace
every placeholder; never commit or post a real Cookie value.

```bash
curl -X POST http://localhost:8000/api/accounts/import-cookie \
  -H "Authorization: Bearer <local-access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "xhs",
    "sub_type": "rednote_pc",
    "cookie_string": "a1=<redacted>; web_session=<redacted>",
    "expected_external_user_id": "<your-rednote-user-id>",
    "expected_nickname": "<optional-expected-nickname>"
  }'
```

## Verification

The automated tests replace all Rednote network calls with deterministic fakes.
They verify host/origin selection, required Cookie names, identity mismatch
rejection before persistence, collection readiness, supported profile/detail
routes, partial-batch persistence, local-asset preservation, unsupported-mode
rejection, manual health checks, scheduled identity-drift handling, auto-task
account gates before Cookie-version queries or decryption, temporary-versus-expired
failure classification, and the absence of China-site adapter fallback.

```bash
python -m pytest tests/backend/test_api.py -k rednote
npm --prefix frontend run build
```

The implementation was also exercised locally with an authorized Rednote Web
session. No Cookie, account identity, target profile, or collected content is
included in this repository or in the automated fixtures.
