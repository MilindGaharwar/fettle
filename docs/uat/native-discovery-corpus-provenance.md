# Native Discovery Held-Out Corpus Provenance

Authored: 2026-09-22. Status: frozen author corpus; candidate qualification NOT RUN.

## Identity and Scope

Corpus: [evals/uat-native-discovery-heldout-2026-09-22.json](../../evals/uat-native-discovery-heldout-2026-09-22.json).

SHA-256 of the exact UTF-8 corpus file bytes, including its final newline:

```text
6067cee014a6e86dd529d630d687e1e730ba866e4a35d13903022ba3016d6b37
```

This is not a canonicalized JSON hash or a hash of this provenance document.
There are 2 suites and 12 cases: 2 healthy baselines, 8 seeded violations,
and 2 timeout controls. Each suite contains exactly 6 variants.

| Suite | Inclusive range | Inside / outside / invalid | Expected states |
| --- | --- | --- | --- |
| signed-window | -24 through 73 | admit / reject / malformed | 1 pass, 4 violation, 1 unknown |
| positive-window | 120 through 480 | within / beyond / invalid | 1 pass, 4 violation, 1 unknown |

The domain is these reviewed, synthetic integer-classification fixtures only.
It does not authorize arbitrary source synthesis or execution of unreviewed code.
Sources use only `re` and `sys`, plus `time` in the timeout controls. They contain
no loops, file access, network access, process creation, environment access,
credential access, or dynamic evaluation. Each source reads `sys.argv[1]` once.
Exactly one argument is an invocation precondition; missing or extra arguments
are outside this qualification interface.

## Independence and Freeze

The user explicitly authorized this held-out authorship. No tools were used to
read Fettle implementation, tests, previous corpora, results, session memories,
logs, or prompts. No candidate, Fettle command, native model, or subagent was
run. No credentials were accessed. No candidate-selected inputs were available
to or used by this author. The ranges, words, defect mechanisms, and witnesses
were chosen independently for this artifact.

The session already contained platform-supplied repository instructions,
preferences, and terminal summaries before this request. This is therefore a
statement of active-read and design independence, not an assertion of a fresh,
air-gapped context. That supplied context was not used as fixture evidence.

Only the two authorized new files were written, using manual `apply_patch`.
No repository scan, commit, push, environment setup, or installation was done.
The user's explicit prohibition on running Fettle takes precedence over the
usual quality-scan workflow for this authorship task.

The JSON was authored once and was not changed in response to any candidate
behavior. The validator-command correction described below changed no corpus
bytes. On delivery of the hash, both artifacts are frozen. Any later correction
requires a separately identified corpus and new provenance, retaining this
version and its evidence; do not silently revise this held-out corpus.

## Exposure and Oracle Contract

For each suite, expose ONLY its `requirements` string and the generic
`python app.py ARG` CLI shape to the selecting model. Do not expose the corpus,
oracle object, source, case identifiers, expected states, this document, or
author witness lists. Requirements describe the full public grammar and
behavior without revealing seeds or example input lists.

Select at most 12 distinct strings per suite, each at most 64 UTF-8 bytes with
no NUL. An empty string is a permitted test argument, but invalid product syntax.
Freeze the selected list before executing any variant, and reuse exactly that
list across all variants in its suite. Pass each string as a single argument,
not as shell text. Do not normalize whitespace, signs, zeros, or Unicode.
No variant-specific reselection, feedback-based repair, or retuning is allowed.
A missing or empty selection cannot provide evidence of behavioral acceptance.

The independent oracle is the JSON's declarative range policy:

1. Require the entire argument to match optional ASCII `+` or `-`, followed by
   one or more ASCII digits. All whitespace and all other characters are invalid.
2. Parse valid strings as signed base-10 integers; allow leading zeros and signed zero.
3. Compare numerically against both inclusive bounds and select the declared word.
4. Require that word plus exactly one newline on stdout, exit code 0, and empty stderr.

The oracle does not derive expectations from any product variant. Author checks
use a separate ASCII grammar and JavaScript `BigInt` for the policy. Within the
64-byte input domain, normal Python integer conversion handles every valid
argument here; arbitrary-length arguments beyond that domain were not assessed.

## Witness Evidence

All strings below use JSON escaping: `\n` denotes a newline, not two literal
characters. The Unicode witness `"\u0661\u0662\u0660"` is three Arabic-Indic
digits, 6 UTF-8 bytes, representing 120 under Python's Unicode digit parsing.
Every witness is within the allowed input size and contains no NUL.

