"""Short-lived, per-sender conversation context held only in server memory."""

import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field

MAX_TURNS = 8
MAX_FACTS = 6
MAX_SESSIONS = 256
USER_TEXT_LIMIT = 500
REPLY_LIMIT = 500
IDLE_SECONDS = max(60, int(os.environ.get("VERNIER_MEMORY_HOURS", "24")) * 3600)


@dataclass
class Session:
    turns: deque = field(default_factory=lambda: deque(maxlen=MAX_TURNS))
    facts: deque = field(default_factory=lambda: deque(maxlen=MAX_FACTS))
    last_used: float = field(default_factory=time.monotonic)


_sessions = {}
_lock = threading.RLock()


def _prune(current):
    for sender, session in list(_sessions.items()):
        if current - session.last_used > IDLE_SECONDS:
            del _sessions[sender]


def context_for(sender):
    if not sender:
        return {"summary": "", "turns": []}
    with _lock:
        current = time.monotonic()
        _prune(current)
        session = _sessions.get(sender)
        if not session:
            return {"summary": "", "turns": []}
        session.last_used = current
        return {"summary": "; ".join(session.facts),
                "turns": [{"user": turn[0], "assistant": turn[1]}
                          for turn in session.turns]}


def remember(sender, user_text, reply, *, fact=None):
    if not sender or not reply:
        return
    with _lock:
        current = time.monotonic()
        _prune(current)
        if sender not in _sessions and len(_sessions) >= MAX_SESSIONS:
            oldest = min(_sessions, key=lambda key: _sessions[key].last_used)
            del _sessions[oldest]
        session = _sessions.setdefault(sender, Session())
        session.last_used = current
        session.turns.append((user_text.strip()[:USER_TEXT_LIMIT],
                              reply.strip()[:REPLY_LIMIT]))
        if fact:
            fact = fact.strip()[:120]
            if fact and (not session.facts or session.facts[-1] != fact):
                session.facts.append(fact)


def forget(sender):
    if sender:
        with _lock:
            _sessions.pop(sender, None)
