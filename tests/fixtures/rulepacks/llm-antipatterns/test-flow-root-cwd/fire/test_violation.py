"""FIRE fixture: cwd-relative mutation-flow root inside a test function."""


def test_uses_dot_root(tmp_path):
    result = run_mutation_test(".", {"paths": ["src/"]})
    assert result
