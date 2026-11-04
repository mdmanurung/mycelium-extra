# Cold-reader test

Check that a document works for someone who has only the document. It applies to `HANDOFF.md` and to a filled Quarto report (`.qmd`), nothing else. The user starts it (`handoff test`, or the one-line offer at the end of `handoff` and `analysis-report`). No skill runs it unasked.

The test is read-only. The reader reports gaps. The agent changes the document only after the user says so.

## 1. Stage a copy

The reader gets one folder and nothing else.

1. Make an empty folder in the scratchpad (else `mktemp -d`). Never use the project folder.
2. Copy the document into it.
3. Copy each file the document points to, at the same relative path. For `HANDOFF.md`, those are the `path:line` pointers under Read first, the Next action and the Pending plan file. For a `.qmd`, they are the PNGs and other files it cites.
4. A pointer to a file that does not exist is not copied. Write its name to `MISSING.txt` in the folder, one per line. The reader reports each as a missing file.
5. Do not copy anything the document does not point to. Do not copy the `.git` folder, `.mycelium-extra/` or `.living/`, unless the document names a file inside them.

Give the reader the staged path only, never the project path.

## 2. Reader prompt

Use this prompt word for word. Replace `<staged>` and `<document>`.

```text
You have only the folder <staged>. Read <document> and the files it points to in that folder. Do not read anywhere else and do not run anything.

List each step you could not do and each term you could not resolve. Give the line of the document for each. Do not guess and do not fill a gap from general knowledge. A file named in MISSING.txt is a missing file: report it.

Answer with a numbered list, one gap per item, as: <line> — <step or term> — <what is missing>. If you find none, answer exactly: no gaps
```

## 3. Run it

- Host with subagents: start a fresh subagent with the prompt and no other context. Do not pass it the conversation or the project path.
- Host without subagents: print the prompt and the staged path. Tell the user to paste both into a new session.

## 4. Report back

Show the user the reader's list unchanged. Say that fixes wait for their word. When they say so, fix the document, then offer the test again.

## Limit

The staged folder is an instruction, not a sandbox. A subagent or a new session can still read the whole repository if it chooses. The test shows what the document says on its own. It does not prove the reader stayed inside the folder.
