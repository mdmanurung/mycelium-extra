"""Independent contract probes; exit 1 means at least one contract was violated.

Run with Python 3.9+: python tests/adversarial_audit.py --output /tmp/audit.json
Only disposable temporary projects are mutated. This is an audit, not a golden
test suite: failures remain visible until the underlying behavior is repaired.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'hooks'), str(ROOT / 'skills/plan-review/scripts'),
                str(ROOT / 'skills/track-changes/scripts')]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def h5ad_cases():
    """Optional-reader trust boundary; a valid categorical control checks the fixture."""
    import h5py
    import numpy as np
    records = []
    script = ROOT / 'skills/data-contract-check/scripts/data_contract_check.py'
    with tempfile.TemporaryDirectory(prefix='mx-adversarial-h5ad-') as tmp:
        root = Path(tmp)
        for label, codes in [('valid', [0]), ('float', [0.5]), ('string', ['x'])]:
            path = root / (label + '.h5ad')
            with h5py.File(path, 'w') as handle:
                obs = handle.create_group('obs')
                obs.attrs['encoding-type'] = 'dataframe'
                obs.attrs['_index'] = '_index'
                obs.attrs['column-order'] = np.array(['group'], dtype=h5py.string_dtype())
                obs.create_dataset('_index', data=np.array(['S1'], dtype=h5py.string_dtype()))
                group = obs.create_group('group')
                group.attrs['encoding-type'] = 'categorical'
                group.create_dataset('codes', data=np.array(codes, dtype=h5py.string_dtype() if label == 'string' else None))
                group.create_dataset('categories', data=np.array(['A', 'B'], dtype=h5py.string_dtype()))
            contract = root / 'contract.json'
            contract.write_text(json.dumps({'schema': 'mycelium-extra.data_contract.v1', 'table': path.name,
                                           'checks': [{'kind': 'cohort', 'column': 'group', 'levels': ['A']}]}))
            result = subprocess.run([sys.executable, str(script), '--contract', str(contract), '--root', str(root), '--json'],
                                    capture_output=True, text=True, timeout=15)
            expected = 0 if label == 'valid' else 3
            records.append({'case': label + ' categorical codes', 'area': 'data-contract-check',
                            'expected': 'exit {} without traceback'.format(expected),
                            'holds': result.returncode == expected and 'Traceback' not in result.stderr,
                            'actual': {'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}})
    return records


def run():
    import gate
    import stateio
    import evidence
    import provenance
    import focus
    import validation
    import journal
    import render
    import review_packet as packet
    import presend_check as presend
    contract = module('audit_contract', 'skills/data-contract-check/scripts/data_contract_check.py')
    decisions = module('audit_decisions', 'skills/decision-status/scripts/decision_threads.py')
    scaffold = module('audit_scaffold', 'skills/new-analysis/scripts/new_analysis.py')
    fidelity = module('audit_fidelity', 'skills/verify/scripts/method_fidelity.py')
    verify = gate.load_verify()
    capture = module('audit_capture', 'skills/idea/scripts/capture.py')
    confirm = module('audit_confirm', 'hooks/confirm_write.py')
    tc = module('audit_tc', 'skills/track-changes/scripts/track_changes.py')
    defaults = module('audit_defaults', 'skills/plan-review/scripts/default_reasons.py')
    records = []

    def check(name, area, expected, action, predicate):
        try:
            actual = action()
            holds = bool(predicate(actual))
        except Exception as error:
            actual = {'exception': type(error).__name__, 'message': str(error)[:500]}
            holds = False
        records.append(dict(case=name, area=area, holds=holds, expected=expected, actual=actual))

    def refuses(action, exception=ValueError):
        try:
            action()
        except exception:
            return True
        return False

    with tempfile.TemporaryDirectory(prefix='mx-adversarial-') as tmp:
        root = Path(tmp) / 'project'
        root.mkdir()
        state = root / '.mycelium-extra'
        state.mkdir()
        (state / 'gate.json').write_text('{"on_error":"deny"}')
        (root / 'analysis').mkdir()
        (root / 'analysis/x.py').write_text('print(1)\n')
        outside = Path(tmp) / 'outside'
        outside.mkdir()

        for value in [None, True, -1, float('nan'), float('inf'), '2', [], {}, 10**1000]:
            check('numeric setting rejects ' + repr(value)[:35], 'gate', 'False',
                  lambda v=value: gate._number(v), lambda v: v is False)
        for value in [0, 1, 0.01]:
            check('numeric setting accepts ' + str(value), 'gate', 'True',
                  lambda v=value: gate._number(v), lambda v: v is True)
        config = gate.load_config(str(root))
        commands = [
            ('plain Python', 'python analysis/x.py'),
            ('relative cd', 'cd analysis && python x.py'),
            ('shell wrapper', "bash -c 'python analysis/x.py'"),
            ('env wrapper', 'env A=1 python analysis/x.py'),
            ('timeout wrapper', 'timeout 2s python analysis/x.py'),
            ('command builtin', 'command python analysis/x.py'),
            ('exec builtin', 'exec python analysis/x.py'),
            ('substitution', 'echo "$(python analysis/x.py)"'),
            ('ANSI escaped path', "python $'analys\\151s/x.py'"),
            ('variable script', 'p=analysis/x.py; python "$p"'),
            ('process substitution', 'cat <(python analysis/x.py)'),
            ('absolute env cwd', 'env -C "' + str(root / 'analysis') + '" python x.py'),
        ]
        commands += [(wrapper + ' wrapper', wrapper + ' python analysis/x.py') for wrapper in
                     ['nice -n 5', 'ionice -c 3', 'stdbuf -oL', 'nohup', 'setsid', 'command -p']]
        commands += [('path character escape ' + escaped, 'python ' + escaped) for escaped in
                     ['anal""ysis/x.py', 'analysis\\/x.py', "$'\\x61nalysis/x.py'", "$'analysis/\\170.py'"]]
        for label, command in commands:
            event = dict(cwd=str(root), session_id='audit', tool_name='Bash', tool_input={'command': command})
            def invoke(e=event):
                result = subprocess.run([sys.executable, str(ROOT/'hooks/gate_run.py'), 'tool'],
                                        input=json.dumps(e), text=True, capture_output=True, timeout=15)
                return json.loads(result.stdout) if result.stdout.strip() else {}
            check('unapproved ' + label, 'gate', 'permissionDecision=deny', invoke,
                  lambda v: v.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny')
        for label, command in [('plain echo', 'echo hello'), ('quoted command as data', "echo 'python analysis/x.py'"),
                               ('read state', 'cat .mycelium-extra/gate.json')]:
            check('benign ' + label, 'gate', 'no permission denial',
                  lambda c=command: list(gate.analyse_command(c, str(root), str(root), config)),
                  lambda v: not v)

        for rel in ['../escape', '/absolute', 'C:\\private', 'a/../b', 'x\x00y', 'x\ny']:
            check('portable path rejects ' + repr(rel), 'evidence', 'False',
                  lambda r=rel: evidence.relative(r), lambda v: v is False)
        for rel in ['analysis/a', 'a b/c.md', 'a/é.md']:
            check('portable path accepts ' + rel, 'evidence', 'True',
                  lambda r=rel: evidence.relative(r), lambda v: v is True)
        check('stable semantic digest ignores clock', 'evidence', 'equal identities',
              lambda: evidence.identity({'x': 1, 'generated_at': 'a'}) == evidence.identity({'x': 1, 'generated_at': 'b'}), bool)
        for secret in ['synthetic-sensitive', 'Bearer synthetic-sensitive', 'https://user:synthetic-sensitive@example.invalid']:
            value = {'hash': '12345678', 'status': 'CONFORMS', 'receipts': [{'command_env': {'KEY': 'synthetic-sensitive'}}],
                     'findings': [['gap', secret]], 'outputs': [{'path': 'analysis/synthetic-sensitive.tsv'}]}
            check('projection withholds environment value ' + secret[:15], 'evidence', 'no environment value anywhere',
                  lambda v=value: 'synthetic-sensitive' not in json.dumps(evidence.project(v)), bool)
        for line in ['password=synthetic-sensitive', 'Bearer synthetic-sensitive',
                     'https://user:synthetic-sensitive@example.invalid']:
            check('track-changes redacts ' + line.split(':')[0], 'track-changes', 'secret removed',
                  lambda s=line: 'synthetic-sensitive' not in tc.Redactor()(s), bool)

        (state/'linked').symlink_to(outside, target_is_directory=True)
        check('atomic refuses linked state parent', 'stateio', 'ValueError',
              lambda: refuses(lambda: stateio.atomic(str(state/'linked/new/file.json'), 'x')), bool)
        check('atomic refusal creates no external directories', 'stateio', 'outside/new absent',
              lambda: not (outside/'new').exists(), bool)
        (state/'write-pending').symlink_to(outside, target_is_directory=True)
        check('confirm-write refuses linked pending directory', 'confirm-write', 'refusal, no pending file outside root',
              lambda: refuses(lambda: confirm.prepare(str(root), 'harden', ['analysis/x.py'])), bool)
        check('confirm-write target escape refused', 'confirm-write', 'SystemExit',
              lambda: refuses(lambda: confirm.prepare(str(root), 'harden', ['../outside/x']), SystemExit), bool)

        table = root/'samples.tsv'
        base_check = {'kind': 'schema', 'columns': ['sample', 'group']}
        def table_code(raw, check_spec=None):
            table.write_bytes(raw)
            _, alerts = contract.run_contract({'schema': contract.SCHEMA, 'table': 'samples.tsv',
                                               'checks': [check_spec or base_check]}, str(root))
            return contract.exit_code(alerts)
        cases = [('valid', b'sample\tgroup\na\tA\n', 0), ('empty', b'', 2),
                 ('header only', b'sample\tgroup\n', 2),
                 ('duplicate header', b'sample\tgroup\tgroup\na\tA\tB\n', 3),
                 ('extra field', b'sample\tgroup\na\tA\textra\n', 2),
                 ('unclosed quote', b'sample\tgroup\n"a\tA\n', 2),
                 ('invalid UTF8', b'sample\tgroup\n\xff\tA\n', 3)]
        for label, raw, code in cases:
            check('table ' + label, 'data-contract-check', 'exit ' + str(code),
                  lambda r=raw: table_code(r), lambda v, c=code: v == c)
        check('missing trailing value blocks no_missing', 'data-contract-check', 'exit 2',
              lambda: table_code(b'sample\tgroup\na\n', {'kind': 'cohort', 'no_missing': ['group']}), lambda v: v == 2)
        check('duplicate keys block', 'data-contract-check', 'exit 2',
              lambda: table_code(b'sample\tgroup\na\tA\na\tB\n', {'kind': 'unique_key', 'columns': ['sample']}), lambda v: v == 2)
        check('filter cannot pass vacuously', 'data-contract-check', 'exit 2',
              lambda: table_code(b'sample\tgroup\na\tA\n', dict(base_check, filters=[{'column': 'group', 'equals': 'B'}])), lambda v: v == 2)
        for key, val in [('rows', True), ('rows', -1), ('rows', 1.5), ('min_rows', '2')]:
            check('invalid cohort ' + key + '=' + repr(val), 'data-contract-check', 'ContractError',
                  lambda k=key, v=val: refuses(lambda: contract.validate({'kind': 'cohort', k: v}, 0), contract.ContractError), bool)

        # Independent CLI test: a checker advertised as read-only must preserve its inputs.
        table.write_text('sample\tgroup\na\tA\n')
        cp = root/'contract.json'
        cp.write_text(json.dumps({'schema': contract.SCHEMA, 'table': 'samples.tsv', 'checks': [base_check]}))
        for target in [table, cp]:
            before = target.read_bytes()
            result = subprocess.run([sys.executable, str(ROOT/'skills/data-contract-check/scripts/data_contract_check.py'),
                                     '--contract', str(cp), '--root', str(root), '--result-json', str(target)],
                                    capture_output=True, text=True, timeout=10)
            check('result cannot overwrite ' + target.name, 'data-contract-check', 'input unchanged and nonzero exit',
                  lambda p=target, b=before, r=result: {'unchanged': p.read_bytes() == b, 'exit': r.returncode},
                  lambda v: v['unchanged'] and v['exit'] != 0)
            target.write_bytes(before)

        for raw in [b'id,value\nx,1\nx,2\n', b'id,value,value\nx,1,2\n']:
            claim = root/'claim.csv'; claim.write_bytes(raw)
            check('ambiguous claim cell ' + repr(raw[:25]), 'verify', 'unreadable/ambiguous',
                  lambda p=claim: verify.claim_cell(str(p), 'value', 'x', 10000), lambda v: v[0] is None and bool(v[1]))
        claim = root/'claim.csv'
        claim.write_text('id,value\nx,0.05,unexpected\n')
        check('malformed extra-column claim table', 'verify', 'claim unavailable',
              lambda: verify.claim_cell(str(claim), 'value', 'x', 10000), lambda v: v[0] is None)
        claim.write_text('id,value\nx,"0.05\n')
        check('unterminated-quote claim table', 'verify', 'claim unavailable',
              lambda: verify.claim_cell(str(claim), 'value', 'x', 10000), lambda v: v[0] is None)
        claim_doc = root/'claims.md'
        claim_doc.write_text('<!-- claims\n0.05 | claim.csv value x\n-->\n')
        check('malformed CSV cannot verify a numeric claim', 'verify', 'unverified claim',
              lambda: verify.check_claims(str(root), None, [{'path': 'claim.csv'}],
                                          [str(claim_doc)], verify.Report(), 10000),
              lambda v: bool(v) and v[0]['claims'][0]['verdict'] == 'unverified')

        for ts in [float('nan'), float('inf'), True, -1]:
            digest = 'a'*64
            consent = state/'review-consent'; consent.mkdir(exist_ok=True)
            (consent/(digest+'.json')).write_text(json.dumps({'schema': packet.CONSENT_SCHEMA, 'digest': digest,
                'session_id': 'synthetic', 'ts': ts, 'prompt': 'send packet ' + digest[:12]}))
            check('packet consent rejects timestamp ' + repr(ts), 'plan-review', 'Refuse',
                  lambda: refuses(lambda: packet.check_consent(str(root), digest, {'created': int(time.time())-1}), packet.Refuse), bool)
        for raw in [b'redactions: []\n', b'redactions: []\nredactions: []\n', b'redactions: null\n']:
            check('presend redactions ' + repr(raw), 'plan-review', '0 for one empty list, otherwise 3',
                  lambda r=raw: presend.analyse(r, str(root))['exit'], lambda v, r=raw: v == (0 if r == b'redactions: []\n' else 3))
        for text in ['password=synthetic-password-long', 'person@example.invalid', '/home/synthetic/work']:
            check('presend detects ' + text.split('=')[0], 'plan-review', 'flag(s)',
                  lambda s=text: bool(presend.check(s)[0]), bool)
        check('empty default reason flagged', 'plan-review', 'at least one finding',
              lambda: bool(defaults.check_plan('| Step | Choice | Source | Validation |\n|---|---|---|---|\n| 1 | x | default: standard | check |\n')[2]), bool)

        for bad_id in [[], {}, 5, None, True, 'bad id']:
            binding = {'version': 1, 'checks': [{'id': bad_id, 'plan_row': '1', 'defined_by': 'researcher-approved',
                        'test_paths': ['analysis/x.py'], 'invocation': ['python', 'analysis/x.py'],
                        'evidence_path': 'analysis/result.json'}]}
            text = '<!-- validation-bindings ' + json.dumps(binding) + ' -->'
            check('validation binding rejects id ' + repr(bad_id), 'validation', 'errors returned without exception',
                  lambda t=text: validation.read_bindings(t, ['1'], str(root)),
                  lambda v: v[0] is None and bool(v[1]))

        # Corrupt recorded history should be localized and exposed as partial coverage.
        for bad in [float('nan'), float('inf'), [], {}]:
            receipt = {'schema': 'mycelium-extra.receipt.v1', 'plans': [], 'focus_folder': 'analysis',
                       'command': 'python analysis/x.py', 'paths': ['analysis/x.py'],
                       'ts': bad, 'attempt_id': 'synthetic', 'exit_status': 0, 'kind': 'python'}
            (state/'receipts.jsonl').write_text(json.dumps(receipt) + '\n')
            check('journal tolerates malformed receipt timestamp ' + repr(bad), 'track-changes',
                  'journal returned with an explicit gap or unknown time',
                  lambda: journal.collect(str(root), 'analysis', gate, focus),
                  lambda v: isinstance(v, dict) and isinstance(v.get('coverage'), dict))
        (state/'receipts.jsonl').unlink()

        decision = root/'decisions.md'
        decision.write_text('## 2026-01-01 Real\n**Status:** confirmed\n```\n## 2026-01-02 Fake\n**Status:** superseded\n```\n')
        check('fenced fake decision ignored', 'decision-status', 'one confirmed real entry',
              lambda: decisions.parse_entries(str(decision)), lambda v: len(v) == 1 and v[0]['status'] == 'confirmed')
        for steps in ['', '../01_x.py', '01_a.py,01_b.R', '02_b.R,01_a.py', '01_a.sh']:
            check('scaffold rejects ' + repr(steps), 'new-analysis', 'Refusal',
                  lambda s=steps: refuses(lambda: scaffold.parse_steps(s), scaffold.Refusal), bool)
        check('scaffold supports mixed ordered steps', 'new-analysis', '3 linked steps',
              lambda: scaffold.parse_steps('01_a.R,02_b.py,03_c.ipynb'),
              lambda v: len(v) == 3 and v[1]['input'] == v[0]['output'])
        check('idea registry escapes cell metacharacters', 'idea', 'no raw bars or line breaks',
              lambda: capture.cell('x|y\r\nz'), lambda v: '|' not in v and '\n' not in v and '\r' not in v)
        for rel in ['../outside', 'analysis/../../outside', '/tmp/outside']:
            check('focus rejects ' + rel, 'focus', 'FocusError',
                  lambda r=rel: refuses(lambda: focus.resolve_target(str(root), r, ['analysis']), focus.FocusError), bool)
        check('session names avoid sanitize collisions', 'focus', 'different names',
              lambda: focus.session_name('a/b') != focus.session_name('a_b'), bool)
        for rel in ['../outside/n.md', '/tmp/n.md']:
            check('journal note rejects ' + rel, 'track-changes', 'ValueError',
                  lambda r=rel: refuses(lambda: journal.note(str(root), r)), bool)
        check('HTML embedded data cannot close script', 'track-changes', 'no raw markup',
              lambda: render.embed({'text': '</script><img src=x onerror=alert(1)>&\u2028'}),
              lambda v: '<' not in v and '>' not in v and '&' not in v and '\u2028' not in v)
        for ts in [float('nan'), float('inf'), True, '2026']:
            check('journal rejects timestamp ' + repr(ts), 'track-changes', 'None',
                  lambda v=ts: journal.utc(v), lambda v: v is None)
        for actual in [['python', 'analysis/x.py', '--new'], ['python', '$SCRIPT'], ['python', 'analysis/x.py']]:
            check('exact invocation ' + repr(actual), 'validation', 'only exact argv matches',
                  lambda a=actual: validation.argv_matches(['python', 'analysis/x.py'], a)[0],
                  lambda v, a=actual: v == (a == ['python', 'analysis/x.py']))
        check('fidelity rejects duplicate JSON keys', 'method-fidelity', 'ValueError',
              lambda: refuses(lambda: fidelity.unique_object([('assay','a'), ('assay','b')])), bool)
        check('provenance invalid digest writes nothing', 'provenance', 'ValueError',
              lambda: refuses(lambda: provenance.publish(str(root/'provenance'), '../bad', lambda _: [])), bool)

        # Exercise every shipped Python CLI parser. No user project is the cwd.
        entrypoints = sorted(ROOT.glob('skills/*/scripts/*.py')) + [ROOT/'hooks/confirm_write.py']
        for entry in entrypoints:
            if entry.name in ('journal.py', 'render.py'):
                continue  # Libraries, not commands.
            def cli_help(p=entry):
                r = subprocess.run([sys.executable, str(p), '--help'], cwd=tmp, capture_output=True, text=True, timeout=15)
                return {'exit': r.returncode, 'usage': 'usage:' in r.stdout.lower(), 'traceback': 'Traceback' in r.stderr}
            check('CLI help ' + str(entry.relative_to(ROOT)), entry.parent.parent.name,
                  'exit 0, usage, no traceback', cli_help,
                  lambda v: v['exit'] == 0 and v['usage'] and not v['traceback'])

        init = ROOT/'skills/init/scripts/gate_init.py'
        init_root = Path(tmp)/'init'; init_root.mkdir()
        check('init dry run writes no files', 'init', 'empty directory and exit 0',
              lambda: {'exit': subprocess.run([sys.executable, str(init), '--root', str(init_root), '--dry-run'],
                      capture_output=True, timeout=15).returncode, 'files': [p.name for p in init_root.iterdir()]},
              lambda v: v['exit'] == 0 and not v['files'])
        check('focus list CLI on ungated project', 'focus', 'exit 0 and no traceback',
              lambda: subprocess.run([sys.executable, str(ROOT/'hooks/focus.py'), 'list', '--repo', str(init_root)],
                                     capture_output=True, text=True, timeout=15).returncode,
              lambda v: v == 0)
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--h5ad-only', action='store_true', help='run optional H5AD probes with existing h5py/numpy')
    args = parser.parse_args()
    try:
        rows = h5ad_cases() if args.h5ad_only else run()
    except ImportError as error:
        Path(args.output).write_text(json.dumps({'status': 'gap', 'reason': str(error)}) + '\n')
        print('Optional reader unavailable: ' + str(error), file=sys.stderr)
        sys.exit(3)
    result = {'python': sys.version, 'cases': rows, 'passed': sum(r['holds'] for r in rows),
              'failed': sum(not r['holds'] for r in rows)}
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=True) + '\n')
    print('{} passed; {} violated contracts'.format(result['passed'], result['failed']))
    for row in rows:
        if not row['holds']:
            print('{}: {} -> {}'.format(row['area'], row['case'], repr(row['actual'])[:250]))
    sys.exit(bool(result['failed']))
