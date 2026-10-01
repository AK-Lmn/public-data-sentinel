"""Small, offline data-contract checks for CSV and JSON extracts."""

from .validation import ContractError, validate

__all__ = ["ContractError", "validate"]
