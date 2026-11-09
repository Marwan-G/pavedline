# Waiting on you

Every step only the founder can take: logins, dashboard clicks, funds, accounts, approvals of a named service,
rotations, a "go". The agent lists an item here the moment it finds one, and removes it only when the founder says it
is done.

Format, one line per item:

`- Fn · what · where/how · what it unblocks`

Open items are the lines that start with `- F`; the session-start hook prints them.

## Open items


## Examples (indented on purpose: these are not open items)

The integration wave needs two accounts only the founder can create. The agent never creates an account and never sees
a key: the keys go into the gitignored `.env.local`, never into chat, a file in git or a prompt.

    - F7 · create the Clerk development instance · dashboard.clerk.com > Create application (development instance, free); copy the publishable and secret keys and the JWKS URL into .env.local (AUTH_ISSUER, AUTH_AUDIENCE, AUTH_JWKS_URL; the secret key stays in .env.local only) · unblocks real sign-in and the Clerk webhook in the integration wave
    - F8 · add the Clerk webhook endpoint · Clerk dashboard > Configure > Webhooks > Add endpoint with the URL tunnel.sh prints plus /webhooks/clerk; copy the Signing Secret (whsec_...) into .env.local as WEBHOOK_CLERK_SECRET and run scripts/local_secrets.sh · unblocks the real-webhook check through the tunnel
    - F9 · create the Stripe sandbox · dashboard.stripe.com > Sandboxes > Create (test mode only, no card needed); copy the test secret key into .env.local (STRIPE_SECRET_KEY) · unblocks payment test mode in the integration wave
    - F10 · run `stripe login` once (Stripe CLI, browser pairing) and `stripe listen --forward-to http://api.localtest.me:8080/webhooks/stripe`; copy the whsec_... it prints into .env.local as WEBHOOK_STRIPE_SECRET · unblocks Stripe webhooks locally (no tunnel needed)
    - F11 · approve the Cloudflare quick tunnel (free, no account, testing only) · answer yes to the question, then the row goes into SERVICES.md · unblocks tunnel.sh
