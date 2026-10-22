"""Real upstream helpers in disposable projects; set MYCELIUM_UPSTREAM to a checkout.

These checks exercise file interfaces, not native host dispatch or model behavior.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path(os.environ.get('MYCELIUM_UPSTREAM', '/nonexistent-mycelium-checkout'))
PACK = ROOT / 'plans/sc-conventions-revised/network/conventions/single-cell-analysis'


@unittest.skipUnless((UPSTREAM / 'skills/core/scripts').is_dir(), 'set MYCELIUM_UPSTREAM to test real helpers')
class MyceliumInterfaces(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        (self.project / '.living').mkdir()

    def run_script(self, script, *args):
        result = subprocess.run([sys.executable, str(script)] + [str(a) for a in args],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    @unittest.skipUnless(PACK.is_dir(), 'reviewed local-only convention pack absent')
    def test_install_revised_pack_and_dependency(self):
        guidance = self.project / 'MYCELIUM.md'
        guidance.write_text('# Project\n\n### Domain (opt-in)\nNo domain conventions installed yet.\n')
        for name, network in [('bioinformatics', UPSTREAM / 'network/conventions'),
                              ('single-cell-analysis', PACK.parent)]:
            with self.subTest(pack=name):
                self.run_script(UPSTREAM / 'skills/core/scripts/install_convention.py',
                                '--name', name, '--network-dir', network, '--target-dir', self.project)
                source = network / name
                dest = self.project / '.living/conventions' / name
                files = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
                self.assertEqual(files, {p.relative_to(dest): p.read_bytes() for p in dest.rglob('*') if p.is_file()})
                self.assertIn(name, (self.project / '.living/conventions/ACTIVE_CONVENTIONS.yaml').read_text())
                self.assertIn(name, guidance.read_text())
        self.assertFalse((dest / 'ROADMAP.md').exists())
        self.assertFalse((dest / 'prototypes').exists())

    def test_new_analysis_reads_upstream_template(self):
        pointer = self.project / '.mycelium/plugin-root'
        pointer.parent.mkdir()
        pointer.write_text(str(UPSTREAM.resolve()) + '\n')
        output = self.run_script(ROOT / 'skills/new-analysis/scripts/new_analysis.py',
                                 '--templates=' + str(ROOT / 'skills/new-analysis/templates'),
                                 '--dest=' + str(self.project / 'analysis/compat-probe'))
        self.assertIn("Mycelium's template at", output)
        self.assertTrue((self.project / 'analysis/compat-probe/COMPAT_PROBE.md').is_file())

    def test_idea_uses_upstream_updater_without_losing_duplicate_titles(self):
        idea = self.project / 'idea.txt'
        idea.write_text('Compatibility test duplicate title\nVerbatim | body.')
        for _ in range(2):
            self.run_script(ROOT / 'skills/idea/scripts/capture.py', '--plugin-root', ROOT,
                            '--root', self.project, '--helper', UPSTREAM / 'skills/core/scripts/upsert_table_row.py',
                            '--python', sys.executable, '--text-file', idea)
        registry = (self.project / 'todo/TODO_REGISTRY.md').read_text()
        files = [p for p in (self.project / 'todo').glob('*.md') if p.name != 'TODO_REGISTRY.md']
        self.assertEqual(len(files), 2)
        for path in files:
            self.assertEqual(registry.count('[{}]({})'.format(path.name, path.name)), 1)
            self.assertIn(idea.read_text(), path.read_text())

    def test_verify_consumes_actual_upstream_lineage_manifest(self):
        output = self.project / 'output.txt'
        output.write_text('synthetic output')
        ts = '2026-10-21T12:00:00Z'
        events = self.project / 'events.jsonl'
        events.write_text(json.dumps({'ts': ts, 'script': 'analysis/a/01_fit.R',
                                      'bash_cmd': 'Rscript analysis/a/01_fit.R', 'bash_exit': 0,
                                      'io_detection': 'static', 'outputs': [{'path': str(output)}]}) + '\n')
        manifest = self.project / '.living/log/data-lineage/compat.json'
        self.run_script(UPSTREAM / 'skills/core/scripts/extract_data_lineage.py',
                        '--events-file', events, '--output', manifest,
                        '--session-id', 'compat-session', '--repo-root', self.project)
        sys.path.insert(0, str(ROOT / 'skills/verify/scripts'))
        import verify
        stamp = verify.parse_iso(ts)
        actions = verify.lineage_actions(str(self.project), stamp - 1, stamp + 1)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['session'], 'compat-session')
        self.assertEqual(actions[0]['exit'], 0)
        self.assertEqual(actions[0]['io'], 'static')
        self.assertEqual(actions[0]['files'][0]['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_hooks_keep_approval_and_reflection_independent(self):
        sys.path.insert(0, str(ROOT / 'tests/e2e'))
        import harness
        for host in ('codex', 'claude'):
            for parallel in (False, True):
                with self.subTest(host=host, parallel=parallel):
                    project = harness.Project.fresh(r=False)
                    try:
                        self.check_hook_lifecycle(project, host, parallel)
                    finally:
                        project.close()

    def check_hook_lifecycle(self, project, host, parallel):
        root = Path(project.root)
        (Path(project.bin) / 'python3').symlink_to(sys.executable)
        env = {k: v for k, v in os.environ.items() if not k.startswith(('MYCELIUM_', 'MX_'))
               and k not in ('CLAUDE_PROJECT_DIR', 'PLUGIN_ROOT')}
        env.update(PATH=project.bin + os.pathsep + env['PATH'],
                   MYCELIUM_KNOWLEDGE_DIR=str(root / '.knowledge'), PYTHONDONTWRITEBYTECODE='1')
        if host == 'claude':
            env['CLAUDE_PROJECT_DIR'] = str(root)
        session = 'synthetic-coexistence'

        def hook(plugin, action, **payload):
            if plugin == 'mycelium':
                command = (['bash', str(UPSTREAM / 'hooks/mycelium-codex-dispatch.sh'), action]
                           if host == 'codex' else ['bash', str(UPSTREAM / 'skills/core/hooks' / action)])
            else:
                command = ['sh', str(ROOT / 'hooks/py.sh'), '--hook', str(ROOT / 'hooks/gate_run.py')]
                command += ['--host', 'codex', action] if host == 'codex' else [action]
            event = dict(payload, cwd=str(root), session_id=session)
            runtime = dict(env, PLUGIN_ROOT=str(UPSTREAM if plugin == 'mycelium' else ROOT),
                           MYCELIUM_PLUGIN_ROOT=str(UPSTREAM))
            result = subprocess.run(command, cwd=root, env=runtime, input=json.dumps(event),
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout) if result.stdout.strip() else None
            self.assertNotIn('gate error', str(value))
            return value

        def snapshot(folder):
            return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()}

        hook('mycelium', 'mycelium-health.sh', source='startup')
        script = 'analysis/vaccine-response/scripts/01_select_samples.py'
        bash = dict(tool_name='Bash', tool_input={'command': 'python3 ' + script}, tool_use_id='run-1')
        upstream_before = snapshot(root / '.mycelium')
        denied = hook('extra', 'tool', **bash)
        self.assertEqual(denied['hookSpecificOutput']['permissionDecision'], 'deny')
        plan = '## Plan\n| 1 | run `' + script + '` | repo | check |\n\nPlan status: READY'
        notice = hook('extra', 'stop', last_assistant_message=plan)
        digest = notice['systemMessage'].split('approve plan ')[1][:8]
        hook('extra', 'prompt', prompt='approve plan ' + digest)
        self.assertIsNone(hook('extra', 'tool', **bash))
        self.assertEqual(snapshot(root / '.mycelium'), upstream_before)
        run = subprocess.run(['python3', script], cwd=root, env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        payload = dict(bash, hook_event_name='PostToolUse',
                       tool_response={'exit_code': 0, 'stdout': run.stdout, 'stderr': run.stderr})
        if host == 'claude':
            payload['tool_response'] = dict(stdout=run.stdout, stderr=run.stderr,
                                            interrupted=False, isImage=False)
        callbacks = [('mycelium', 'mycelium-post-action.sh'), ('extra', 'post'),
                     ('mycelium', 'mycelium-data-tracker.sh')]
        if parallel:
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [pool.submit(hook, plugin, action, **payload) for plugin, action in callbacks]
                for future in futures:
                    future.result()
        else:
            for plugin, action in callbacks:
                hook(plugin, action, **payload)
        receipts = project.receipts()
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]['exit_status'], 0)
        self.assertEqual(receipts[0]['plans'], [digest])
        extra_before = snapshot(root / '.mycelium-extra')
        blocked = hook('mycelium', 'mycelium-stop-check.sh', hook_event_name='Stop')
        self.assertEqual(blocked['decision'], 'block')
        self.assertIn('.living/', blocked['reason'])
        manifests = list((root / '.living/log/data-lineage').glob('*.json'))
        self.assertEqual(len(manifests), 1)
        actions = json.loads(manifests[0].read_text())['actions']
        self.assertEqual(len(actions), 1)
        self.assertTrue(actions[0]['script'].endswith(script))
        self.assertEqual(snapshot(root / '.mycelium-extra'), extra_before)
        with (root / '.living/learnings.md').open('a') as handle:
            handle.write('\n### Synthetic coexistence check\nSample selection completed; no scientific finding.\n')
        private = root / '.mycelium/run' / host / session
        (private / 'last-session.md').write_text(
            '# Synthetic handoff\n\n## What worked on\nRan sample selection.\n\n'
            '## Key decisions\nUsed fixture plan.\n### Locked decisions\nSynthetic test only.\n\n'
            '## Blockers\nNone.\n### Dead ends — do not redo\nNone.\n\n'
            '## Current state\nOutput written; no scientific finding.\n\n## Next steps\nFinish lifecycle.\n')
        accepted = hook('mycelium', 'mycelium-stop-check.sh', hook_event_name='Stop')
        self.assertNotEqual((accepted or {}).get('decision'), 'block')
        self.assertTrue((root / '.mycelium/last-session.md').is_file())
        self.assertEqual(snapshot(root / '.mycelium-extra'), extra_before)


if __name__ == '__main__':
    unittest.main()
