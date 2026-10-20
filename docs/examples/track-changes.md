# Track changes: a real report

`track-changes` shows how one analysis moved from what you approved. It reads the gate's and `verify`'s records, writes a short brief and an HTML report, and changes nothing.

[Open the example report](https://mdmanurung.github.io/mycelium-extra/track-changes-report.html) to see it. It is the real output on a synthetic analysis: invented names, no data. It is a single offline file, so you can also open it from disk.

The report lists what needs your attention first, such as a changed plan choice, a script edited since approval, or work in another analysis while this one was in focus. It then lists what was authorised and what it could not see. You review the diffs, then type `freeze <hash>` or ask `grill` to amend the plan.

New to this? See the [`track-changes` reference](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/track-changes.md) for the options and what it compares.

To regenerate the file, run `python3 tests/e2e/make_track_changes_example.py`.
