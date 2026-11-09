# Prompts for the gate reviewers

Each prompt is self-contained. Pass files, never summaries. Run the agents in the foreground.

## Gate 2: `pavedline:reviewer`

- The diff file and the scanner output (lint, types, Semgrep, Trivy, Checkov, the boundary, row-level-security and contract checks), the spec, `GLOSSARY.md` and the decisions.
- "Review architecture, layering, duplication, error handling, types, naming, complexity, dead code, tenant scoping and the glossary. Check that every guard check has a test that creates the bad state and expects failure. You cannot run anything; verify by reading. End with one VERDICT line."

## Gate 3: security review

- Brief the `security-review` skill with: tenant isolation (`tenant_id` on every query, row-level security), authentication and authorisation on every route, secrets in code, logs or images, injection (SQL, shell, template), unsafe input parsing, sensitive data in logs, dependency and image findings from the scanners.

## Gate 3b: `pavedline:adversary`

- The diff file and the files it touches, nothing else. Put the threat model and the stop rule in the first paragraph: "A finding counts if it is a credential, money or tenancy defect in a common real-world idiom, a hang or ReDoS, a functional break, a regression or a fail-open. A contrived spelling of an already covered class is INFO. Each finding is a concrete input, the `file:line`, and the expected result. End with one ADVERSARIAL line."
- Trying to make a guard pass a bad state is part of the job: for each check in the diff, name the input that would get past it.

## Fix round: one narrow reviewer

- The previous findings, the new diff file. Ask three questions only: is each finding fixed, did anything regress, do the new tests fail on the old code. One VERDICT line.
