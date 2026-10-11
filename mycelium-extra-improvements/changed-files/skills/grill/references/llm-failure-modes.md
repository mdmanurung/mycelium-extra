# LLM failure modes

A coverage list of the ways an agent goes wrong while planning, coding, analysing, and reporting, as a companion to [analysis-decisions.md](analysis-decisions.md). That file lists the design decisions a plan must settle; this one lists the mistakes an agent makes while carrying a settled design out. Walk both for any bioinformatics or statistical analysis.

For each mode that applies, the plan names a guard: a validation step, a read-only probe, or a check, with its source (`repo: <path>`, `user`, or `default: <reason>`). Put the guard in the plan row it protects or, when it protects the whole plan, in Assumptions and risk. Skip modes that do not apply. A mode marked `cross-ref:` is satisfied by that analysis-decisions entry; cite it, do not duplicate it. The list sets coverage, not reading depth, and is not a question list: ask only under the gate in `SKILL.md`.

In the last column, a named tool (`data-contract-check`, `verify`, or the approval gate) is a check that exists today and catches the mode as described. `partial: <tool> (<what it covers>)` means the tool checks only the part in brackets; the plan's guard must cover the rest, and the plan must not cite the tool for more. `planned: <ID>` names a roadmap task in `docs/roadmap/` that would automate the guard; until it ships, the guard is a manual step, and the plan must not claim the check runs. `none` means no tool checks it.

## Planning and premise

| Failure mode | How it shows up | Guard the plan must name | Check |
| --- | --- | --- | --- |
| Estimand drift | The plan answers a nearby question: a different contrast, population, or outcome from the one the user asked | The Objective restates the user's question in their terms; each step's output feeds that estimand | cross-ref: Estimand and claim type |
| Reversed contrast | "Treated vs control" fitted with control as the numerator, or the factor's reference level is not the stated baseline | Name the reference level and the sign of a positive effect; a probe reads the factor levels | partial: data-contract-check (both levels exist, not which is the reference) |
| Stale evidence as current | A file's existence, or an old finding, is cited as if its outputs were current | Each cited output carries its date or commit, and a step re-checks it or marks it unverified | partial: verify (outputs older than the approval, and `stale` for verified plans) |
| Silent scope growth | Extra subgroups, cell types, or sensitivity runs appear that nobody asked for | Every step traces to the objective; extras go to Parked with a return condition | partial: approval gate (runs of unplanned scripts in gated paths, not extra work inside a planned script) |
| Redoing settled work | The repository already holds a finding that answers the task, and the plan re-runs it without saying so | Cite the finding first; make reuse versus re-run an explicit plan row | none |

## Data handling

