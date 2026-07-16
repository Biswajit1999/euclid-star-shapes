class ProjectError(RuntimeError):
    """Base exception for actionable project failures."""


class DataSchemaError(ProjectError):
    """Raised when an input product does not match the documented schema."""


class ProvenanceError(ProjectError):
    """Raised when required provenance metadata are absent or inconsistent."""


class ArchiveAccessError(ProjectError):
    """Raised when an archive query or download cannot be completed or verified."""


class ConvergenceError(ProjectError):
    """Raised when a numerical fit or iterative method fails to converge."""


class InsufficientDataError(ProjectError):
    """Raised when a sample is too small or too degenerate to report a metric."""
