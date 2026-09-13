"""Read Inspect evaluation logs into turn observations and utterances.

This is the loader behind the primary result. It streams samples so that only one is
in memory at a time, because an eval log with resolved attachments does not fit
comfortably otherwise.

Five things are extracted per sample, per spec §9.1: the reasoning state of every
assistant turn, the run's reasoning configuration, the task class, the tool calls, and
any inter-agent traffic. The last one has two code paths — `handoff()` agents append to
`EvalSample.messages`, while `as_tool()` agents surface only in `EvalSample.events` —
and reading only the first silently drops sub-agent traffic.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from channels.coverage import observe_turns
from channels.errors import CorpusUnavailableError, SchemaDiscoveryError
from channels.loaders.base import actor_concentration, file_hash
from channels.schema import (
    Channel,
    CorpusDescription,
    Provenance,
    TurnObservation,
    Utterance,
)

# Inspect writes both formats; a run directory may contain either.
LOG_SUFFIXES = (".eval", ".json")


@dataclass(frozen=True)
class ErroredSampleTally:
    """Samples whose `error` is set, split by whether they produced assistant turns."""

    with_turns: int      # errored samples that still contributed assistant turns
    turns: int           # the assistant turns those samples contributed
    without_turns: int   # errored samples that contributed no assistant turn


class InspectLogLoader:
    """Loads a directory of Inspect eval logs. One directory, many tasks and models."""

    name = "inspect_logs"

    def __init__(
        self,
        root: Path,
        name: str | None = None,
        licence: str | None = None,
        label_by_directory: bool = False,
    ) -> None:
        self.root = root
        # When one model is run under several CONFIGURATIONS - reasoning on vs
        # off, three reasoning_effort levels - the model id is no longer the
        # experimental condition, and grouping on it silently pools arms that
        # differ by exactly the variable under study. With this set, the arm
        # directory name becomes the label and the real model id moves to
        # corpus_meta. Caught on 2026-09-13 when Figure 1 showed one
        # "deepseek-v3.2" bar that was really the reasoning-on arm alone.
        self.label_by_directory = label_by_directory
        # A second directory of Inspect logs is a second CORPUS, not more rows of
        # the first: it has its own provenance, its own licence and its own source
        # hash. The step indices mean the same thing in both, so unlike Mythos they
        # could legitimately be pooled - but that must be a stated choice, not a
        # side effect of both landing in the same loader.
        if name is not None:
            self.name = name
        self.licence = licence or (
            "run artefacts of safety-eval-pipeline; MIT, same author"
        )

    def available(self) -> bool:
        """Whether any Inspect log file exists under the configured root."""
        return bool(self.log_paths())

    def errored_samples(self) -> int:
        """Return how many requested samples the log headers report as not completed.

        This is the header's arithmetic (total_samples - completed_samples), and it
        says nothing about turns: a sample can error after taking many turns, which
        are counted because they occurred (see `errored_sample_tally`). A header that
        cannot be read raises rather than being skipped, because skipping it would
        make the reported shortfall silently smaller than the real one.
        """
        from inspect_ai.log import read_eval_log

        total = 0
        for path in self.log_paths():
            try:
                header = read_eval_log(str(path), header_only=True)
            except Exception as error:
                raise CorpusUnavailableError(
                    f"could not read the header of {path} while counting errored "
                    f"samples: {error!r}"
                ) from error
            stats = getattr(header.results, "completed_samples", None)
            requested = getattr(header.results, "total_samples", None)
            if stats is not None and requested is not None:
                total += max(0, requested - stats)
        return total

    def incomplete_logs(self) -> list[Path]:
        """Logs whose run has not finished, and which are therefore excluded.

        A log still being written has fewer samples than the run will produce.
        Including it would silently shrink a denominator, which is the exact
        failure `emission.py` exists to prevent — so incomplete logs are skipped
        AND named in `describe()`, never quietly dropped.
        """
        from inspect_ai.log import read_eval_log

        incomplete: list[Path] = []
        for path in self._all_log_paths():
            try:
                status = read_eval_log(str(path), header_only=True).status
            except Exception:
                incomplete.append(path)
                continue
            if status != "success":
                incomplete.append(path)
        return incomplete

    def _all_log_paths(self) -> list[Path]:
        """Every Inspect log under the root, complete or not."""
        if not self.root.is_dir():
            return []
        found: list[Path] = []
        for suffix in LOG_SUFFIXES:
            found.extend(self.root.rglob(f"*{suffix}"))
        return sorted(found)

    def log_paths(self) -> list[Path]:
        """Every COMPLETE Inspect log under the root, sorted reproducibly."""
        excluded = set(self.incomplete_logs())
        return [path for path in self._all_log_paths() if path not in excluded]

    def require_available(self) -> list[Path]:
        """Return the log paths, or raise naming the exact path that was checked.

        Missing data is a result in this project. This raises rather than returning an
        empty list so that an empty corpus can never be mistaken for a measured zero.
        """
        paths = self.log_paths()
        if not paths:
            raise CorpusUnavailableError(
                f"no Inspect logs found under {self.root.resolve()} "
                f"(looked for {', '.join(LOG_SUFFIXES)}). "
                "Expected the logs/ directory of a safety-eval-pipeline run."
            )
        return paths

    def observations(self) -> Iterator[TurnObservation]:
        """Yield one TurnObservation per assistant turn across every log in the root."""
        for path in self.require_available():
            yield from self._observations_for_log(path)

    def load(self, **kwargs: Any) -> Iterator[Utterance]:
        """Yield utterances for the non-reasoning channels: tool calls and messages."""
        for path in self.require_available():
            yield from self._utterances_for_log(path)

    def errored_sample_tally(self) -> ErroredSampleTally:
        """Return errored samples split by whether they contributed assistant turns.

        The turns of an errored sample occurred and stay in every denominator; what
        must be reported is that they came from a sample that did not finish, and
        separately how many errored samples left no turn at all.
        """
        return self._observations_and_errors()[1]

    def _observations_and_errors(
        self,
    ) -> tuple[list[TurnObservation], ErroredSampleTally]:
        """Return every observation and the errored-sample tally from one read pass."""
        observations: list[TurnObservation] = []
        with_turns = turns = without_turns = 0
        for path in self.require_available():
            for sample, sample_observations in self._sample_observations(path):
                observations.extend(sample_observations)
                if not getattr(sample, "error", None):
                    continue
                with_turns += bool(sample_observations)
                without_turns += not sample_observations
                turns += len(sample_observations)
        return observations, ErroredSampleTally(with_turns, turns, without_turns)

    def describe(self) -> CorpusDescription:
        """Summarise the log directory, including which task classes it covers."""
        paths = self.require_available()
        observations, errored = self._observations_and_errors()
        samples = [o.sample_id for o in observations]
        task_classes = sorted({o.task_class for o in observations})
        return CorpusDescription(
            name=self.name,
            n_utterances=len(observations),
            n_actors=len({o.model for o in observations}),
            actor_concentration=actor_concentration(samples),
            date_range=None,
            source_hash=_combined_hash(paths),
            licence=self.licence,
            caveats=(
                f"task classes present: {task_classes}",
                f"{len(paths)} complete log file(s) under {self.root}",
                "one trajectory is one cluster; per-turn independence is false",
                f"reasoning_effort settings present: "
                f"{sorted({str(o.reasoning_effort) for o in observations})}",
                f"{len(self.incomplete_logs())} incomplete log(s) EXCLUDED "
                "(run not finished); their samples are absent from every "
                "denominator rather than partially counted",
                f"{errored.with_turns} errored sample(s) contributed "
                f"{errored.turns} assistant turn(s); those turns occurred and are "
                "counted in every denominator",
                f"{errored.without_turns} errored sample(s) contributed no "
                "assistant turn; they are absent from the denominator, not "
                "counted as emitting nothing",
                f"log headers report {self.errored_samples()} requested sample(s) "
                "not completed (total_samples - completed_samples)",
            ),
        )

    def _label_for(self, path: Path, model: str) -> str:
        """The grouping label: the arm directory, or the model id."""
        if self.label_by_directory and path.parent != self.root:
            return path.parent.name
        return model

    def _observations_for_log(self, path: Path) -> Iterator[TurnObservation]:
        """Stream one log file and classify every assistant turn it contains."""
        for _, sample_observations in self._sample_observations(path):
            yield from sample_observations

    def _sample_observations(
        self, path: Path
    ) -> Iterator[tuple[Any, list[TurnObservation]]]:
        """Stream one log file, yielding each sample with its classified turns."""
        from inspect_ai.log import read_eval_log, read_eval_log_samples

        header = read_eval_log(str(path), header_only=True)
        model = self._label_for(path, _model_of(header, path))
        task_class = _task_class_of(header, path)
        effort = _reasoning_effort_of(header)
        for sample in read_eval_log_samples(str(path), resolve_attachments=True):
            yield sample, observe_turns(sample, model, task_class, effort)

    def _utterances_for_log(self, path: Path) -> Iterator[Utterance]:
        """Stream one log file and emit tool calls and inter-agent messages."""
        from inspect_ai.log import read_eval_log, read_eval_log_samples

        header = read_eval_log(str(path), header_only=True)
        model = self._label_for(path, _model_of(header, path))
        task_class = _task_class_of(header, path)
        for sample in read_eval_log_samples(str(path), resolve_attachments=True):
            yield from sample_utterances(sample, model, task_class, self.name)


def sample_utterances(
    sample: Any, model: str, task_class: str, corpus: str
) -> Iterator[Utterance]:
    """Emit tool-call and inter-agent utterances for one sample.

    Tool calls are behavioural evidence independent of any text channel, which is why
    they are extracted even though the primary result is about reasoning: they are what
    remains observable when the reasoning channel is empty.
    """
    sample_id = str(getattr(sample, "id", "unknown"))
    step_index = 0
    for message in getattr(sample, "messages", []) or []:
        role = getattr(message, "role", None)
        if role != "assistant":
            continue
        for position, call in enumerate(getattr(message, "tool_calls", None) or []):
            yield Utterance(
                uid=f"{corpus}:{sample_id}:{step_index}:tool:{position}",
                corpus=corpus,
                channel=Channel.TOOL_CALL,
                provenance=Provenance.VERBATIM,
                text=getattr(call, "function", None),
                actor=model,
                thread_id=sample_id,
                seq=step_index,
                step_index=step_index,
                model=model,
                task_class=task_class,
                corpus_meta={
                    "tool_call_id": getattr(call, "id", None),
                    "parse_error": getattr(call, "parse_error", None),
                },
            )
        step_index += 1
    yield from _subagent_utterances(sample, model, task_class, corpus, sample_id)


def _subagent_utterances(
    sample: Any, model: str, task_class: str, corpus: str, sample_id: str
) -> Iterator[Utterance]:
    """Emit inter-agent traffic that appears only as events, not as messages.

    `as_tool()` sub-agents never reach `EvalSample.messages`; they surface as
    SubtaskEvent plus span events. Reading only the message list drops them silently,
    which would understate the inter-agent channel by exactly the traffic that is
    hardest to oversee.
    """
    for position, event in enumerate(getattr(sample, "events", []) or []):
        if getattr(event, "event", None) != "subtask":
            continue
        yield Utterance(
            uid=f"{corpus}:{sample_id}:event:{position}",
            corpus=corpus,
            channel=Channel.INTER_AGENT_MESSAGE,
            provenance=Provenance.VERBATIM,
            text=None,  # withheld here; counts as uninspectable, not dropped
            actor=str(getattr(event, "name", None) or model),
            thread_id=sample_id,
            seq=position,
            model=model,
            task_class=task_class,
            corpus_meta={"event_type": "subtask"},
        )


def _model_of(header: Any, path: Path) -> str:
    """Return the model identifier from the log header, raising when it is absent.

    An "unknown_model" label would become a cell, a bar and a gate stratum of its
    own, and a rate for an unnamed model cannot be attributed to anything.
    """
    model = getattr(getattr(header, "eval", None), "model", None)
    if not model:
        raise SchemaDiscoveryError(_missing_header_field(header, path, "model"))
    return str(model)


def _task_class_of(header: Any, path: Path) -> str:
    """Return the task class from the log's task name, raising when it is absent.

    Required rather than optional: the reporting-unit argument is that a rate without
    a task class is not interpretable, so a log that cannot name one is a problem to
    surface, not a default to fill in.
    """
    task = getattr(getattr(header, "eval", None), "task", None)
    if not task:
        raise SchemaDiscoveryError(_missing_header_field(header, path, "task"))
    # Inspect prefixes registry tasks, e.g. "inspect_evals/sycophancy".
    return str(task).rsplit("/", maxsplit=1)[-1]


def _missing_header_field(header: Any, path: Path, field: str) -> str:
    """The error message for a header lacking `eval.<field>`, with the keys seen."""
    spec = getattr(header, "eval", None)
    seen = _keys_of(spec) if spec is not None else _keys_of(header)
    where = "eval" if spec is not None else "header (no eval block)"
    return (
        f"{path}: log header has no eval.{field}; expected it on every Inspect log. "
        f"Keys seen on {where}: {seen}"
    )


def _keys_of(obj: Any) -> list[str]:
    """Field names present on a header object, pydantic or plain."""
    fields = getattr(type(obj), "model_fields", None)
    if isinstance(fields, dict):
        return sorted(name for name in fields if getattr(obj, name, None) is not None)
    return sorted(key for key, value in vars(obj).items() if value is not None)


def _reasoning_effort_of(header: Any) -> str | None:
    """Reasoning effort from the eval spec's model generate config, if the run set one.

    None means the run did not set it, which is different from setting it to a low
    value, and the two must not collapse into the same cell.
    """
    spec = getattr(header, "eval", None)
    config = getattr(spec, "model_generate_config", None)
    effort = getattr(config, "reasoning_effort", None)
    return str(effort) if effort else None


def _combined_hash(paths: Sequence[Path]) -> str:
    """One hash over several log files, order-independent via sorted member hashes."""
    import hashlib

    digest = hashlib.sha256()
    for member in sorted(file_hash(path) for path in paths):
        digest.update(member.encode())
    return f"sha256:{digest.hexdigest()}"
