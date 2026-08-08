# Agents and Skills

The custom agent in [agents/bisect_reasoner.py](agents/bisect_reasoner.py) explains why a suspect commit likely caused a bug. It receives bisect results, the candidate commit, and the relevant diff, then produces a plain-language explanation with evidence, confidence, and limitations. It exists to make the pipeline explainable: after the bisect engine narrows candidates and the pattern matcher ranks them, the agent turns raw evidence into a human-readable finding.

[agents/bisect_reasoner_agent.md](agents/bisect_reasoner_agent.md) documents the expected behavior and constraints for that runtime agent.

The custom skill in [skills/git_churn_analysis.py](skills/git_churn_analysis.py) provides extra context for that explanation. It inspects a file’s recent git history and returns lightweight churn metrics such as commit count, unique authors, and revert count. The CLI loads it through `src/dtm/skill_bridge.py` and attaches the churn context to reported candidates.

Together, these components connect to the architecture in [ARCHITECTURE.md](ARCHITECTURE.md) at the reasoning stage: the bisect engine identifies candidates, the pattern matcher ranks them, and the reasoner agent uses both the commit diff and supporting context to explain the likely root cause.
