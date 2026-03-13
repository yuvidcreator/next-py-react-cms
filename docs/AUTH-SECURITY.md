# PyPress — Auth & Security Architecture

## Cookie-Based JWT (httpOnly)

### Why httpOnly cookies instead of localStorage + Authorization headers?

1. **XSS immunity** — httpOnly cookies cannot be read by JavaScript. If an attacker injects
   malicious JS (via a plugin bug, XSS in content, etc.), they cannot steal the auth token.
   With localStorage, any JS on the page can read `localStorage.getItem("token")`.

2. **Automatic transmission** — Browser sends cookies on every request automatically. No need
   for frontend code to manually attach Authorization headers. Less code = fewer bugs.

3. **SameSite protection** — SameSite=Lax prevents cookies from being sent on cross-origin
   POST requests, blocking most CSRF attacks by default.

4. **Defense in depth** — We add a CSRF double-submit token ON TOP of SameSite cookies.
   An attacker from another domain cannot read our cookies (same-origin policy), so they
   cannot extract the CSRF token to set the required X-CSRF-Token header.

### Token Flow

```
LOGIN:
  Browser → POST /api/v1/auth/login {username, password}
  Backend → Validates credentials
  Backend → Creates access_token (JWT, 60min) + refresh_token (JWT, 30d) + csrf_token
  Backend → Sets 3 cookies on the response:
    pypress_access_token  (httpOnly=true,  SameSite=Lax,    Path=/)
    pypress_refresh_token (httpOnly=true,  SameSite=Strict, Path=/api/v1/auth)
    pypress_csrf_token    (httpOnly=false, SameSite=Lax,    Path=/)
  Backend → Stores hash(refresh_token) in pp_user_sessions
  Backend → Returns {message, user} — tokens NOT in response body

EVERY REQUEST:
  Browser → Sends cookies automatically (no JS needed)
  Backend → Reads access_token from cookie
  Backend → Validates JWT signature + expiry
  Backend → Extracts user_id, roles from token
  Backend → Verifies user still active in DB

MUTATIONS (POST/PUT/DELETE):
  Frontend JS → Reads pypress_csrf_token cookie (it's not httpOnly)
  Frontend JS → Sets X-CSRF-Token header with the value
  Backend → Compares cookie value with header value (double-submit check)
  Backend → Validates CSRF token JWT signature + expiry

TOKEN REFRESH:
  Frontend → Gets 401 on an API call (access token expired)
  Frontend → POST /api/v1/auth/refresh (browser sends refresh cookie automatically)
  Backend → Validates refresh_token from cookie
  Backend → Verifies session exists + is active in pp_user_sessions
  Backend → Token Rotation: issues entirely new tokens, invalidates old
  Backend → Sets new cookies, returns success

LOGOUT:
  Frontend → POST /api/v1/auth/logout
  Backend → Marks session as inactive in pp_user_sessions
  Backend → Clears all 3 cookies
  Result → Even if attacker somehow has the old tokens, the session is revoked in DB
```

### OAuth2.0 Social Login (Future — Phase 9+)

OAuth2.0 uses the SAME cookie-based flow. The only difference is how the user proves
their identity — instead of username/password, they authenticate via Google/GitHub/Facebook.

```
OAUTH LOGIN:
  Browser → GET /api/v1/auth/oauth/google
  Backend → Redirects to Google's consent screen
  User → Authenticates with Google
  Google → Redirects to /api/v1/auth/oauth/google/callback?code=...
  Backend → Exchanges code for Google access token
  Backend → Fetches user's email + profile from Google
  Backend → Creates or links user account in pp_users (oauth_provider="google")
  Backend → Sets the same 3 httpOnly cookies as regular login
  Backend → Redirects to /admin (user is now logged in)
```

The pp_users table has `oauth_provider` and `oauth_provider_id` columns ready for this.
A user can have BOTH a password and an OAuth link (they signed up with email, then linked Google).

### Session Management

Every active login creates a row in pp_user_sessions. This enables:
- Administrators can see all active sessions for any user
- Users can see their own active sessions (devices)
- Individual sessions can be revoked (force-logout a specific device)
- Refresh token rotation: old tokens are invalidated when new ones are issued
- Expired sessions are cleaned up automatically

### WordPress RBAC Compatibility

The role/capability system is an exact replica of WordPress:
- 5 default roles: administrator, editor, author, contributor, subscriber
- Each role has the same capabilities as WordPress
- Plugins can add custom roles and capabilities
- Capability checks happen on both frontend (UX) and backend (authoritative)
