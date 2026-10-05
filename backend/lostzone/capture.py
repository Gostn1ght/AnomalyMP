"""Reject oversized abstract captures before parsing/assembling every state."""
from .store import Conflict


class CaptureBudget:
    def __init__(self, limit=1024*1024):
        self.remaining = limit

    def consume(self, encoded):
        # Reserve space for ID/version/type and nested JSON structure as well.
        self.remaining -= len(encoded.encode("utf-8"))+256
        if self.remaining < 0:
            raise Conflict("abstract state capture exceeds admission byte budget")
