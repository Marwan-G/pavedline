---
name: compliance
description: Asks the one compliance question of step 0 with its exact wording, takes three short follow-ups on yes, and records the answer as a decision. Used by the start skill; also use it when the compliance scope changes.
---

# compliance

Ask exactly this, word for word:

Should we design with compliance in mind (privacy laws such as GDPR, health or payment rules)? Recommended: yes.

Ask it in the question dialog (header `Q3 of 7`), with this sentence unchanged as the question text, "Yes (Recommended)" first and "No" second.

Say once that the answers stay in the user's own repository.

## If yes

Ask three short questions, one at a time, and nothing more. The first is a multi-select in the question dialog (`Q3.1 of 7`) with the four kinds as options; "Other" takes anything else, or "unknown". The other two (`Q3.2 of 7`, `Q3.3 of 7`) are open, so ask them in plain text as the `start` skill says.

1. Which kinds of data will the product hold: personal, health, payment, children's?
2. Which countries will it serve?
3. Is there a rule set the user already knows applies?

Record one decision, "compliance in scope", with the three answers in Context. Consequences: the answers feed the market research (step 1), the security rows of system design (step 4), the threat model, the data-processing agreements with vendors, and the launch checklist.

Do not interrogate beyond these three. Do not give legal advice. If the user does not know an answer, write "unknown" and move on.

## If no

Record a decision titled "compliance not in scope". In Consequences write one line: "Some data types carry legal duties regardless of this choice." Add a note that the launch checklist asks once more before go-live.

## Either way

The decision has Status `accepted`, today's date from `date +%F`, and "Stale outputs: none". The user can reopen it later with a new decision that supersedes it.
