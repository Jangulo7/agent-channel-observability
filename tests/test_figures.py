"""Figures render, and their captions carry the numbers a reader needs."""

from pathlib import Path

from channels.emission import MIN_CELL_N, arm_profiles, binned_profile, build_cells
from channels.figures import figure_one, figure_two
from channels.schema import ReasoningState

from .fixtures.synthetic import turns

RAW = ReasoningState.RAW_PRESENT
ABSENT = ReasoningState.ABSENT


def _many_turns(n: int) -> list:
    observations = []
    for index in range(n):
        observations.extend(turns([RAW, ABSENT], sample_id=f"SYNTHETIC_{index}"))
    return observations


def test_figure_one_writes_a_file_and_states_n(tmp_path: Path) -> None:
    cells = build_cells(_many_turns(MIN_CELL_N))
    path, caption = figure_one(cells, tmp_path / "fig1.png")
    assert path.is_file()
    assert path.stat().st_size > 0
    assert f"n={2 * MIN_CELL_N}" in caption
    assert "raw_present" in caption
    assert "denominator" in caption.lower()


def test_figure_one_caption_names_excluded_low_n_cells(tmp_path: Path) -> None:
    """A low-n cell leaves the plot but must not leave the record."""
    cells = build_cells(
        _many_turns(MIN_CELL_N)
        + turns([RAW], model="SYNTHETIC-MODEL-TINY", sample_id="SYNTHETIC_TINY")
    )
    _, caption = figure_one(cells, tmp_path / "fig1.png")
    assert "SYNTHETIC-MODEL-TINY" in caption
    assert f"n < {MIN_CELL_N}" in caption


def test_figure_two_writes_a_file_and_states_n(tmp_path: Path) -> None:
    cells = build_cells(_many_turns(MIN_CELL_N))
    (profile,) = arm_profiles(cells, n_bins=2)
    path, caption = figure_two(profile, tmp_path / "fig2.png")
    assert path.is_file()
    assert "n = " in caption
    assert "INDUCED" in caption


def test_figure_two_caption_warns_on_a_single_cluster(tmp_path: Path) -> None:
    """One trajectory means the interval is descriptive, and the caption must say so."""
    cells = build_cells(turns([RAW, ABSENT] * 20, sample_id="SYNTHETIC_ONLY"))
    (profile,) = arm_profiles(cells, n_bins=2)
    _, caption = figure_two(profile, tmp_path / "fig2.png")
    assert "n_clusters = 1" in caption
    assert "descriptive, not inferential" in caption


def test_figure_two_states_the_worst_position(tmp_path: Path) -> None:
    cells = build_cells(_many_turns(MIN_CELL_N))
    (profile,) = arm_profiles(cells, n_bins=2)
    _, caption = figure_two(profile, tmp_path / "fig2.png")
    assert "lowest at position" in caption


def _model_task_turns(
    model: str, task: str, state: ReasoningState, n: int
) -> list:
    """n single-turn synthetic samples for one model and task class."""
    observations = []
    for index in range(n):
        observations.extend(
            turns([state], model=model, task_class=task,
                  sample_id=f"SYNTHETIC_{model}_{task}_{index}")
        )
    return observations


def test_task_class_spread_detects_within_model_variation() -> None:
    """The check that decides whether pooling task classes is honest."""
    from channels.figures import task_class_spread

    flat = build_cells(
        _model_task_turns("SYNTHETIC-FLAT", "task_a", RAW, MIN_CELL_N)
        + _model_task_turns("SYNTHETIC-FLAT", "task_b", RAW, MIN_CELL_N)
    )
    assert task_class_spread(flat)["SYNTHETIC-FLAT"] == 0.0

    varying = build_cells(
        _model_task_turns("SYNTHETIC-VARY", "task_a", RAW, MIN_CELL_N)
        + _model_task_turns("SYNTHETIC-VARY", "task_b", ABSENT, MIN_CELL_N)
    )
    assert task_class_spread(varying)["SYNTHETIC-VARY"] == 1.0


def test_figure_one_can_pool_task_classes(tmp_path: Path) -> None:
    """by_task=False gives one bar per model, and the caption says so."""
    cells = build_cells(
        _model_task_turns("SYNTHETIC-POOL", "task_a", RAW, MIN_CELL_N)
        + _model_task_turns("SYNTHETIC-POOL", "task_b", RAW, MIN_CELL_N)
    )
    path, caption = figure_one(cells, tmp_path / "f1_pooled.png", by_task=False)
    assert path.is_file()
    assert "all task classes" in caption
    assert f"n={2 * MIN_CELL_N}" in caption


