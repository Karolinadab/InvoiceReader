from dataclasses import dataclass
from typing import Optional

@dataclass
class InvoiceItem:
    ordinal_number: Optional[int] = None  # Lp.
    name: Optional[str] = None            # Nazwa towaru lub usługi
    unit: Optional[str] = None            # Jm.
    quantity: Optional[int] = None        # Ilość
    unit_price_netto: Optional[float] = None   # Cena netto
    total_price_netto: Optional[float] = None  # Wartość netto
    tax_rate: Optional[float] = None           # Stawka VAT
    tax_amount: Optional[float] = None         # Kwota VAT
    total_price_gross: Optional[float] = None  # Wartość brutto