# RepoMind

The course's running system, built one layer at a time. RepoMind triages issues
for **Ledgerline**, a small reporting and export service: it reads an issue,
searches Ledgerline's private codebase, applies a label, opens a draft pull request
for the file it names, and posts a triage comment where the issue's author can read
it.

That combination is deliberate. RepoMind reads text anyone can write, reaches
code nobody outside the team should see, and writes somewhere public. Lecture 1
calls it the lethal trifecta. You build it this way on purpose, and Lecture 8 is
when you close it.

## Start here

You have two things: this repository, and the assignment handout from your
instructor. The handout says what to build and how it is graded; this file says
how the repository works. For Assignment 5, read the handout's "Getting started"
first.

This repository holds Assignment 4's working solution in place of your own code:
the planned way with its checkpoints, its resume and its store, and the ten tools
behind one registry. RepoMind now applies its label with `apply_label` as well as
writing it in the comment. Every write it makes, it makes unasked: the registry's
hook allows every call, and nothing decides which actions need a person. A fresh
copy runs, and `make check-05` awards it nothing. That is expected.

### What you need

- Python 3.10 or later, `git` and `make`. Python's built-in `sqlite3` is all the
  database this assignment needs.
- The model and API key you used before, or any model with tool calling. Never
  commit the key and never share it.

### Set up, and use your model

```bash
make setup                     # creates .venv and installs the three dependencies
source .venv/bin/activate      # in every new terminal
make test                      # the harness's own tests; they spend no tokens
```

From your earlier repository, copy the `provider`, `model`, `base_url` and
`api_key_env` lines of `settings.yaml` into this one, and your model's line in
`pricing.yaml`, if this sheet does not have it. Change nothing else in
`settings.yaml`. Two backends cover almost every vendor:

| Your model | In `settings.yaml` |
|---|---|
| Claude, through Anthropic's API | `provider: anthropic`, `model`; the key in `ANTHROPIC_API_KEY` |
| Anything with an OpenAI-compatible API: OpenAI, Google Gemini, Mistral, DeepSeek, Groq, OpenRouter, a local Ollama or vLLM server, and many more | `provider: openai-compatible`, `model`, `base_url` (none for OpenAI itself), and `api_key_env`, the variable that holds your key (default `OPENAI_API_KEY`) |

Then check it:

```bash
export OPENAI_API_KEY=...      # or the variable your api_key_env names
make ping                      # your key, your model, tool calling, its price line, and your tool definitions
```

`make test` and `make ping` must both pass before you write any code.

### Where to start: Assignment 5

| Order | What you write | How you test it | Costs |
|---|---|---|---|
| Part A | `policy/autonomy.yaml`, `policy/hook.py` and your registry's call to it; the inbox drain in your way and a boundary parser; `bin/replay_policy` | The scripted models, free; `bin/replay_policy fixtures/rollup_2026-08-04.jsonl` | Nothing |
| Part D | The disclosure line, and the hook's rule that a comment carries it. Build it with Part A, before any run of your model posts | The scripted models, free | Nothing |
| Part B | `policy/screen.py` and your decisions log; then you review a working day at `bin/review` | `REVIEWER=human python run.py --way planned --set day` | 40 runs, maybe 80 |
| Part C | Your escalation, the live notification, `bin/stop`, and `bin/rollback` | The three moments, free; ten stops and one rollback on your model | About 11 runs |

`make check-05` works at any point and shows what is still missing; it is the same
checker staff run.

## What is here, and what is yours