def test_positional_figures_are_written_per_arm(tmp_path: Path) -> None:
    """c(j) must not average arms whose profiles differ.

    Found by reading a generated caption: the agentic corpus pooled a
    raw-emitting arm with a fully-redacted one and reported "lowest at position
    2 (0.490)" - a number belonging to no arm that was run. A profile averaged
    across arms describes neither.
    """
    from channels.figures import figure_two

    readable = _model_task_turns("SYNTHETIC-READS", "t", RAW, MIN_CELL_N)
    withheld = _model_task_turns("SYNTHETIC-HIDES", "t", ABSENT, MIN_CELL_N)

    for arm, obs in (("READS", readable), ("HIDES", withheld)):
        (profile,) = arm_profiles(build_cells(obs), n_bins=2)
        path, caption = figure_two(profile, tmp_path / f"f2_{arm}.png")
        assert path.is_file()
        # Each arm's caption states its own coverage, not a blended one.
        assert ("1.000" in caption) if arm == "READS" else ("0.000" in caption)

    pooled = binned_profile(build_cells(readable + withheld), n_bins=2)
    pooled_rate = next(iter(pooled.values())).rate
    assert pooled_rate is not None
    # The pooled profile sits between the two and describes neither.
    assert 0.0 < pooled_rate < 1.0


def test_figure_two_plots_steps_and_names_low_n_positions(tmp_path: Path) -> None:
    """A multi-trajectory arm is drawn per step; thin steps are named, not ranked.

    30 trajectories reach step 0 (all readable) and step 1 (none readable); only 2
    reach step 2 (readable). The lowest powered position is step 1, and step 2 is
    named as low-n.
    """
    observations = [
        obs
        for index in range(MIN_CELL_N)
        for obs in turns(
            [RAW, ABSENT, RAW] if index < 2 else [RAW, ABSENT],
            sample_id=f"SYNTHETIC_{index}",
        )
    ]
    (profile,) = arm_profiles(build_cells(observations))
    assert profile.unit == "step"
    _, caption = figure_two(profile, tmp_path / "fig2.png")
    assert "per step index" in caption
    assert "Among powered positions" in caption
    assert "lowest at position 1 (0.000" in caption
    assert "2 (n = 2)" in caption
    assert "hollow grey" in caption


def test_figure_two_never_ranks_a_low_n_minimum(tmp_path: Path) -> None:
    """A low-n step with the lowest rate must not become the reported worst step."""
    observations = [
        obs
        for index in range(MIN_CELL_N)
        for obs in turns(
            [RAW, RAW, ABSENT] if index < 3 else [RAW, RAW],
            sample_id=f"SYNTHETIC_{index}",
        )
    ]
    (profile,) = arm_profiles(build_cells(observations))
    _, caption = figure_two(profile, tmp_path / "fig2.png")
    assert "lowest at position 0 (1.000" in caption
    assert "lowest at position 2" not in caption


def test_figure_two_single_trajectory_is_captioned_as_bins(tmp_path: Path) -> None:
    (profile,) = arm_profiles(
        build_cells(turns([RAW, ABSENT] * 20, sample_id="SYNTHETIC_ONLY")), n_bins=4
    )
    _, caption = figure_two(profile, tmp_path / "fig2.png")
    assert "equal-width bins of 10 steps" in caption
    assert "no interval is drawn" in caption


def test_adaptr1_is_plotted_as_a_thinking_share() -> None:
    """The published value is a no-think ratio; the figure plots its complement."""
    from channels.figures import adaptr1_thinking_share
    from channels.priors import ADAPTR1_STEP_PROFILE

    share = adaptr1_thinking_share()
    assert share.keys() == ADAPTR1_STEP_PROFILE.keys()
    for step, ratio in ADAPTR1_STEP_PROFILE.items():
        assert share[step] == 1.0 - ratio


def test_figure_two_caption_labels_the_adaptr1_transformation(tmp_path: Path) -> None:
    (profile,) = arm_profiles(build_cells(_many_turns(MIN_CELL_N)))
    _, caption = figure_two(profile, tmp_path / "fig2.png")
    assert "TRANSFORMATION of a published value" in caption
    assert "induced by RL objective, not observed" in caption


def test_figure_one_intervals_are_clustered_by_trajectory(tmp_path: Path) -> None:
    """Pooled over steps, turns are not independent: the interval says so."""
    cells = build_cells(
        _many_turns(MIN_CELL_N)
        + turns([RAW, ABSENT] * 20, model="SYNTHETIC-ONE-TRAJ", sample_id="SYN_ONE")
    )
    _, caption = figure_one(cells, tmp_path / "fig1.png")
    assert "clustered by trajectory" in caption
    assert f"{MIN_CELL_N} trajectories" in caption
    assert "status single_cluster_no_interval" in caption
