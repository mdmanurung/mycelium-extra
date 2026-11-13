#!/usr/bin/env python3
"""Compare approved intent with an executed-model record; never authenticate a fitted model.

Two modes, chosen by the schema of the --expected file.
R3: field-by-field agreement of a recorded model (method_expectations.v1 vs executed_model.v1).
R5: the design matrix and contrast the fitting code wrote (design_expectations.v1 vs fit_design.v1).

Python 3.6+, standard library only. Exit 0: recorded agreement; 2: drift; 3: unavailable/malformed evidence.
"""
import argparse
import hashlib
import json
import math
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


def read_record(role, path):
    identity = {'role': role, 'path': os.path.abspath(path), 'sha256': None}
    try:
        with open(path, 'rb') as handle:
            raw = handle.read()
        identity.update(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
        return identity, json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object), None
    except (OSError, ValueError, TypeError, RecursionError) as error:
        return identity, None, role + ': ' + str(error)


def envelope(inputs, checks, limit):
    if any(c['status'] == 'gap' for c in checks):
        code, status = 3, 'gap'
    elif any(c['status'] == 'block' for c in checks):
        code, status = 2, 'block'
    else:
        code, status = 0, 'pass'
    return {'schema': 'mycelium-extra.contract_result.v1', 'status': status, 'exit_code': code,
            'contract': {k: inputs[0][k] for k in ('path', 'sha256')}, 'inputs': inputs,
            'checks': checks, 'message': limit}


def compare(expected_path, observed_path):
    expected_id, expected, expected_error = read_record('expected', expected_path)
    observed_id, observed, observed_error = read_record('observed', observed_path)
    inputs = [expected_id, observed_id]
    if isinstance(expected, dict) and expected.get('schema') == DESIGN_EXPECTED:
        return compare_design(inputs, expected, observed, observed_error)
    errors = []
    for role, record, error, schema in (
            ('expected', expected, expected_error, 'mycelium-extra.method_expectations.v1'),
            ('observed', observed, observed_error, 'mycelium-extra.executed_model.v1')):
        try:
            if error:
                raise ValueError(error.split(': ', 1)[1])
            validate(record, schema)
        except (ValueError, TypeError) as caught:
            errors.append(role + ': ' + str(caught))
    if errors:
        checks = [{'id': 'method-fidelity', 'status': 'gap', 'message': '; '.join(errors)}]
    else:
        checks = []
        for field in FIELDS:
            left, right = expected[field], observed[field]
            agrees = sorted(left) == sorted(right) if field in LISTS else left == right
            checks.append({'id': 'method-' + field, 'status': 'pass' if agrees else 'block',
                           'expected': left, 'observed': right,
                           'message': field + (' agrees' if agrees else ' differs from approved intent')})
    return envelope(inputs, checks, LIMIT)


# R5: design matrix and contrast from the fit itself ------------------------------------------------

DESIGN_EXPECTED = 'mycelium-extra.design_expectations.v1'
FIT_DESIGN = 'mycelium-extra.fit_design.v1'
DESIGN_LIMIT = ('Checks that the design matrix and contrast the fitting code wrote match the approved ones, '
                'and that the contrast is estimable and not aliased with batch. Matches columns by name and reads '
                'no coding: a sum or Helmert column under a treatment-style name passes. Does not authenticate '
                'that the record came from the fit (the extraction snippet trusts the design and contrast '
                'it is given), or show that the analysis is scientifically valid.')
TOLERANCE = 1e-9
ZERO_COLUMN = 1e-12  # column length, relative to the longest column, below which a column counts as zero


def is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_design_expected(record):
    allowed = {'schema', 'contrast', 'batch_columns', 'formula', 'sample_table_sha256'}
    if set(record) - allowed or not {'contrast', 'batch_columns'} <= set(record):
        raise ValueError('expected record needs contrast and batch_columns; optional: formula, sample_table_sha256')
    contrast = record['contrast']
    if (not isinstance(contrast, dict) or not contrast or
            not all(isinstance(k, str) and k.strip() and is_number(v) for k, v in contrast.items()) or
            not any(contrast.values())):
        raise ValueError('contrast must map design column names to numeric weights, at least one nonzero')
    batch = record['batch_columns']
    if not isinstance(batch, list) or not all(isinstance(b, str) and b.strip() for b in batch) or len(set(batch)) != len(batch):
        raise ValueError('batch_columns must be a list of unique nonempty design column names (empty list: no batch)')
    for field in ('formula', 'sample_table_sha256'):
        if field in record and (not isinstance(record[field], str) or not record[field].strip()):
            raise ValueError(field + ' must be a nonempty string when given')


def read_design(record):
    """Return (columns, rows, contrast, why-not). A missing design is a gap, not a block."""
    if not isinstance(record, dict) or record.get('schema') != FIT_DESIGN:
        return None, None, None, 'fit output is not a ' + FIT_DESIGN + ' record'
    columns, rows = record.get('design_columns'), record.get('design')
    if not columns or not rows:
        return None, None, None, 'fit output holds no design matrix (design_columns or design is missing or empty)'
    if (not isinstance(columns, list) or not all(isinstance(c, str) and c for c in columns) or
            len(set(columns)) != len(columns)):
        return None, None, None, 'design_columns must be unique nonempty strings'
    if (not isinstance(rows, list) or not all(isinstance(r, list) and len(r) == len(columns) and
                                              all(is_number(v) for v in r) for r in rows)):
        return None, None, None, 'design must be rows of finite numbers, one value per design column'
    contrast = record.get('contrast')
    if (not isinstance(contrast, dict) or not contrast or
            not all(k in columns and is_number(v) for k, v in contrast.items())):
        return None, None, None, 'fit contrast must map design columns to numeric weights'
    return columns, rows, contrast, None


