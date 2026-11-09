# Services

Every external service the product uses. Add a row before the service is adopted, after the founder approves it.
Never put a secret value in this file: name the place it lives instead.

| service | what it does | dashboard | where its secrets live | owner | rotation |
|---|---|---|---|---|---|

<!-- Integration wave only. The tunnel script refuses until this row exists, and the row is added only after the
founder approves the service (ask-before-adding). Copy it into the table above:

| Cloudflare quick tunnel | free tunnel from the internet to the local cluster, for real webhooks in the integration wave; testing only, no account, the URL changes at every start, 200 requests in flight, no server-sent events | https://try.cloudflare.com | none (no account, no secret) | founder | not applicable |
-->
