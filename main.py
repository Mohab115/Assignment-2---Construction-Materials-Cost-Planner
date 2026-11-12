"""
main.py - Construction Materials Cost Planner
=============================================

Connects Module 1 (material_calculator) and Module 2 (cost_analysis) through a
simple text menu.

Run:
    python main.py
"""

from __future__ import annotations

import os

from material_calculator import (
    ConcreteElement,
    ElementManager,
    ValidationError,
    load_elements_csv,
)
import cost_analysis as ca

# --- Paths (resolved relative to this file so it runs from any folder) --------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")

ELEMENTS_CSV = os.path.join(DATA_DIR, "elements.csv")
PRICES_CSV = os.path.join(DATA_DIR, "prices.csv")
PURCHASES_CSV = os.path.join(DATA_DIR, "purchases.csv")

# Menu is a tuple of (key, label) tuples - immutable, ordered.
MENU = (
    ("1", "Add element"),
    ("2", "List elements and quantities"),
    ("3", "Search element"),
    ("4", "Update element"),
    ("5", "Save elements and quantities to CSV"),
    ("6", "Run purchase & cost analysis (reports + charts)"),
    ("7", "What-if: increase a material price (NumPy)"),
    ("0", "Exit"),
)


# --- Small input helpers -----------------------------------------------------
def ask_float(prompt: str) -> float:
    while True:
        try:
            return float(input(prompt).strip())
        except ValueError:
            print("  Please enter a number.")


def print_element(el: ConcreteElement) -> None:
    q = el.quantities()
    print(
        f"  {q['element_id']} | {q['element_name']} | {q['site']} | "
        f"net={q['net_volume_m3']} m3 | with waste={q['volume_with_waste_m3']} m3 | "
        f"cement={q['cement_kg']} kg | sand={q['sand_m3']} m3 | "
        f"aggregate={q['aggregate_m3']} m3"
    )


# --- Menu actions ------------------------------------------------------------
def action_add(mgr: ElementManager) -> None:
    try:
        mgr.add_from_values(
            element_id=input("  Element ID: ").strip(),
            element_name=input("  Name: ").strip(),
            site=input("  Site: ").strip(),
            length_m=ask_float("  Length (m): "),
            width_m=ask_float("  Width (m): "),
            height_m=ask_float("  Height (m): "),
            waste_pct=ask_float("  Waste (%): "),
        )
        print("  Element added.")
    except ValidationError as exc:
        print(f"  Rejected: {exc}")


def action_list(mgr: ElementManager) -> None:
    elements = mgr.list_elements()
    if not elements:
        print("  No elements yet.")
        return
    for el in elements:
        print_element(el)
    # slicing example: show the first two element IDs as a quick preview tuple
    ids = [el.element_id for el in elements]
    print(f"  ({len(ids)} elements; first two: {tuple(ids[:2])})")


def action_search(mgr: ElementManager) -> None:
    hits = mgr.search(input("  Search by ID or name: ").strip())
    if not hits:
        print("  No match.")
    for el in hits:
        print_element(el)


def action_update(mgr: ElementManager) -> None:
    el_id = input("  Element ID to update: ").strip()
    if mgr.get(el_id) is None:
        print("  Unknown element_id.")
        return
    field = input("  Field (name/site/length_m/width_m/height_m/waste_pct): ").strip()
    key_map = {"name": "element_name"}  # friendly alias
    field = key_map.get(field, field)
    raw = input("  New value: ").strip()
    value = raw
    if field in {"length_m", "width_m", "height_m", "waste_pct"}:
        try:
            value = float(raw)
        except ValueError:
            print("  Numeric field needs a number.")
            return
    try:
        mgr.update(el_id, **{field: value})
        print("  Updated.")
    except ValidationError as exc:
        print(f"  Rejected: {exc}")


def action_save(mgr: ElementManager) -> None:
    mgr.save_elements_csv(os.path.join(REPORTS_DIR, "elements_saved.csv"))
    mgr.save_quantities_csv(os.path.join(REPORTS_DIR, "element_quantities.csv"))
    print(f"  Saved to {REPORTS_DIR}/elements_saved.csv and element_quantities.csv")


def action_analysis(mgr: ElementManager) -> dict:
    res = ca.run_full_analysis(
        mgr, PRICES_CSV, PURCHASES_CSV, REPORTS_DIR, CHARTS_DIR
    )
    print("\n  Cost by site:")
    print(ca.cost_by(res["merged"], "site").to_string(index=False))
    print("\n  Cost by supplier:")
    print(ca.cost_by(res["merged"], "supplier_id").to_string(index=False))
    print("\n  Cost by month:")
    print(ca.cost_by(res["merged"], "month").to_string(index=False))
    shortages = res["comparison"][res["comparison"]["status"] == "SHORTAGE"]
    print(f"\n  {len(shortages)} shortage line(s) across elements/materials.")
    print(f"  Reports -> {REPORTS_DIR}")
    print(f"  Charts  -> {CHARTS_DIR}")
    return res


def action_whatif(mgr: ElementManager) -> None:
    prices = ca.load_prices(PRICES_CSV)
    materials = sorted(set(prices["material"]))  # set -> sorted list
    print(f"  Materials: {materials}")
    material = input("  Material to increase: ").strip().title()
    if material not in materials:
        print("  Unknown material.")
        return
    pct = ask_float("  Increase by (%): ")
    sim = ca.simulate_price_increase(mgr, prices, material, pct)
    print("\n  Required-quantity re-costing (baseline = lowest price/material):")
    for i in range(len(sim["materials"])):  # indexing over parallel arrays
        print(
            f"    {sim['materials'][i]:<10} qty={sim['required_qty'][i]:>10} "
            f"base={sim['baseline_unit_price'][i]:>6} "
            f"new={sim['new_unit_price'][i]:>6} "
            f"before={sim['cost_before'][i]:>10} after={sim['cost_after'][i]:>10}"
        )
    print(
        f"  TOTAL  before={sim['total_before']}  after={sim['total_after']}  "
        f"delta={sim['total_delta']} ({pct:+.0f}% on {material})"
    )


# --- Menu loop ---------------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print(" Construction Materials Cost Planner")
    print("=" * 60)

    if os.path.exists(ELEMENTS_CSV):
        mgr = load_elements_csv(ELEMENTS_CSV)
        print(f"Loaded {len(mgr.list_elements())} elements from data/elements.csv")
    else:
        mgr = ElementManager()
        print("Starting with an empty element list.")

    actions = {
        "1": action_add,
        "2": action_list,
        "3": action_search,
        "4": action_update,
        "5": action_save,
        "6": action_analysis,
        "7": action_whatif,
    }

    while True:
        print("\nMenu:")
        for key, label in MENU:
            print(f"  {key}. {label}")
        choice = input("Choose: ").strip()
        if choice == "0":
            print("Goodbye.")
            break
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid choice.")
            continue
        handler(mgr)


if __name__ == "__main__":
    main()
