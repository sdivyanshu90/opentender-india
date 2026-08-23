"""Source adapter registry package."""

from scrapers.adapters.gem import GemAdapter
from scrapers.adapters.gepnic import GePNICAdapter
from scrapers.adapters.ireps_works import IrepsWorksAdapter

__all__ = ["GePNICAdapter", "GemAdapter", "IrepsWorksAdapter"]
