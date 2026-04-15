from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DiscoveredField:
    """A label:value pair found in the document."""
    label: str
    value: str
    line_index: int = 0
    confidence: float = 1.0
    source: str = "label_value"


@dataclass
class TaxIdHit:
    """A CIF/NIF found in the document with its position."""
    tax_id: str
    line_index: int
    nearby_name: str = ""


@dataclass
class NumericCandidate:
    """A number found in the document with its context."""
    value: float
    label: str = ""
    line_index: int = 0


@dataclass
class TableRow:
    """A row from a detected table."""
    description: str = ""
    quantity: float = 0
    unit_price: float = 0
    amount: float = 0
    raw_text: str = ""


@dataclass
class ScanResult:
    """Output of field_scanner: all structured data found in the document."""
    fields: list[DiscoveredField] = field(default_factory=list)
    tax_ids: list[TaxIdHit] = field(default_factory=list)
    amounts: list[NumericCandidate] = field(default_factory=list)
    table_rows: list[TableRow] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    raw_text: str = ""
