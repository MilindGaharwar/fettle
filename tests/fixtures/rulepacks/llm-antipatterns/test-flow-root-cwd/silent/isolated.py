"""SILENT fixture: isolated roots and non-test callers stay unflagged."""


def test_isolated(tmp_path):
    result = run_mutation_test(str(tmp_path), {"paths": ["src/"]})
    assert result


def cmd_mutation(args):
    return run_mutation_test(".", {"paths": args.paths})