| Path | What it is | Yours to edit? |
|---|---|---|
| `ways/planned.py`, `agent/`, `prompts/`, `state/` | Assignment 4's working solution, with Assignment 5's task: the plan's label step before the PR, the label the comment's draft states, and steps for any of the ten tools | **Yes**: your inbox drain, your escalation, your live notification, your stop and hold, your disclosure line |
| `tools/` | The ten tools and their registry. New: `issues_label` (apply_label), `issues_close` (close_issue), `branches_push` (push_commit), `pulls_merge` (merge_pr) and `code_run_tests` (run_tests). The four new writes are keyed like the comment and the PR | The registry, `tools/__init__.py`, to add your hook to its `hooks`; **not** the five new tools |
| `policy/` | You create it: `autonomy.yaml`, `hook.py`, `screen.py`, and whatever else your policy needs. Your boundary rules go in `policy/rules.jsonl` | **Yes** |
| `bin/review` | The reviewer console: it shows each waiting request through your `policy/screen.py` and records your answer | No: its screen is yours, in `policy/screen.py` |
| `bin/replay_policy`, `bin/stop`, `bin/rollback` | You create them (`checks/FORMATS.md`, section 13.10) | **Yes** |
| `run.py` | Runs a way over issues. New: `--set day`, `--set day2` and `--set moments`, and `--resume` of a run that ended `held` or `stopped` | No |
| `harness/` | The model client, tracker, trace writer, runner, prices and scripted models. New for Assignment 5: the mock remote's labels, closes, pushes and merges, branch protection on `main`, its write log and its three compensating endpoints; issue metadata and each call's facts (`harness/facts.py`); the reviewer (`harness/reviewer.py`); the inbox (`harness/inbox.py`); the notification sink (`harness/notify.py`); one clock for every log (`harness/clock.py`); the `held` and `stopped` endings; the three moments and the boundary's test run (`harness/scripted.py`) | No |
| `fixtures/rollup_2026-08-04.jsonl` | One recorded day of RepoMind's traffic: 520 calls over 40 issues, each with its facts, recorded with no policy in force (Part A) | **Never** |
| `fixtures/issues/day/`, `fixtures/issues/day2/` | Two day queues of 40 issues each, with their metadata (Part B) | **Never** |
| `fixtures/issues/moments/`, `fixtures/test_results.yaml` | The three moments' issues, and the test suite's recorded result on each branch (Part C) | **Never** |
| `fixtures/` | Everything else: Ledgerline's codebase, the issues and answers, the search index, the memory candidates | **Never** |
| `checks/` | `check_05.py`, the Assignment 5 checker, and `FORMATS.md`, which defines every format it reads (section 13 is new) | No |
| `tests/` | The harness's own tests | No |
| `settings.yaml`, `pricing.yaml` | Your model, the ceilings, the dated price sheet | Once, in setup: your model and its price line; never the ceilings |
| `eval/` | The grounded check, and the earlier assignments' scripts; any script of yours | **Yes** |
| `reports/`, `ARCHITECTURE.md`, `CHANGES.md` | Your write-ups; `reports/` starts with the templates for `LAB_05.md` and `LAB_05.json` | **Yes** |
| `runs/`, `tracker/`, `state/*.db`, `logs/`, `escalations/` | Made as you run: traces, call records, the ledger, the inbox, the tracker's database and its archives, your checkpoints and store, the logs and the packets | Written by the harness and your code; **commit them** |

## Running

```bash
python run.py --way planned --issues 4192                                  # one run
REVIEWER=human python run.py --way planned --set day                       # Part B: you review, at bin/review
make review                                                                # bin/review, in a second terminal
REVIEWER=scripted:approve-all python run.py --way planned --set dev --runs 5 --jobs 1   # Part C: ten runs to stop
python run.py --resume <run_id>                                            # a held or stopped run, again
python -m harness.inbox send --issue 4303 "BOUNDARY: deny path=src/db/**"  # a user's message, to the next run on 4303
make check-05                                                              # the Assignment 5 checker
```

**The three moments** are scripted runs, free, each on its own issue (`checks/FORMATS.md`, section 13.8):

```bash
REVIEWER=scripted:replay:fixtures/reviewers/moment_a.jsonl \
  python run.py --way planned --issues 4501 --backend harness.scripted:MomentA   # its tests fail, then it would push
REVIEWER=scripted:none python run.py --way planned --issues 4501 --backend harness.scripted:MomentA   # nobody answers: it holds
REVIEWER=scripted:approve-all python run.py --way planned --issues 4502 --backend harness.scripted:MomentB   # every search finds nothing
REVIEWER=scripted:approve-all python run.py --way planned --issues 4503 --backend harness.scripted:MomentC   # it is not sure of its label
REVIEWER=scripted:approve-all REPOMIND_COMPACT_AT=300 \
  python run.py --way planned --issues 4303 --backend harness.scripted:BoundaryProbe   # its third read is src/db/client.ts
REVIEWER=scripted:approve-all python run.py --way planned --issues 4192 --backend harness.scripted:ProhibitedProbe # it merges and pushes to main
REVIEWER=scripted:approve-all python run.py --way planned --issues 4192 --backend harness.scripted:SlowTriage      # a second a call: stop it
```

Moment A's reviewer file, `fixtures/reviewers/moment_a.jsonl`, approves every gated
call and denies the escalation, so that the PR opens and its tests fail before the
push: the checker runs it the same way. Send BoundaryProbe's boundary first, with
`python -m harness.inbox send --issue 4303 --before-call 2 "BOUNDARY: deny path=src/db/**"`.

