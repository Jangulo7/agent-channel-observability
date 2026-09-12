"""Custom exceptions. Every message names the offending value and what was expected.

Missing data is a result in this project, not an inconvenience to be routed around.
These types exist so that a missing actor, an unvalidated detector or an absent
corpus surfaces loudly instead of quietly degrading into a smaller denominator.
"""


class ChannelsError(Exception):
    """Base class for every error this package raises."""


class MissingActorError(ChannelsError):
    """Raised when a clustered computation must pool observations lacking an actor.

    Pooling would silently assume independence across observations that are not
    independent, which is exactly the inference error `cluster.py` exists to prevent.
    """


class ProvenanceError(ChannelsError):
    """Raised when utterances ineligible for a confirmatory endpoint reach one."""


class SchemaDiscoveryError(ChannelsError):
    """Raised when a corpus lacks a required field; lists the keys actually seen."""


class UnvalidatedDetectorError(ChannelsError):
    """Raised when a detector with no validation record tries to report a rate."""


class CorpusUnavailableError(ChannelsError):
    """Raised when a loader finds no data. The paths checked belong in the message."""


class InvalidRateError(ChannelsError):
    """Raised when a probability argument falls outside [0, 1]."""