def rank(matrix):
    """Rank by Gaussian elimination with partial pivoting on unit-length columns; a pivot below a relative
    tolerance counts as zero."""
    work = [list(map(float, row)) for row in matrix]
    if not work:
        return 0
    # Scale each column to unit length first: rank does not change, but one column of raw depth or library
    # size no longer makes the 0/1 columns look like zero pivots.
    norms = [math.sqrt(sum(row[j] ** 2 for row in work)) for j in range(len(work[0]))]
    floor = ZERO_COLUMN * max(norms)  # a column this small next to the largest is zero, not a column to scale up
    norms = [n if n > floor else 1.0 for n in norms]
    work = [[v / n for v, n in zip(row, norms)] for row in work]
    scale = max((abs(v) for row in work for v in row), default=0.0)
    if scale == 0:
        return 0
    found, width = 0, len(work[0])
    for col in range(width):
        pivot = max(range(found, len(work)), key=lambda r: abs(work[r][col]), default=None)
        if pivot is None or abs(work[pivot][col]) <= TOLERANCE * scale * max(len(work), width):
            continue
        work[found], work[pivot] = work[pivot], work[found]
        for r in range(found + 1, len(work)):
            factor = work[r][col] / work[found][col]
            if factor:
                work[r] = [a - factor * b for a, b in zip(work[r], work[found])]
        found += 1
        if found == len(work):
            break
    return found


def estimable(rows, weights):
    """A contrast is estimable when it lies in the row space of the design."""
    return rank(rows + [weights]) == rank(rows)


def drop_columns(rows, indices):
    keep = [i for i in range(len(rows[0])) if i not in indices]
    return [[row[i] for i in keep] for row in rows]


def compare_design(inputs, expected, observed, observed_error):
    checks = []
    try:
        validate_design_expected(expected)
    except ValueError as error:
        return envelope(inputs, [{'id': 'fit-design', 'status': 'gap', 'message': 'expected: ' + str(error)}], DESIGN_LIMIT)
    columns, rows, contrast, why = (None, None, None, observed_error) if observed_error else read_design(observed)
    if why:
        return envelope(inputs, [{'id': 'fit-design', 'status': 'gap', 'message': 'observed: ' + why}], DESIGN_LIMIT)
    fitted = {k: float(v) for k, v in contrast.items() if v}
    approved = {k: float(v) for k, v in expected['contrast'].items() if v}
    agrees = set(fitted) == set(approved) and all(abs(fitted[k] - approved[k]) <= TOLERANCE for k in fitted)
    if 'formula' in expected:
        same = ''.join(str(observed.get('formula')).split()) == ''.join(expected['formula'].split())  # spacing is not a model change
        checks.append({'id': 'fit-formula', 'status': 'pass' if same else 'block', 'expected': expected['formula'],
                       'observed': observed.get('formula'),
                       'message': 'formula ' + ('agrees' if same else 'differs from approved intent')})
    if 'sample_table_sha256' in expected:
        same = observed.get('sample_table_sha256') == expected['sample_table_sha256']
        checks.append({'id': 'fit-sample-table', 'status': 'pass' if same else 'block',
                       'message': 'sample table hash ' + ('agrees' if same else 'differs from the approved table')})
    checks.append({'id': 'fit-contrast', 'status': 'pass' if agrees else 'block', 'expected': approved,
                   'observed': fitted, 'message': 'fitted contrast ' + (
                       'equals the approved contrast, sign included' if agrees else 'differs from the approved contrast')})
    weights = [float(contrast.get(c, 0)) for c in columns]
    batch = expected["batch_columns"]
    missing = [c for c in batch if c not in columns]
    batch_index = {columns.index(c) for c in batch if c in columns}
    full_rank = rank(rows)
    ok_full = estimable(rows, weights)
    without = drop_columns(rows, batch_index) if batch_index else rows
    ok_without = estimable(without, [w for i, w in enumerate(weights) if i not in batch_index])
    if ok_full:
        message = 'contrast is estimable'
    elif ok_without:
        message = 'contrast is estimable without the batch columns but not with them: aliased with batch'
    else:
        message = 'contrast is not estimable: it is not in the row space of the design'
    checks.append({'id': 'fit-estimable', 'status': 'pass' if ok_full else 'block', 'message': message,
                   'design_rank': full_rank, 'design_columns': len(columns), 'estimable_without_batch': ok_without})
    if missing:
        checks.append({'id': 'fit-batch-term', 'status': 'block', 'message': 'approved batch columns are absent '
                       'from the fitted design: ' + ', '.join(missing)})
    elif batch_index:
        # The contrast's per-sample group indicator (design times contrast) against the batch indicator.
        indicator = [sum(w * v for w, v in zip(weights, row)) for row in rows]
        batch_space = [[row[i] for i in sorted(batch_index)] + [1.0] for row in rows]
        confounded = rank([r + [g] for r, g in zip(batch_space, indicator)]) == rank(batch_space)
        checks.append({'id': 'fit-batch-confounding', 'status': 'block' if confounded else 'pass',
                       'message': 'the contrast group indicator ' + ('is a function of batch: perfectly confounded'
                                                                      if confounded else 'is not a function of batch')})
    return envelope(inputs, checks, DESIGN_LIMIT)


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
