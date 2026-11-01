# repo-setup

Sets up a new repository by running existing generators in order: Mycelium's init and the approval gate for an analysis repository, or [`ericmjl/cookiecutter-python-project`](https://github.com/ericmjl/cookiecutter-python-project) for a Python package; then lucid-coder's style configs and its `lucid-coder.yaml` environment pointer.

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

`/mycelium-extra:repo-setup [analysis|package] [analysis name]` (Codex: `$mycelium-extra:repo-setup`). No script and no flags.

## What it does

1. Asks once whether the repository is an analysis repository or a Python package, unless your message says.
2. Analysis repository: `git init` when needed, `/mycelium:core init`, then `/mycelium-extra:init`. Python package: `cookiecutter gh:ericmjl/cookiecutter-python-project`, after saying that it needs network, `cookiecutter` and `gh`, and that its post-generation hook runs `git init`, installs the pixi environment and pre-commit hooks, and commits.
3. Runs `/lucid-coder:align` when lucid-coder is installed, which writes `lucid-coder.yaml`: the environment manager, its name, and the `Rscript` and `python` paths. [new-analysis](new-analysis.md) and [grill](grill.md) read it.
4. Optionally writes `step_format` to `.mycelium-extra/gate.json` and scaffolds a first analysis with `new-analysis`.
5. Reports what each step wrote and the next commands.

## Reads and writes

Writes nothing itself except an optional `step_format` edit to `.mycelium-extra/gate.json`. Every other file comes from the generator it runs: Mycelium's init (`.living/`, `MYCELIUM.md`, `CLAUDE.md`, `AGENTS.md`), the cookiecutter, lucid-coder's align, `init` and `new-analysis`.

## Default on or off

On when invoked.

## Enforced versus the agent's instruction

Nothing here is enforced. Showing each command and waiting for a yes is the agent's instruction. The cookiecutter's post-generation hook makes a git commit; the skill says so before it runs.

## Related

[init](init.md), [new-analysis](new-analysis.md), lucid-coder's `align`.
