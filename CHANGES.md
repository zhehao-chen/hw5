# CHANGES.md

Three lines per assignment: what it added, what it removed, what it constrained.
Removals are logged like additions.

## Assignment 1
- **Added:** a bounded tool loop; four ways to triage an issue (a direct call, a workflow, an agent, and a hybrid of the two); a grounded success check that reads the tracker; a results script
- **Removed:** nothing
- **Constrained:** every agent run to three bounds checked in code (steps, tokens, wall clock); success to what the tracker holds for the run's ID

## Assignment 2
- **Added:** a plan written as data before the issue is read; a validator with four checks; an executor that runs only the plan's steps; one checkpoint that may revise the plan; a second pass before the comment; detectors and a diff over traces; a progress file and a compaction
- **Removed:** the model's choice of the next tool, in the planned way
- **Constrained:** every tool call to a step of a validated plan; revisions to steps not yet done; the comment to drafts that pass the second pass

## Assignment 3
- **Added:** five rewritten tool definitions with examples, among them open_pr; a boundary check before every call; errors that name the fix; harness-derived idempotency keys, a check before every write attempt and a read-back after a timeout; the call record; a fail-closed hook
- **Removed:** free-text tool descriptions and free-form filters; protocol detail in anything the model sees
- **Constrained:** every write to be safe to retry, and to a person when its outcome cannot be read back; the comment to the last write, after the PR

## Assignment 4
- **Added:** a checkpoint after each file read and before each write, saved sync; a resume from the last checkpoint that replays a write with its saved arguments and key; a memory store of dated records with their source and origin, read before the first search; a write policy with one record per issue, superseded when it disagrees
- **Removed:** the conversation from every checkpoint; the issue's own text from what memory shows a prompt
- **Constrained:** a crashed run to resume, never restart; what is remembered to what a person stated or RepoMind derived, each with its source


## Assignment 5
- **Added:** an autonomy policy in three columns, placed by action class (`policy/autonomy.yaml`), enforced by a pre-call hook outside the model (`policy/hook.py`); boundaries from the inbox promoted to rules the hook reads (`policy/rules.jsonl`); a replay of a recorded day through the hook's own code (`bin/replay_policy`, with `--batched`); an approval screen of dry runs and harness facts (`policy/screen.py`) and a decisions log; escalation on four named signals with a packet, a checkpoint, a hold and a cap of three a day; a live notification before every run's first write; a stop the hook enforces, with a checkpoint and a resume that lifts it (`bin/stop`); rollback through the remote's compensations, newest first (`bin/rollback`); the disclosure line on every comment, added in code and required by the hook
- **Removed:** autonomous merge (`merge_pr` is prohibited in every reviewer mode); the allow-all hook; any write a gated call makes without an answer (no answer holds the run); any call whose arguments still hold the plan's `$fill` template
- **Constrained:** `post_comment` by circumstance (alone on an issue RepoMind opened, with approval on a person's thread, active or quiet); `push_commit` by branch (with approval only to RepoMind's own PR branch, prohibited to `main` or anyone else's); `open_pr` to `develop`, with approval; `close_issue` to issues RepoMind opened; every comment to carry the disclosure line