| Failure mode | How it shows up | Guard the plan must name | Check |
| --- | --- | --- | --- |
| Invented columns or levels | Code uses a column name or factor level taken from the user's prose or from memory, not from the file | A header probe or data contract confirms every column and level the code uses | data-contract-check |
| Silent row loss | NA handling, `dropna`, `complete.cases`, or an inner join removes samples without a count | Log row counts before and after every filter and join; name the expected n | partial: data-contract-check (input row counts after the contract's filters, not losses inside the code) |
| Join duplication | A many-to-many join multiplies rows; a cell or sample appears twice | Assert key uniqueness on both sides and the row count after the join | partial: data-contract-check (repeated units in the sample table, not joins in the code) |
| Identifier mismatch | Sample IDs differ between tables in case, prefixes, or separators, so a join matches a subset | Report the overlap (matched, left-only, right-only) before joining | none |
| Gene symbol corruption | Spreadsheet-converted symbols (SEPT2 to a date, MARCH1), outdated aliases, or symbol versus Ensembl mixing | Map through a versioned annotation; report unmapped and duplicated symbols | cross-ref: Reference and identifiers |
| Coordinate base | BED (0-based, half-open) mixed with VCF or GTF (1-based, closed), giving off-by-one intervals | Name each file's coordinate convention and the conversion step | none |
| Chromosome naming and build | `chr1` versus `1`, or a GRCh37 file joined to GRCh38 annotation, so lookups silently miss | A probe of the contig names and the build in each header | cross-ref: Reference and identifiers |
| Strand assumptions | Library strandedness or feature strand assumed rather than read, halving or inverting counts | Read strandedness from the protocol or infer it (for example a strandedness check); record it | none |
| Sample label swap | Metadata row order assumed to match the matrix's column order | Join by explicit ID, never by position; assert the IDs are identical | none |
| Silent type coercion | IDs read as numbers (lost leading zeros), dates parsed as strings, factors as integers | Name the column types on read; a probe checks a few known IDs round-trip unchanged | none |

## Code and tools

| Failure mode | How it shows up | Guard the plan must name | Check |
| --- | --- | --- | --- |
| Invented API or flags | A function, argument, or CLI option that does not exist in the installed version | Record each tool's resolved path and version; check unfamiliar calls against its help or docs | none |
| Version-specific behaviour | A default or return format that changed between versions (for example a renamed argument or new default normalisation) | Pin the version in a lockfile or record it in the run plan | cross-ref: Normalization and transformation |
| Unstated defaults | The result depends on a default parameter nobody chose (resolution, number of neighbours, filtering thresholds) | Write consequential parameters out explicitly, each with a source | partial: verify (an advisory note on a `default:` source with no reason or only an empty phrase such as `standard`, not parameters left out of the plan) |
| Non-determinism | No seed, or parallel code whose result varies run to run | Set and record seeds; name which steps cannot be made deterministic | none |
| Wrong layer or assay | Tests run on scaled or log values when counts were needed, or the reverse | Name the layer at each downstream call | cross-ref: Input and matrix state |
| Memory blow-up | A sparse matrix densified, or a whole object copied, crashing or truncating a job | Estimate object size; keep sparse operations sparse; name the machine size | none |
| Swallowed errors | `try`/`except: pass`, `tryCatch` returning NULL, or a trailing `\|\| true` hides a failing step | No blanket error suppression; failures stop the run | partial: verify (an output file named on the plan's Outputs line that was never written) |

## Statistics and inference

| Failure mode | How it shows up | Guard the plan must name | Check |
| --- | --- | --- | --- |
| Retry until significant | Parameters, subsets, or methods changed across runs until a result appears; explore runs shopped for the best one | Pre-specify the primary analysis; count every contrast tried, including explore runs | cross-ref: Multiplicity; planned: D4 |
| Test chosen after results | The test or model changes after the first look at the data | The test is fixed in the approved plan; a change needs a new plan | cross-ref: Model or test |
| p versus padj confusion | Raw p-values reported or thresholded as if adjusted, or the reverse | Name which column each threshold uses | cross-ref: Multiplicity |
| Log base and sign confusion | log2 versus ln versus log10 mixed; fold-change direction flipped between table and text | Name the log base and the sign convention once; reports use it throughout | planned: D1 |
| Absence of evidence as evidence of absence | A non-significant result reported as "no effect" | Report effect size and interval; underpowered nulls are called inconclusive | none |
| Missing effect sizes | Only p-values reported, with no magnitude or uncertainty | Every reported test carries an effect size and its interval | none |
| Causal wording for associations | "Drives", "causes", "protects" for observational contrasts | Claim type matches the estimand; causal wording only with a causal design | cross-ref: Estimand and claim type |

## Claims and reporting

| Failure mode | How it shows up | Guard the plan must name | Check |
| --- | --- | --- | --- |
| Number transcription | A value in the report text differs from the artifact it came from | Report values are read from output files, not retyped; a check compares them | planned: D1 |
| Invented citations | A DOI, PMID, or reference that does not exist or does not support the claim | Every citation resolves, and the cited source is read before it is used | planned: D2 |
| Figure and text disagree | The text describes a trend, n, or direction the figure does not show | Figures and text come from the same output file; n is in the figure | cross-ref: Outputs and reporting |
| Explore results reported | A value from an explore run appears in a reportable document | Reportable numbers come only from runs under an approved plan | partial: verify (explore runs and the outputs they wrote, not report text); planned: D1 |
| Missing n or units | A figure or table without its sample size, units, or the unit of replication | Each figure and table states n, units, and what one point is | cross-ref: Outputs and reporting |