**Evidence level:** the actual columns are source-derived results checked by
the restricted static semantic evaluator below, NOT observations of a Python
process. For each non-timeout row, expected and source-derived exit codes are
both 0 and expected and source-derived stderr are both `""`.

| Case | Plausible mechanism | Input | Oracle stdout | Source-derived actual stdout |
| --- | --- | --- | --- | --- |
| signed-lower-open | Exclusive lower comparison | `"-24"` | `"admit\n"` | `"reject\n"` |
| signed-upper-open | Exclusive upper comparison | `"73"` | `"admit\n"` | `"reject\n"` |
| signed-unsigned-only | Validator accepts only unsigned decimal strings | `"+0"` | `"admit\n"` | `"malformed\n"` |
| signed-trims-space | Input normalization before syntax validation | `" 0"` | `"malformed\n"` | `"admit\n"` |
| positive-no-leading-zero | Canonical-number regex rejects padding | `"0120"` | `"within\n"` | `"invalid\n"` |
| positive-unicode-digits | Unicode `\d` mistaken for ASCII digits | `"\u0661\u0662\u0660"` | `"invalid\n"` | `"within\n"` |
| positive-magnitude | Sign discarded by magnitude conversion | `"-120"` | `"beyond\n"` | `"within\n"` |
| positive-text-order | Numeric bounds compared as strings | `"2"` | `"beyond\n"` | `"within\n"` |

These are general grammar, normalization, or comparison faults, not secret
trigger traps. Baselines use full ASCII matching, ordinary signed integer
conversion, and the exact inclusive policy bounds. Their only output operation
is one `print` in the selected branch; they make no stderr writes and terminate
normally. Under the stated invocation and input-size preconditions, those
straight-line semantics satisfy the policy.

Healthy checks covered the following 28 inputs per baseline, independently of
any selecting model. The author validation set is not a model discovery list
and is not subject to that model's 12-selection budget.

| Healthy baseline inputs | signed-baseline stdout | positive-baseline stdout |
| --- | --- | --- |
| Respective minimum minus one: `"-25"` / `"119"` | `"reject\n"` | `"beyond\n"` |
| Respective minimum and next integer: `"-24"`, `"-23"` / `"120"`, `"121"` | `"admit\n"` | `"within\n"` |
| Respective maximum minus one and maximum: `"72"`, `"73"` / `"479"`, `"480"` | `"admit\n"` | `"within\n"` |
| Respective maximum plus one: `"74"` / `"481"` | `"reject\n"` | `"beyond\n"` |
| `"0"`, `"+0"`, `"-0"`, `"000"` | `"admit\n"` | `"beyond\n"` |
| `"+000120"` | `"reject\n"` | `"within\n"` |
| `"-00024"` | `"admit\n"` | `"beyond\n"` |
| `""`, `"+"`, `"-"` | `"malformed\n"` | `"invalid\n"` |
| `" 0"`, `"0 "`, `"0\n"`, `"\t0"` | `"malformed\n"` | `"invalid\n"` |
| `"1_20"`, `"1.0"`, `"1e2"`, `"++1"`, `"+-1"` | `"malformed\n"` | `"invalid\n"` |
| `"\u0661\u0662\u0660"`, `"\u22121"` | `"malformed\n"` | `"invalid\n"` |
| 64 ASCII nines; ASCII minus followed by 63 ASCII nines | `"reject\n"` | `"beyond\n"` |

## Timeout and Blocked Controls

Both timeout sources call `time.sleep(3)` before classification or output, then
perform the corresponding healthy classification. Their declared state is
`unknown`, never `pass` or `violation`. Use a predeclared per-product invocation
deadline below 3 seconds, for example 1 second, consistently for every variant.
That deadline is distinct from the selecting model's time budget.

| Case | Author witness | Policy stdout | Source-derived pre-deadline behavior | Eventual stdout without timeout |
| --- | --- | --- | --- | --- |
| signed-timeout | `"0"` | `"admit\n"` | No output before the sleep completes; unknown at the deadline | `"admit\n"` |
| positive-timeout | `"0"` | `"beyond\n"` | No output before the sleep completes; unknown at the deadline | `"beyond\n"` |

No runtime kill, exit code, elapsed time, or timeout handling was observed by
this author. A terminated invocation has no normal successful exit evidence;
do not manufacture exit code 0. The runtime must preserve its actual timeout
reason and any captured output. A deadline of 3 seconds or longer does not
reliably establish these controls and must not be accommodated by changing
their expected states or tuning their sources.

