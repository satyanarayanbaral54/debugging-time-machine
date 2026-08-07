# AGENTS.md — Agent rules for Debugging Time Machine

These are the rules every AI agent (coding agent or the tool's own runtime
agent) must follow while working on this project.

## 1. Coding agent rules (Cline / Roo Code, while building)

1. **Always work in Plan mode before Act mode** for any change touching more
   than one file. State the plan, get human approval, then execute.
2. **Never invent APIs or library methods.** If unsure whether something
   exists, say so and ask, rather than guessing.
3. **Small, reviewable diffs.** No single commit should touch more than one
   module (scanner, bisect engine, pattern matcher, reasoner, reporter)
   unless explicitly told to.
4. **Commit after every working increment**, not at the end of a session.
   No end-of-day commit dumps.
5. **Never commit secrets.** API keys live only in `.env`, which is
   git-ignored. If a key appears in a diff, stop and flag it.
6. **Respect provider quotas.** Use NVIDIA models for the main coding loop,
   Gemini for planning/explanation steps, and fall back to Groq/OpenRouter on
   a 429 error rather than retrying the same provider.

## 2. Runtime agent rules (the tool's own reasoning agent, in production)

1. **Evidence before conclusions.** The agent must never report a "guilty"
   commit without citing the specific diff lines or test signal that support
   it. No evidence, no verdict — report "inconclusive" instead.
2. **No silent actions.** The agent only reports findings. It never reverts,
   rewrites, or merges code on its own.
3. **Confidence scores are mandatory.** Every result includes a confidence
   score (0-100%) so a human can judge how much to trust it.
4. **Say "I don't know" when uncertain.** If the bisect search is inconclusive
   or the evidence is weak, the agent must say so plainly rather than
   forcing a guess.
5. **Stay within the repo.** The agent only reads the git history and files
   of the target repository — no external network calls beyond the
   configured LLM provider.

## 3. Custom agent (required non-negotiable)

`agents/bisect_reasoner.py` — a custom agent that takes bisect engine output
and produces a cited, human-readable explanation. This is the "1 custom
agent" required by the hackathon rules.

## 4. Custom skill (required non-negotiable)

`skills/git_churn_analysis.py` — a reusable skill that scores any file's
historical bug-proneness from its git log (frequency of bug-fix commits,
revert count, churn rate). Used by the Pattern Matcher stage. This is the
"1 custom skill" required by the hackathon rules, and is documented in
`AGENTS_AND_SKILLS.md`.

## 5. Review checklist before every commit

- [ ] Does this change stay inside one module's responsibility?
- [ ] Are there tests for the new behavior?
- [ ] Is the commit message specific (not "fix stuff")?
- [ ] No secrets, no hardcoded keys?
- [ ] Does CI still pass?
