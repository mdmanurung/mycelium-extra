#!/usr/bin/env python3
"""Compare approved intent with an executed-model record; never authenticate a fitted model.

Python 3.6+, standard library only. Exit 0: recorded agreement; 2: drift; 3: unavailable/malformed evidence.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile

FIELDS = ('formula', 'contrast', 'random_effects', 'covariates', 'assay', 'exclusions')
LISTS = ('random_effects', 'covariates', 'exclusions')
LIMIT = ('Checks recorded field fidelity only; does not extract or authenticate a fitted model, '
         'establish model validity, or prove that the record describes the execution.')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def validate(record, schema):
    if not isinstance(record, dict) or record.get('schema') != schema:
        raise ValueError('unsupported or missing schema: expected ' + schema)
    if set(record) != set(FIELDS) | {'schema'}:
        raise ValueError('missing or unknown fields: expected ' + ', '.join(FIELDS))
    for field in ('formula', 'assay'):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError(field + ' must be a nonempty string')
    for field in LISTS:
        values = record[field]
        if (not isinstance(values, list) or
                not all(isinstance(v, str) and v.strip() for v in values) or len(set(values)) != len(values)):
            raise ValueError(field + ' must be an explicit list of unique nonempty strings')
    contrast = record['contrast']
    if not isinstance(contrast, dict) or set(contrast) != {'numerator', 'denominator', 'sign'}:
        raise ValueError('contrast needs numerator, denominator and sign')
    if not all(isinstance(contrast[k], str) and contrast[k].strip() for k in ('numerator', 'denominator')):
        raise ValueError('contrast numerator and denominator must be nonempty strings')
    if contrast['numerator'] == contrast['denominator']:
        raise ValueError('contrast numerator and denominator must differ')
    if type(contrast['sign']) is not int or contrast['sign'] not in (-1, 1):
        raise ValueError('contrast sign must be integer 1 or -1')


def compare(expected_path, observed_path):
    inputs, records, errors = [], [], []
    for role, path, schema in (
            ('expected', expected_path, 'mycelium-extra.method_expectations.v1'),
            ('observed', observed_path, 'mycelium-extra.executed_model.v1')):
        identity = {'role': role, 'path': os.path.abspath(path), 'sha256': None}
        try:
            with open(path, 'rb') as handle:
                raw = handle.read()
            identity.update(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
            record = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object)
            validate(record, schema)
            records.append(record)
        except (OSError, ValueError, TypeError, RecursionError) as error:
            errors.append(role + ': ' + str(error))
        inputs.append(identity)
    checks = []
    if errors:
        code, status = 3, 'gap'
        checks.append({'id': 'method-fidelity', 'status': 'gap', 'message': '; '.join(errors)})
    else:
        expected, observed = records
        for field in FIELDS:
            left, right = expected[field], observed[field]
            agrees = sorted(left) == sorted(right) if field in LISTS else left == right
            checks.append({'id': 'method-' + field, 'status': 'pass' if agrees else 'block',
                           'expected': left, 'observed': right,
                           'message': field + (' agrees' if agrees else ' differs from approved intent')})
        code = 2 if any(c['status'] == 'block' for c in checks) else 0
        status = 'block' if code else 'pass'
    return {'schema': 'mycelium-extra.contract_result.v1', 'status': status, 'exit_code': code,
            'contract': {k: inputs[0][k] for k in ('path', 'sha256')}, 'inputs': inputs,
            'checks': checks, 'message': LIMIT}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected', required=True)
    parser.add_argument('--observed', required=True)
    parser.add_argument('--result-json', required=True)
    args = parser.parse_args(argv)
    if os.path.realpath(args.result_json) in (os.path.realpath(args.expected), os.path.realpath(args.observed)):
        print('result path must differ from both input paths', file=sys.stderr)
        return 3
    result = compare(args.expected, args.observed)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=os.path.dirname(os.path.abspath(args.result_json)),
                                         delete=False) as handle:
            temporary = handle.name
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write('\n')
        os.replace(temporary, args.result_json)
    except OSError as error:
        print('cannot write result: ' + str(error), file=sys.stderr)
        return 3
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    print(json.dumps(result, sort_keys=True))
    return result['exit_code']


if __name__ == '__main__':
    sys.exit(main())
