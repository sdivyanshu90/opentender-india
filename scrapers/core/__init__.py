"""Core ingestion framework: adapters, normalization, storage, health."""

from scrapers.core.adapter import AdapterMeta, TenderSourceAdapter
from scrapers.core.models import CanonicalTender, TenderDocument

__all__ = ["CanonicalTender", "TenderDocument", "AdapterMeta", "TenderSourceAdapter"]