An upstream blocked launch or unavailable model may demonstrate only blocked
handling when that criterion is explicitly assessed. It does not establish
that either sleep executed, that a healthy product passed, or that seeded
defects were found. A correctly reported `unknown` is handling evidence only,
never behavioral acceptance.

## Hard Qualification Criteria

The main agent must review safety, verify the frozen hash, and run the held-out
qualification once without retuning. Qualification passes only when ALL of
the following are established by preserved run evidence:

- All 12 observed case states exactly match their declared expected states.
- Both healthy baselines pass with compliant stdout, exit code, and stderr on
  the frozen selected inputs: zero false alarms.
- All 8 defect cases are reported as violations with concrete selected-input
  counterexamples against the declarative oracle: zero missed defects and
  zero false passes. A defect reported as `unknown` is still a qualification failure.
- Both timeout controls are `unknown` with actual timeout evidence and no
  behavioral-pass credit. Unrelated blockage is not a timeout-control success.
- Selection exposure, input limits, distinctness, same-input reuse, and
  single-run discipline are evidenced. Empty, missing, malformed, stale,
  skipped, blocked, contradictory, or indeterminate required evidence is non-pass.

Preserve the exact selections, corpus hash, every case outcome, raw stdout and
stderr, exit or termination status, and timeout or block reasons, including
failures. Do not discard unsuccessful attempts or report only aggregate
accuracy. These criteria qualify this bounded fixture exercise only, not
universal correctness or arbitrary synthesized programs.

## Author Validation Record and Caveats

1. Confirmed the workspace with `pwd`, checked only the nonexistence of the two
   authorized paths, and located Node with `command -v node`.
2. Created the JSON once. Initial `node <<'NODE'` validator attempt failed before
   fixture evaluation with `SyntaxError: Invalid regular expression` / `Invalid
   group`: terminal transport turned a negative-lookahead `?!` into `?\!`.
   Node reported version v26.7.0. This failed attempt supplies no fixture evidence.
3. Replaced terminal-sensitive negation syntax with explicit full-match length
   checks in the validator command, without changing the JSON. Reran it:
   56/56 healthy example checks, 8/8 concrete defect witness checks, and 2/2
   timeout source checks passed; exact schema, identifier and label constraints,
   size limits, requirements-policy consistency, and the source safety shape
   checks passed. The computed hash is recorded above. Assertion failures: 0.
4. Stored the reproducible validator below and reran it from this document with
   a fixed-hash assertion. This remains static source-semantic validation.

No Python fixture was executed. No runtime stdout, stderr, exit status, Unicode
argv behavior, or actual deadline handling has been verified. The evaluator is
deliberately restricted to the exact authored source subset; it is not a Python
interpreter or general security analyzer. Its Unicode conversion models the
Arabic-Indic witness block only; its trimming model is exercised on the ASCII
space witness only. No broad equivalence of JavaScript and Python Unicode or
whitespace semantics is claimed. The baseline proof and explicit seed witnesses
are source-semantic evidence, not candidate qualification results. Runtime
qualification remains unverified and must not be called passed.

## Reproducible Static Check

Run from the repository root. This reads only the two author-created artifacts,
creates no files, launches no subprocesses, and runs neither Python nor Fettle:

```sh
node -e 'const fs=require("node:fs"); const text=fs.readFileSync("docs/uat/native-discovery-corpus-provenance.md","utf8"); const fence=String.fromCharCode(96).repeat(3); const code=text.split(fence+"javascript\n")[1].split("\n"+fence)[0]; new Function("require",code)(require);'
```

The script reports 56 baseline checks, 8 defect witness checks, 2 timeout source
checks, 0 assertion failures, and the exact corpus hash. Its witness output
explicitly labels results `sourceDerivedActual` and timeouts `runtimeVerified: false`.