**The reviewer.** `REVIEWER` says who answers when your policy asks:
`scripted:approve-all`, `scripted:deny-all`, `scripted:none` (nobody answers; the
default when it is unset), `scripted:replay:FILE` (the decisions in a file, such as
your own `logs/approvals.jsonl`), or `human`: you, at `bin/review`. Bulk runs never
wait for a person. Every run records its reviewer in its `run_start` line.

## How your code calls the harness

Two contexts appear below. In your hook, `self.ctx` is the registry's `RunContext`
(`run_id`, `tracker`, `issue`, `calls`). In your way, `ctx` is the run's
`WayContext` (`run_id`, `issue_number`, `client`, `trace`, `tracker`, `tools`).

```python
from harness.roles import action_of, arg      # a tool's action, by Lecture 5's name: action_of("issues_comment") == "post_comment"

# In your hook: the call's facts, which the harness computed and the model never sees (13.2)
rc = self.ctx                                 # the registry's RunContext
facts = rc.tracker.facts(rc.run_id, action, args, rc.issue)
facts["issue_opened_by_agent"], facts["minutes_since_human_comment"], facts["branch_protected"], facts["paths"]

# A gated call, or an escalation: ask the reviewer, and wait (13.4)
from harness.reviewer import Reviewer
answer = Reviewer.from_env().ask({"run_id": rc.run_id, "action": action, "action_class": klass,
                                  "args": args, "facts": facts}, timeout_s=1800,
                                 until=lambda: False)   # return True to withdraw early, such as on a stop
answer is None            # no answer before the timeout (or withdrawn): never a yes
answer["decision"], answer["seconds"], answer["reviewer"], answer["mode"]

# In your way, before every model call: the user's messages (13.3); ctx is the WayContext
from harness.inbox import drain
for message in drain(ctx):
    message["text"]       # "BOUNDARY: deny path=src/db/**" (harness.formats.BOUNDARY), or anything else

# The notification sink (13.5), and one clock for every log
from harness.notify import notify
from harness.clock import now
notify("live", ctx.run_id, f"RepoMind is running on issue {ctx.issue_number}")

# The remote, for bin/rollback (13.6): a run's writes, oldest first, and the three compensations
from harness.tracker import Tracker
remote = Tracker()
remote.log(run_id)                              # every write the remote received, with its outcome and time
remote.remove_label(run_id, label_id)           # and close_pr(run_id, pr_id), reopen_issue(run_id, close_id)
```

Your hook is a function `hook(name, args)` that returns `None` to allow a call and
a reason to refuse it; add it to `self.hooks` in `tools/__init__.py`'s registry,
which has the run's context as `self.ctx`. A hook that raises denies the call. It
is not told the plan step; count anything per step, such as a step blocked three
times, in your way. Your way ends a run with `ctx.trace.end("held", ...)` or
`ctx.trace.end("stopped", ...)`, and `python run.py --resume <run_id>` reopens it.
Run `bin/review` and your own `bin/` scripts with the virtual environment active. The formats your code writes (the
policy file, the rule file, the hook log, the decisions log, the stops log, the
escalation packet and `reports/LAB_05.json`) are in `checks/FORMATS.md`, section 13.

## The rules the harness enforces

- **Success is read from the environment, never from the agent.** The checker
  reads the remote's write log, the logs, the traces and the checkpoints, never what
  the model says it did.
- **Every read of the tracker is scoped to one run**, and every write is stamped
  with it.
- **Branch protection on `main` is the remote's**, a repository setting, not your
  policy: a push to `main` reaches the remote and is rejected there.
- **There is no way to delete a comment or undo a push or a merge.**
- **Every run has a hard ceiling** (`session_token_ceiling`), and **every
  assignment has one** (`lab_token_ceiling`). The runner stops starting runs at the
  second. Ask before you pass `--over-budget`.
- **Prompts live in `prompts/`**, and a layer held only by a prompt is empty: your
  policy is enforced in the hook, and the model never sees it.
- **Disclose AI assistance** in each report: which tool, what it wrote, what you
  checked.

## Submitting an assignment

Your copy of this repository is private. When you create it, add the course
staff's GitHub account as a collaborator (**Settings**, then **Collaborators**)
and post its URL on the assignment in Canvas: that is how staff find and read
your work.

Run `make check-05` first; it is the same checker staff run. Commit everything,
including `runs/`, `tracker/` with its archives, `logs/`, `escalations/` and your
checkpoint and store databases (the checker reads them all), then tag the commit
and push both the commit and the tag. A tag you have not pushed has not been
submitted.

```bash
make check-05
git add -A
git commit -m "Assignment 5"
git tag lab-05
git push
git push origin lab-05
```
