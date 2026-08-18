# Google Safe Browsing Warning

Date: 2026-08-18

## Finding

Chrome showed a red Safe Browsing phishing warning when opening a Thesos email-verification link at `chat.cephalonthesos.com/verify`. This is a Google Safe Browsing classification, not a TLS or Cloudflare error.

Google's public diagnostic currently reports that some pages on `cephalonthesos.com` are unsafe in the phishing/social-engineering category, while the `chat` host and `/verify` path report no available data. Google notes that warnings can vary by browsing context, browser cache, and URL.

## Origin audit

- Production was running the expected pinned release `bff8c520`.
- Web, API, and worker containers had no unexplained filesystem changes.
- `/` and `/verify` returned the expected application; apex and `www` redirected to `chat`.
- Content Security Policy restricted scripts and connections to first-party content plus Cloudflare Turnstile.
- Ports 80/443 were restricted to Cloudflare at the host firewall.
- Resend SPF and DKIM records were present. DMARC was not configured.
- No public malware or phishing scan results were found for the domain.

## Likely cause

The domain is extremely new and immediately presents account registration, password fields, and tokenized verification links. That combination can resemble a phishing page to automated systems. A Chrome password-reuse signal on the friend's registration flow is another plausible trigger; the friend should not disclose the password, only whether Chrome warned that it was reused or saved for another site.

This investigation found no evidence of an injected page, malicious redirect, or compromised deployment, but the Safe Browsing classification should be treated as real until Google clears it.

## Follow-up

1. Add `cephalonthesos.com` to Google Search Console as a Domain property.
2. Check **Security & Manual Actions > Security issues** and inspect any sample URLs.
3. Submit a review if the legitimate authentication pages were classified incorrectly.
4. Submit the false-positive report at <https://safebrowsing.google.com/safebrowsing/report_error/>.
5. Add a basic DMARC record for the sending domain.
6. Make the login surface explicitly identify Thesos as an unofficial Warframe knowledge assistant and its operator.
7. Resend the verification email because the token in the screenshot is exposed.

Do not ask users to bypass the Chrome warning until the review is complete.
