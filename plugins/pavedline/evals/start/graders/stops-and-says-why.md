---
type: regex
target: trace
pattern: 'container runtime|colima|docker'
flags: i
---
The eval sandbox has no container runtime, so the machine check fails: step 0 must stop and name what is missing.
