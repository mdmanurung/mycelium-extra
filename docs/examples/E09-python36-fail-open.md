# E09. The hook ran under Python 3.6 and failed open: logged, visible, later fixed

Control point: **visibility**

Anonymised from a real project. Source: `gate-errors.jsonl` of project A (21 lines) and the CHANGELOG entries for `hooks/py.sh`. No receipt exists for any call in the failing windows.

## 1. Socratic: ask these first

- When the gate cannot check a call, does it block or allow? Which setting decides?
- Where would I see that it did not check?
- For this stretch of work, what record would verify have to rely on?

## 2. What the records show

21 gate errors in 2 sessions over 3 days: 20 were "needs Python 3.9 or later, but the hook ran Python 3.6" (tool 8, post 7, prompt 3, stop 2), 1 was a module-not-found. Every line carries `"decision": "allow"`. Shape of a line (ids replaced):

```text
{"host": null, "session_id": "<session>", "call_id": "<call>", "ts": <epoch>, "event": "tool",
 "error": "mycelium-extra needs Python 3.9 or later, but the hook ran /usr/bin/python3 3.6.8; install python3.9 or later, or set MYCELIUM_EXTRA_PYTHON",
 "decision": "allow"}
```

The cause: an older hook registration ran under the system `python3`. Fixed in the plugin by `hooks/py.sh`, which finds the newest Python 3.9+ on PATH and otherwise reports an old one through `on_error`. Default stays `allow`; `"on_error": "deny"` blocks every unchecked call.

## 3. Track-changes shape

Observed: 21 hook calls without a gate decision. Potential: gated scripts ran without a pin check. Gap: 0 receipts in those windows, so `verify` can show only that no run was recorded. Unknown: what ran.

## 4. Librarian block

None.

## 5. What the human decided

Set the interpreter for the hooks (the fix path named in the message) and kept the log. An honest note for readers: the default is fail-open, as documented; deny is opt-in.

## 6. Without the tool

The failure would have been silent: calls allowed, nothing recorded, no line saying the gate had not looked.

Basis: 21 gate errors (project A); project B had none.
