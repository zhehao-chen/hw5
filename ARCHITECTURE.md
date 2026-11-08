# ARCHITECTURE.md · RepoMind on the seven layers

For each layer: what does this job, and where is it enforced. Cite code as a file
path and line number joined by a colon, inside backticks; a checker opens every
reference (`checks/FORMATS.md`, section 8). A layer held only by a sentence in a
prompt (any file under `prompts/`) is **EMPTY**, and so is a layer nothing does
yet. Status is one of: present, partial (say what is missing), or **EMPTY**. Each
assignment brings this file up to date.

What each layer is for (Lecture 1, slides 42 to 44):

- **Model**: reasoning, choosing tools, generating text.
- **Harness**: runs the loop, builds each prompt, trims old history.
- **Tools**: where the system acts on the world.
- **Memory & State**: what survives a step, a session, a restart.
- **Control & Policy**: what the system may do, and when it must ask.
- **Observability**: a step-by-step record of what it did.
- **Evaluation**: measuring quality, before and after release.

The table below is RepoMind during Assignment 5.

| Layer | What does this job | Where it is enforced | Status |
|---|---|---|---|
| Model | The configured model, called only through the metered client | `harness/client.py:150` | present |
| Harness | The loop, with three bounds checked in code; a plan validated before it runs, and an executor that runs only the plan's steps | `agent/loop.py:38`, `ways/planned.py:309`, `ways/planned.py:404` | present |
| Tools | Ten namespaced tools behind one registry: every call checked at the boundary before it runs; every write keyed by the harness, checked before each attempt and read back after a timeout; every attempt in the call record | `tools/__init__.py:168`, `tools/__init__.py:258`, `tools/__init__.py:267`, `tools/__init__.py:284`, `tools/__init__.py:323` | present |
| Memory & State | A checkpoint after each file read and before each write, sync, and a resume from the last one; a store of dated records with their origin, read before the first search and written once at the end of a run | `ways/planned.py:366`, `ways/planned.py:379`, `ways/planned.py:245`, `ways/planned.py:265`, `state/checkpointer.py:55`, `state/store.py:96` | present |
| Control & Policy | An autonomy policy in three columns (`policy/autonomy.yaml`), enforced by a pre-call hook the model never sees: the registry runs it before every call and denies when it raises. In order it refuses a stopped run's calls (`bin/stop`), places each call in an action class from the harness's facts and refuses the prohibited column in every reviewer mode, refuses a call that crosses a user's boundary (parsed from the inbox, in the harness, into `policy/rules.jsonl` before every model call), refuses a comment without the disclosure line, and asks the reviewer for the requires-approval column, where no answer refuses the call and holds the run. The way escalates on four named signals before an action it cannot undo (packet in `escalations/`, checkpoint, hold, a cap of three a day), sends a live notification before its first write, ends stopped after a checkpoint and lifts the stop on resume; `bin/rollback` offsets a run's writes newest first; `bin/replay_policy` places a recorded day with the hook's own code | `tools/__init__.py:145`, `tools/__init__.py:234`, `policy/hook.py:132`, `policy/hook.py:141`, `policy/hook.py:146`, `policy/hook.py:65`, `policy/hook.py:90`, `policy/hook.py:153`, `policy/hook.py:157`, `policy/hook.py:164`, `policy/hook.py:175`, `policy/rules.py:70`, `policy/inbox.py:33`, `ways/planned.py:190`, `ways/planned.py:795`, `ways/planned.py:188`, `ways/planned.py:186`, `ways/planned.py:466`, `ways/planned.py:500`, `ways/planned.py:524`, `ways/planned.py:573`, `ways/planned.py:506`, `policy/escalation.py:71`, `policy/escalation.py:88`, `policy/stop.py:60`, `bin/stop:51`, `bin/rollback:28`, `ways/planned.py:792` | present |
| Observability | One trace line per model call and per tool call, and the plan as data before it runs; Assignment 5 adds a live notification per run (and on a hold, a stop or an escalation) to `logs/notifications.jsonl`, and logs of every refusal (`logs/hook.jsonl`), every reviewer decision (`logs/approvals.jsonl`), every stop (`logs/stops.jsonl`) and every escalation (`logs/escalations.jsonl`) | `agent/loop.py:50`, `ways/planned.py:203`, `policy/hook.py:106` | partial: the notification sink is a file, not a pager or a channel |
| Evaluation | The grounded check reads the tracker, never the agent | `eval/check_triage.py:7` | partial: offline only |

**Empty layers: 0 of 7**, and two are partial.
