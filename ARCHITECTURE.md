# Architecture — Debugging Time Machine

## 1. Problem statement

When a bug is found, developers manually scroll through commit history trying
to find which change introduced it. This is slow, repetitive, and error-prone.
The Debugging Time Machine automates that search: given a failing test or bug
description, it finds the guilty commit and explains why, in plain language.

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Strong git tooling (`GitPython`), fast to prototype |
| Git operations | `GitPython` + native `git bisect` | Reliable, well-tested primitives instead of reinventing bisect |
| Agent / reasoning | Custom agent on NVIDIA Build (code model) + Google Gemini (planning/explanation) | Split by job per hackathon rate-limit guidance |
| Storage | SQLite | Lightweight, zero-setup, enough for commit/bug history in one repo |
| Interface | CLI (`python -m dtm analyze`) + optional GitHub Action | CLI is fastest to demo; Action shows real workflow integration |
| CI/CD | GitHub Actions | Required non-negotiable; runs lint + tests on every push |
| Testing | `pytest` + fixture repos with known "planted" bugs | Lets us prove accuracy with a measurable score |

## 3. Data model

**Commit record**
```
commit_hash, author, timestamp, files_changed, diff_summary, churn_score
```

**Bug report**
```
bug_id, description, failing_test_name, reported_at, status
```

**Analysis result**
```
bug_id, suspect_commit_hash, confidence_score, explanation, evidence[]
```

`evidence[]` stores the specific diff lines and test failure signals that
justify the confidence score — this is what lets the agent cite its reasoning
instead of just guessing.

## 4. High-level design

```
Bug report / failing test
        |
        v
[1] Git History Scanner  -->  pulls commit log + diffs for the affected files
        |
        v
[2] Bisect Engine          -->  runs automated git bisect across candidate commits,
        |                       re-running the failing test at each step
        v
[3] Pattern Matcher         -->  ranks candidate commits by churn, file risk history,
        |                        and proximity to the failure
        v
[4] LLM Reasoner (agent)    -->  explains WHY the top candidate is guilty, citing
        |                        the exact diff lines
        v
[5] Reporter                -->  outputs CLI report / GitHub PR comment
```

## 5. Human-in-the-loop points

- The tool never auto-reverts or auto-fixes code — it only reports findings
- A human confirms the suspect commit before any action is taken
- All agent output includes its evidence, so a human can verify the reasoning
  rather than blindly trusting it

## 6. Day 2 extensibility

Each stage (scanner, bisect engine, pattern matcher, reasoner, reporter) is a
separate module with a clean input/output contract. A new requirement (e.g.
"support multi-repo analysis" or "output as a web dashboard") can be added by
extending stage 5 (Reporter) without touching the bisect logic — this is the
seam we designed for the Day 2 surprise feature.
