"""Published constants must carry their provenance."""

from channels import priors


def test_priors_have_sources() -> None:
    tables = (
        priors.AISI_DELIBERATION_COVERAGE,
        priors.ADAPTTHINK_TASK_SPREAD,
    )
    for table in tables:
        for key, rate in table.items():
            assert rate.source, f"{key} has no source"


def test_priors_are_probabilities() -> None:
    for table in (priors.AISI_DELIBERATION_COVERAGE, priors.ADAPTTHINK_TASK_SPREAD):
        for key, rate in table.items():
            assert 0.0 <= rate.value <= 1.0, key
    for step, value in priors.ADAPTR1_STEP_PROFILE.items():
        assert 0.0 <= value <= 1.0, step


def test_priors_module_has_no_side_effects() -> None:
    """priors.py must be importable without doing anything; it is constants only."""
    import ast
    from pathlib import Path

    source = Path(priors.__file__).read_text()
    tree = ast.parse(source)
    for node in tree.body:
        assert isinstance(
            node, ast.Import | ast.ImportFrom | ast.Assign | ast.ClassDef | ast.Expr
        ), f"priors.py contains executable logic: {type(node).__name__}"
