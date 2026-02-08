
from dataclasses import dataclass, field
from datetime import date
from typing import List, cast

from app.services.company import Company
from app.services.invoice_item import InvoiceItem

@dataclass
class Invoice:
    place_of_issue: str | None = None
    date_of_issue: date | None = None
    date_of_sale: date | None = None
    buyer: Company | None = None
    seller: Company | None = None

    name: str | None = None

    items: List[InvoiceItem] = field(default_factory=lambda: cast(List[InvoiceItem], []))
    
    total_amount: float | None = None
    total_amount_words: str | None = None
    currency: str | None = None
    account_number: str | None = None
    payment_due_date: date | None = None
    payment_method: str | None = None
