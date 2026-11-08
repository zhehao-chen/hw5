"""The inbox drain: a person's messages, read before every model call (Lecture 5, slide 17).

`Draining` wraps a run's model client. Before each create() it drains the inbox
(harness.inbox.drain). A boundary (`BOUNDARY: deny path=<glob>`) is parsed here, in the
harness, and written to policy/rules.jsonl, where the hook reads it before every tool
call. It never goes to the model, so no compaction can drop it. Any other message is
passed on to the model as the user's words, in this call and every later one.

Wrapping the client covers every model call the way makes, through ctx.client: the
planner's, a revision's, a fill's, a critique's and a compaction's.
"""

from __future__ import annotations

from harness.inbox import drain
from policy import rules

HEADING = "## Messages from the user who asked for this triage"


class Draining:
    def __init__(self, client, ctx):
        self._client = client
        self._ctx = ctx
        self.said: list[str] = []      # the user's other messages, shown in every later call

    def create(self, **request):
        self.absorb()
        if self.said:
            request = {**request, "messages": with_user_words(request.get("messages") or [], self.said)}
        return self._client.create(**request)

    def absorb(self) -> None:
        ctx = self._ctx
        for message in drain(ctx):
            glob = rules.parse(message["text"])
            if glob is not None:
                rules.add(ctx.run_id, glob, message["text"], stated_at=message.get("delivered_at"))
                ctx.trace.event("boundary", path=glob, message=message["text"], call=message.get("call"))
            else:
                self.said.append(message["text"])
                ctx.trace.event("user_message", text=message["text"], call=message.get("call"))

    def __getattr__(self, name):
        return getattr(self._client, name)


def with_user_words(messages: list[dict], said: list[str]) -> list[dict]:
    """The request's messages, with the user's words added to its last user turn."""
    block = HEADING + "\n" + "\n".join(f"- {s}" for s in said)
    out = [dict(m) for m in messages]
    for m in reversed(out):
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str):
            m["content"] = f"{content}\n\n{block}"
        elif isinstance(content, list):
            m["content"] = list(content) + [{"type": "text", "text": block}]
        return out
    return out + [{"role": "user", "content": block}]
