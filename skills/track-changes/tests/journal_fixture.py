"""One evolving synthetic history, using current gate hooks and verification results.
No scheduler or analysis process is launched by this fixture.
"""
from test_track_changes import FIT, plan


def history(case, count=47):
    first = case.approve(plan("500 cells", outputs="none"))
    case.hook("prompt", {"prompt": "focus analysis/a plan " + first})
    case.run_cmd("python " + FIT, code=1)
    case.run_cmd("python " + FIT)
    case.write(FIT, "min_cells = 200\n")
    case.run_cmd("python " + FIT)  # real repin
    case.approve(plan("500 cells", outputs="none"))  # same hash, changed script freeze
    second = case.approve(plan("200 cells", outputs="none"))
    case.hook("prompt", {"prompt": "focus analysis/a"}, session="s2")
    original_hook = case.hook
    case.hook = lambda event, payload, session="s2": original_hook(event, payload, session=session)
    case.approve(plan("200 cells", outputs="none"))  # approval is session-scoped
    for i in range(count):
        case.run_cmd("python " + FIT)
    third = case.approve(plan("100 cells", "sbatch `analysis/a/job.sh`", outputs="none"))
    case.write("analysis/a/job.sh", "#!/bin/sh\ntrue\n")
    case.run_cmd("sbatch analysis/a/job.sh")
    case.write("notes/interpretation.md", "# Researcher's note\nUnresolved synthetic interpretation.\n")
    case.hook = original_hook
    return first, second, third
