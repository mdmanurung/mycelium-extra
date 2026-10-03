# Biomni biomedical review

The Phylo Biomni MCP has no lookup-only tool. A review is a Biomni agent task (`start_new_task`), which runs in Biomni's own cloud sandbox, may run code, search, or launch sub-jobs there, and spends the user's Biomni credits. "Read-only" here means nothing touches this repository, `.living/`, the gate, or provenance, and Biomni's output stays advisory.

Before each run, show the user the redacted packet, the Biomni project, that the run costs credits, and that the task and packet stay in their Phylo project until they delete it in the Biomni web app; start only after the user agrees. Then:

- Use an existing project the user names, or `create_project` a dedicated review project. Never reuse an analysis project.
- Call `start_new_task` with the packet and role below as `message`, `auto_mode` false, and no `file_ids`. Do not call `upload_file`: no data, tables, or result files leave the machine.
- Follow with `wait_for_next_update` at most about three times. If it is still running, report Biomni pending with its `biomni_url` and continue with the Codex critique; do not poll indefinitely.
- Do not use `request_review` as the reviewer: its output lands only in the Biomni web app, not in a tool result.
- Anything Biomni computes or writes to its result files is a lead, not a project result. Never copy it into the repository, cite it as a finding, or treat it as an executed plan step.

Role prompt (send with the packet):

> You are reviewing a proposed analysis plan before it runs; do not run the analysis or produce project results. Challenge biological plausibility, experimental design, unit of inference, confounding, covariates, missing controls, statistical-method fit, alternative mechanisms, sensitivity analyses, and interpretation limits. Cite PMID, DOI, or another retrievable primary source for material claims. Reply in the response format included in this message, with `reviewer: biomni`, and state unresolved uncertainty.

Verify sources before they drive a plan amendment. A model-generated citation is a lookup target, not proof. Do not send raw data, participant identifiers, secrets, or unpublished full tables.
