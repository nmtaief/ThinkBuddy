# Cloudflare & Edge Proxy Configuration for ThinkBuddy

## 1. Domain Routing & DNS Ingress
- **Ingress Domain:** `api.thinkbuddy.com`
- **Origin Server:** Single VM / Load Balancer running Caddy/Nginx reverse proxy on port 443.
- **Cloudflare Proxy Status:** **Proxied (Orange Cloud)**.
- **SSL/TLS Mode:** **Full (Strict)** with Cloudflare Origin CA certificate installed on Caddy/Nginx.

---

## 2. Server-Sent Events (SSE) & Real-Time Streaming Configuration
ThinkBuddy streams AI tutoring responses over HTTP SSE (`text/event-stream`) via `/v1/chat/messages`.
To prevent proxy buffering from breaking token-by-token streaming to mobile and web clients:

### Cloudflare Rules (Transform Rules / Configuration Rules)
1. **Disable Proxy Buffering:**
   - Under **Rules > Configuration Rules**, create a rule for `starts_with(http.request.uri.path, "/v1/chat/messages")`.
   - **Response Buffering:** Disabled.
2. **HTTP Timeouts:**
   - Enterprise: Increase `Proxy Read Timeout` to `120s`.
   - Free/Pro/Business: Keep client keep-alive pings active. ThinkBuddy Gateway sends SSE heartbeat comment `: heartbeat\n\n` every **15 seconds** (configured below the 100s default Cloudflare timeout).
3. **Compression Settings:**
   - Disable Brotli/Gzip compression on `/v1/chat/messages` streaming responses so the edge does not hold chunks waiting for compression blocks. Caddy emits header `Cache-Control: no-cache, no-transform`.

---

## 3. Web Application Firewall (WAF) & Rate Limiting
1. **Rate Limiting at Edge:**
   - Auth endpoints (`/v1/auth/exchange`, `/v1/auth/reauthenticate`): Max 30 requests per IP per minute.
   - General API (`/v1/*`): Max 300 requests per IP per minute.
2. **Bot Fight Mode:**
   - Enable Bot Fight Mode for web traffic.
   - **Bypass for Native Apps:** Create a WAF Skip rule for requests with verified Android `X-Client-Platform: android` and Play Integrity device tokens when verified by backend.
3. **Security Headers Enforced at Edge:**
   - `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Cross-Origin-Opener-Policy: same-origin`

---

## 4. Origin Server Reverse Proxy (Caddy / Nginx) Directives
In `infra/caddy/Caddyfile`:
```caddyfile
api.thinkbuddy.com {
    tls /etc/ssl/certs/origin-cert.pem /etc/ssl/certs/origin-key.pem

    # SSE streaming route - disable buffering
    handle /v1/chat/messages* {
        reverse_proxy gateway:8000 {
            flush_interval -1
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }

    # All API routes routed to Gateway
    handle /* {
        reverse_proxy gateway:8000 {
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }
}
```
