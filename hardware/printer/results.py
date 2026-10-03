"""Transport outcome without claiming that spool acceptance proves paper."""

from dataclasses import dataclass


class PrintFailure(Exception):
    """Known failure before any document was submitted to the spooler."""


@dataclass(frozen=True)
class PrintResult:
    status: str
    message: str
    spooler_job_id: int | None = None