```javascript
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');
const bytes = fs.readFileSync('evals/uat-native-discovery-heldout-2026-09-22.json');
const hash = crypto.createHash('sha256').update(bytes).digest('hex');
assert.equal(hash, '6067cee014a6e86dd529d630d687e1e730ba866e4a35d13903022ba3016d6b37');
const corpus = JSON.parse(bytes);
const exactKeys = (object, keys) => assert.deepEqual(Object.keys(object).sort(), keys.slice().sort());
const fullMatch = (regex, text) => { const match = regex.exec(text); return match && match[0] === text ? match : null; };
const idPattern = /^[a-z][a-z0-9-]{0,39}$/;
const labelPattern = /^[A-Za-z][A-Za-z0-9_-]{0,31}$/;
const sourceShape = /^import re\nimport sys\n(?<timeImport>import time\n)?\ntoken = sys\.argv\[1\](?<trim>\.strip\(\))?\n(?<sleep>time\.sleep\(3\)\n)?if re\.fullmatch\(r"(?<grammar>[^"\n]+)", token\) is None:\n    print\("(?<invalid>[A-Za-z][A-Za-z0-9_-]{0,31})"\)\nelse:\n(?:    value = (?<conversion>int\(token\)|abs\(int\(token\)\))\n)?    print\("(?<inside>[A-Za-z][A-Za-z0-9_-]{0,31})" if (?<condition>[^\n]+) else "(?<outside>[A-Za-z][A-Za-z0-9_-]{0,31})"\)\n$/u;
const validGrammars = new Set(['[+-]?[0-9]+', '[0-9]+', '[+-]?(?:0|[1-9][0-9]*)', '[+-]?\\d+']);
function policy(oracle, input) {
  if (fullMatch(/^[+-]?[0-9]+$/u, input) === null) return oracle.invalid + '\n';
  const value = BigInt(input);
  return (BigInt(oracle.minimum) <= value && value <= BigInt(oracle.maximum) ? oracle.inside : oracle.outside) + '\n';
}
function sourceModel(source) {
  const match = fullMatch(sourceShape, source);
  assert.ok(match, 'source must match the entire reviewed straight-line Python subset');
  const form = match.groups;
  assert.equal(Boolean(form.timeImport), Boolean(form.sleep));
  assert.ok(validGrammars.has(form.grammar));
  const numeric = fullMatch(/^(-?[0-9]+) (<|<=) value (<|<=) (-?[0-9]+)$/, form.condition);
  const textual = fullMatch(/^"([0-9]+)" <= token <= "([0-9]+)"$/, form.condition);
  assert.ok(numeric || textual);
  assert.equal(Boolean(form.conversion), Boolean(numeric));
  const grammar = new RegExp('^(?:' + form.grammar.replace('\\d', '\\p{Decimal_Number}') + ')$', 'u');
  return { form, evaluate(input) {
    if (form.sleep) return { state: 'unknown', reason: 'requires a product deadline below 3 seconds' };
    const token = form.trim ? input.trim() : input;
    if (fullMatch(grammar, token) === null) return { stdout: form.invalid + '\n', stderr: '', exit: 0 };
    let inside;
    if (textual) inside = textual[1] <= token && token <= textual[2];
    else {
      const normalized = token.replace(/[\u0660-\u0669]/gu, digit => String(digit.codePointAt(0) - 0x660));
      let value = BigInt(normalized);
      if (form.conversion === 'abs(int(token))' && value < 0n) value = -value;
      const lower = BigInt(numeric[1]);
      const upper = BigInt(numeric[4]);
      inside = (numeric[2] === '<' ? lower < value : lower <= value) && (numeric[3] === '<' ? value < upper : value <= upper);
    }
    return { stdout: (inside ? form.inside : form.outside) + '\n', stderr: '', exit: 0 };
  }};
}
const witnesses = {
  'signed-lower-open': ['-24', 'admit\n', 'reject\n'],
  'signed-upper-open': ['73', 'admit\n', 'reject\n'],
  'signed-unsigned-only': ['+0', 'admit\n', 'malformed\n'],
  'signed-trims-space': [' 0', 'malformed\n', 'admit\n'],
  'positive-no-leading-zero': ['0120', 'within\n', 'invalid\n'],
  'positive-unicode-digits': ['\u0661\u0662\u0660', 'invalid\n', 'within\n'],
  'positive-magnitude': ['-120', 'beyond\n', 'within\n'],
  'positive-text-order': ['2', 'beyond\n', 'within\n']
};
function requiredText(oracle) {
  return `The product is invoked as python app.py ARG with exactly one string argument. ARG is valid only when the entire string consists of an optional single ASCII plus sign (+) or ASCII minus sign (-), followed by one or more ASCII digits (0 through 9). No whitespace, separators, decimal points, other characters, or non-ASCII digits or signs are permitted. Leading zeros are allowed. Interpret valid strings as base-10 integers, with the sign applied to the value; signed zero is zero. For a valid integer in the inclusive range ${oracle.minimum} through ${oracle.maximum}, print ${oracle.inside}. For any other valid integer, print ${oracle.outside}. For any invalid string, print ${oracle.invalid}. In every case, stdout must contain exactly the specified lowercase word followed by one newline, the exit code must be 0, and stderr must be empty. No other output is permitted.`;
}
exactKeys(corpus, ['schema_version', 'suites']);
assert.equal(corpus.schema_version, 1); assert.equal(corpus.suites.length, 2);
assert.notDeepEqual(corpus.suites.map(suite => suite.oracle.minimum), [corpus.suites[0].oracle.minimum, corpus.suites[0].oracle.minimum]);
assert.equal(new Set(corpus.suites.flatMap(suite => [suite.oracle.inside, suite.oracle.outside, suite.oracle.invalid])).size, 6);
const ids = new Set();
let baselineChecks = 0; let witnessChecks = 0; let timeouts = 0;
for (const suite of corpus.suites) {
  exactKeys(suite, ['id', 'requirements', 'oracle', 'cases']);
  assert.ok(fullMatch(idPattern, suite.id)); assert.equal(ids.has(suite.id), false); ids.add(suite.id);
  assert.ok(Buffer.byteLength(suite.requirements, 'utf8') <= 8192);
  const oracle = suite.oracle;
  exactKeys(oracle, ['minimum', 'maximum', 'inside', 'outside', 'invalid']);
  for (const bound of [oracle.minimum, oracle.maximum]) assert.ok(Number.isInteger(bound) && Math.abs(bound) <= 1e9);
  assert.ok(oracle.minimum <= oracle.maximum);
  const labels = [oracle.inside, oracle.outside, oracle.invalid];
  assert.equal(new Set(labels).size, 3); labels.forEach(label => assert.ok(fullMatch(labelPattern, label)));
  assert.equal(suite.requirements, requiredText(oracle)); assert.equal(suite.cases.length, 6);
  assert.deepEqual(suite.cases.map(item => item.expected_state).sort(), ['pass', 'unknown', 'violation', 'violation', 'violation', 'violation']);
  for (const item of suite.cases) {
    exactKeys(item, ['id', 'source', 'expected_state']);
    assert.ok(fullMatch(idPattern, item.id)); assert.equal(ids.has(item.id), false); ids.add(item.id);
    assert.ok(Buffer.byteLength(item.source, 'utf8') <= 16384);
    const model = sourceModel(item.source);
    assert.deepEqual([model.form.inside, model.form.outside, model.form.invalid], labels);
    if (item.expected_state === 'pass') {
      assert.equal(model.form.grammar, '[+-]?[0-9]+'); assert.equal(model.form.conversion, 'int(token)');
      assert.equal(model.form.condition, `${oracle.minimum} <= value <= ${oracle.maximum}`);
      assert.equal(Boolean(model.form.trim || model.form.sleep), false);
      const inputs = [String(oracle.minimum - 1), String(oracle.minimum), String(oracle.minimum + 1), String(oracle.maximum - 1), String(oracle.maximum), String(oracle.maximum + 1), '', '+', '-', '0', '+0', '-0', '000', '+000120', '-00024', ' 0', '0 ', '0\n', '\t0', '1_20', '1.0', '1e2', '++1', '+-1', '\u0661\u0662\u0660', '\u22121', '9'.repeat(64), '-' + '9'.repeat(63)];
      for (const input of inputs) {
        assert.ok(Buffer.byteLength(input, 'utf8') <= 64); assert.equal(input.includes('\0'), false);
        assert.deepEqual(model.evaluate(input), { stdout: policy(oracle, input), stderr: '', exit: 0 }); baselineChecks++;
      }
      console.log(JSON.stringify({ case: item.id, staticBaselineChecks: inputs.length }));
    } else if (item.expected_state === 'violation') {
      const [input, expected, actual] = witnesses[item.id];
      assert.ok(Buffer.byteLength(input, 'utf8') <= 64); assert.equal(input.includes('\0'), false);
      assert.equal(policy(oracle, input), expected); assert.deepEqual(model.evaluate(input), { stdout: actual, stderr: '', exit: 0 });
      assert.notEqual(actual, expected); witnessChecks++;
      console.log(JSON.stringify({ case: item.id, input, expected, sourceDerivedActual: actual, exit: 0, stderr: '' }));
    } else {
      assert.ok(model.form.sleep);
      assert.deepEqual(model.evaluate('0'), { state: 'unknown', reason: 'requires a product deadline below 3 seconds' }); timeouts++;
      console.log(JSON.stringify({ case: item.id, sleepSeconds: 3, staticState: 'unknown', runtimeVerified: false }));
    }
  }
}
assert.equal(baselineChecks, 56); assert.equal(witnessChecks, 8); assert.equal(timeouts, 2);
console.log(JSON.stringify({ sha256: hash, suites: 2, cases: 12, baselineChecks, witnessChecks, timeoutSourceChecks: timeouts, failures: 0, method: 'static source-semantic validation; no Python or candidate execution' }));
```