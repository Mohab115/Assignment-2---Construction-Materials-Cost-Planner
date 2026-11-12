"""
Module 1 - Material Quantity Calculator
=======================================

Defines a :class:`ConcreteElement` (one concrete element on a site) and an
:class:`ElementManager` that lets the user add, list, search and update
elements, computes concrete volumes and the required cement / sand / aggregate
quantities, and saves everything to CSV.

Assumed mix rates, per 1 m3 of concrete INCLUDING waste:
    cement    = 300 kg
    sand      = 0.5 m3
    aggregate = 0.8 m3
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field

# --- Assumed training mix rates per cubic metre (including waste) -------------
CEMENT_KG_PER_M3 = 300.0
SAND_M3_PER_M3 = 0.5
AGGREGATE_M3_PER_M3 = 0.8

# Units used throughout the whole application, keyed by material. Keeping them
# in one place guarantees Module 1 and Module 2 stay consistent.
MATERIAL_UNITS = {"Cement": "kg", "Sand": "m3", "Aggregate": "m3"}


class ValidationError(ValueError):
    """Raised when an element fails an input-validation rule."""


@dataclass
class ConcreteElement:
    """A single concrete element and its derived material quantities."""

    element_id: str
    element_name: str
    site: str
    length_m: float
    width_m: float
    height_m: float
    waste_pct: float

    def __post_init__(self) -> None:
        # Normalise text fields and validate numeric ones on creation.
        self.element_id = str(self.element_id).strip()
        self.element_name = str(self.element_name).strip()
        self.site = str(self.site).strip()
        self.length_m = float(self.length_m)
        self.width_m = float(self.width_m)
        self.height_m = float(self.height_m)
        self.waste_pct = float(self.waste_pct)
        self.validate()

    # --- Validation ----------------------------------------------------------
    def validate(self) -> None:
        """Dimensions must be > 0 and waste must be within [0, 100]."""
        for field_name in ("length_m", "width_m", "height_m"):
            if getattr(self, field_name) <= 0:
                raise ValidationError(
                    f"{field_name} must be greater than zero "
                    f"(got {getattr(self, field_name)})."
                )
        if not 0 <= self.waste_pct <= 100:
            raise ValidationError(
                f"waste_pct must be between 0 and 100 (got {self.waste_pct})."
            )

    # --- Derived quantities (computed on demand) -----------------------------
    @property
    def net_volume(self) -> float:
        """Net volume in m3 = length x width x height."""
        return self.length_m * self.width_m * self.height_m

    @property
    def volume_with_waste(self) -> float:
        """Volume in m3 including waste = net volume x (1 + waste / 100)."""
        return self.net_volume * (1 + self.waste_pct / 100.0)

    @property
    def cement_kg(self) -> float:
        return self.volume_with_waste * CEMENT_KG_PER_M3

    @property
    def sand_m3(self) -> float:
        return self.volume_with_waste * SAND_M3_PER_M3

    @property
    def aggregate_m3(self) -> float:
        return self.volume_with_waste * AGGREGATE_M3_PER_M3

    def quantities(self) -> dict:
        """Return a flat dict of the element plus all computed quantities."""
        return {
            "element_id": self.element_id,
            "element_name": self.element_name,
            "site": self.site,
            "length_m": self.length_m,
            "width_m": self.width_m,
            "height_m": self.height_m,
            "waste_pct": self.waste_pct,
            "net_volume_m3": round(self.net_volume, 4),
            "volume_with_waste_m3": round(self.volume_with_waste, 4),
            "cement_kg": round(self.cement_kg, 4),
            "sand_m3": round(self.sand_m3, 4),
            "aggregate_m3": round(self.aggregate_m3, 4),
        }


class ElementManager:
    """In-memory collection of elements with add / list / search / update."""

    # Column order used when persisting the raw element definitions.
    BASE_FIELDS = (
        "element_id",
        "element_name",
        "site",
        "length_m",
        "width_m",
        "height_m",
        "waste_pct",
    )

    def __init__(self) -> None:
        # dict keyed by element_id gives O(1) duplicate checks and look-ups.
        self._elements: dict[str, ConcreteElement] = {}

    # --- Create --------------------------------------------------------------
    def add(self, element: ConcreteElement) -> ConcreteElement:
        """Add a new element, rejecting duplicate IDs."""
        if element.element_id in self._elements:
            raise ValidationError(
                f"Duplicate element_id '{element.element_id}' - rejected."
            )
        self._elements[element.element_id] = element
        return element

    def add_from_values(self, **kwargs) -> ConcreteElement:
        """Convenience: build a ConcreteElement from raw values and add it."""
        return self.add(ConcreteElement(**kwargs))

    # --- Read ----------------------------------------------------------------
    def list_elements(self) -> list[ConcreteElement]:
        """Return all elements sorted by ID (stable, predictable order)."""
        return [self._elements[k] for k in sorted(self._elements)]

    def search(self, term: str) -> list[ConcreteElement]:
        """Find elements by exact ID or by case-insensitive name substring."""
        term = str(term).strip()
        if term in self._elements:
            return [self._elements[term]]
        term_low = term.lower()
        return [
            el
            for el in self.list_elements()
            if term_low in el.element_name.lower()
        ]

    def get(self, element_id: str) -> ConcreteElement | None:
        return self._elements.get(str(element_id).strip())

    @property
    def sites(self) -> set[str]:
        """Unique set of sites across all elements."""
        return {el.site for el in self._elements.values()}

    # --- Update --------------------------------------------------------------
    def update(self, element_id: str, **changes) -> ConcreteElement:
        """Update fields of an existing element; unknown IDs are rejected."""
        element = self.get(element_id)
        if element is None:
            raise ValidationError(
                f"Unknown element_id '{element_id}' - cannot update."
            )
        allowed = set(self.BASE_FIELDS) - {"element_id"}
        for key, value in changes.items():
            if key not in allowed:
                raise ValidationError(f"Field '{key}' is not updatable.")
            setattr(element, key, value)
        element.__post_init__()  # re-normalise and re-validate after changes
        return element

    # --- Persistence ---------------------------------------------------------
    def save_elements_csv(self, path: str) -> str:
        """Save the raw element definitions."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(self.BASE_FIELDS))
            writer.writeheader()
            for el in self.list_elements():
                writer.writerow({k: getattr(el, k) for k in self.BASE_FIELDS})
        return path

    def save_quantities_csv(self, path: str) -> str:
        """Save the elements together with all calculated quantities."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        rows = [el.quantities() for el in self.list_elements()]
        fieldnames = list(rows[0].keys()) if rows else list(self.BASE_FIELDS)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def required_by_site(self) -> dict[str, dict[str, float]]:
        """Aggregate required quantities per site (cement/sand/aggregate)."""
        totals: dict[str, dict[str, float]] = {}
        for el in self.list_elements():
            site = totals.setdefault(
                el.site, {"Cement": 0.0, "Sand": 0.0, "Aggregate": 0.0}
            )
            site["Cement"] += el.cement_kg
            site["Sand"] += el.sand_m3
            site["Aggregate"] += el.aggregate_m3
        return totals


# --- Loading helpers ---------------------------------------------------------
def load_elements_csv(path: str) -> ElementManager:
    """Build an :class:`ElementManager` from an elements CSV file."""
    manager = ElementManager()
    with open(path, newline="", encoding="utf-8") as fh:
        for line_no, row in enumerate(csv.DictReader(fh), start=2):
            try:
                manager.add_from_values(
                    element_id=row["element_id"],
                    element_name=row["element_name"],
                    site=row["site"],
                    length_m=row["length_m"],
                    width_m=row["width_m"],
                    height_m=row["height_m"],
                    waste_pct=row["waste_pct"],
                )
            except ValidationError as exc:
                print(f"  [skip] line {line_no}: {exc}")
    return manager


if __name__ == "__main__":
    # Quick smoke test when run directly.
    mgr = load_elements_csv(os.path.join("data", "elements.csv"))
    print(f"Loaded {len(mgr.list_elements())} elements across sites {mgr.sites}")
    for e in mgr.list_elements():
        q = e.quantities()
        print(
            f"  {q['element_id']} {q['element_name']:<12} "
            f"vol(waste)={q['volume_with_waste_m3']:>8} m3  "
            f"cement={q['cement_kg']:>9} kg"
        )
