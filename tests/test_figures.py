"""Figures render, and their captions carry the numbers a reader needs."""

from pathlib import Path

from channels.emission import MIN_CELL_N, binned_profile, build_cells
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
    profile = binned_profile(cells, n_bins=2)
    path, caption = figure_two(profile, tmp_path / "fig2.png")
    assert path.is_file()
    assert "n = " in caption
    assert "INDUCED" in caption


def test_figure_two_caption_warns_on_a_single_cluster(tmp_path: Path) -> None:
    """One trajectory means the interval is descriptive, and the caption must say so."""
    cells = build_cells(turns([RAW, ABSENT] * 20, sample_id="SYNTHETIC_ONLY"))
    profile = binned_profile(cells, n_bins=2)
    _, caption = figure_two(profile, tmp_path / "fig2.png")
    assert "n_clusters = 1" in caption
    assert "descriptive, not inferential" in caption


def test_figure_two_states_the_worst_position(tmp_path: Path) -> None:
    cells = build_cells(_many_turns(MIN_CELL_N))
    profile = binned_profile(cells, n_bins=2)
    _, caption = figure_two(profile, tmp_path / "fig2.png")
    assert "lowest at position" in caption
