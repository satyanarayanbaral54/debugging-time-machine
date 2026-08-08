# Product Requirements Document

## User Story 1: Run analysis on a repository

As a developer, I want to run debugging analysis against a git repository, so that I can identify the commit most likely responsible for a bug.

### Acceptance Criteria 1

- [x] I can run the CLI command with a repository path, a known good commit, a known bad commit, and a test command.
- [x] The tool evaluates candidate commits in a git worktree and reports the likely culprit.
- [x] The command exits successfully when the analysis completes.

## User Story 2: Get a plain-language explanation

As a developer, I want to receive a plain-language explanation of why a suspect commit likely caused the bug, so that I can understand the root cause quickly.

### Acceptance Criteria 2

- [x] The tool produces an explanation for the top candidate commit.
- [x] The explanation references the commit SHA and the relevant diff details.
- [x] The explanation is written in clear, human-readable language rather than raw technical output.

## User Story 3: Get structured reports

As a developer, I want to receive analysis results in markdown or JSON, so that I can share them in the terminal, docs, or automation workflows.

### Acceptance Criteria

- [x] The tool supports both markdown and JSON output formats.
- [x] The markdown report highlights the likely guilty commit in a readable incident-style layout.
- [x] The JSON report contains the candidate commits and explanation in structured data.
