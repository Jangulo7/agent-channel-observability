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
from pathlib import Path
from typing import Any

from channels.coverage import observe_turns
from channels.errors import CorpusUnavailableError
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


class InspectLogLoader:
    """Loads a directory of Inspect eval logs. One directory, many tasks and models."""

    name = "inspect_logs"

    def __init__(
        self,
        root: Path,
        name: str | None = None,
        licence: str | None = None,
    ) -> None:
        self.root = root
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

    def describe(self) -> CorpusDescription:
        """Summarise the log directory, including which task classes it covers."""
        paths = self.require_available()
        observations = list(self.observations())
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
            ),
        )

    def _observations_for_log(self, path: Path) -> Iterator[TurnObservation]:
        """Stream one log file and classify every assistant turn it contains."""
        from inspect_ai.log import read_eval_log, read_eval_log_samples

        header = read_eval_log(str(path), header_only=True)
        model = _model_of(header)
        task_class = _task_class_of(header)
        effort = _reasoning_effort_of(header)
        for sample in read_eval_log_samples(str(path), resolve_attachments=True):
            yield from observe_turns(sample, model, task_class, effort)

    def _utterances_for_log(self, path: Path) -> Iterator[Utterance]:
        """Stream one log file and emit tool calls and inter-agent messages."""
        from inspect_ai.log import read_eval_log, read_eval_log_samples

        header = read_eval_log(str(path), header_only=True)
        model = _model_of(header)
        task_class = _task_class_of(header)
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


def _model_of(header: Any) -> str:
    """Model identifier from the log header, or an explicit unknown marker."""
    spec = getattr(header, "eval", None)
    return str(getattr(spec, "model", None) or "unknown_model")


def _task_class_of(header: Any) -> str:
    """Task class from the log's task name.

    Required rather than optional: the reporting-unit argument is that a rate without
    a task class is not interpretable, so a log that cannot name one is a problem to
    surface, not a default to fill in.
    """
    spec = getattr(header, "eval", None)
    task = getattr(spec, "task", None)
    if not task:
        return "unknown_task_class"
    # Inspect prefixes registry tasks, e.g. "inspect_evals/sycophancy".
    return str(task).rsplit("/", maxsplit=1)[-1]


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
