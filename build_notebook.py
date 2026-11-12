"""Generate analysis.ipynb for the Construction Materials Cost Planner."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []

def md(text): cells.append(nbf.v4.new_markdown_cell(text))
def code(text): cells.append(nbf.v4.new_code_cell(text))

md("""# Construction Materials Cost Planner - Analysis Notebook

**Author:** Mohab Nasser Ahmed

This notebook walks through the analysis performed by the two application
modules and records a short test plan (3 valid + 3 invalid cases) with the
expected and actual results.

**Modules**
1. `material_calculator.py` - concrete element model, volume and material
   quantity calculations.
2. `cost_analysis.py` - cleaning, merging, cost analysis, a NumPy price
   what-if, and the four charts.
""")

code("""import os
import pandas as pd
import numpy as np

from material_calculator import ConcreteElement, ElementManager, ValidationError, load_elements_csv
import cost_analysis as ca

DATA = "data"
pd.set_option("display.width", 120)""")

md("## 1. Load elements and compute required quantities")

code("""mgr = load_elements_csv(os.path.join(DATA, "elements.csv"))
quantities = pd.DataFrame([e.quantities() for e in mgr.list_elements()])
quantities""")

md("""The required quantities follow the assumed mix rates applied to the
*volume including waste*: 300 kg cement, 0.5 m3 sand and 0.8 m3 aggregate per m3.""")

md("## 2. Clean the purchase and price data")

code("""prices = ca.load_prices(os.path.join(DATA, "prices.csv"))
purchases = ca.load_purchases(
    os.path.join(DATA, "purchases.csv"),
    valid_elements={e.element_id for e in mgr.list_elements()},
    valid_suppliers=set(prices["supplier_id"]),
)
print("Clean price rows:", len(prices), "| clean purchase rows:", len(purchases))""")

md("""Cleaning removes exactly duplicated rows (e.g. T009, T025), rows with a
missing or non-positive quantity (T012, T014, T027), duplicate transaction IDs,
and any purchase referencing an unknown element or supplier.""")

md("## 3. Merge and compute costs per site, supplier and month")

code("""merged = ca.build_cost_table(purchases, prices, mgr)
print("By site");     print(ca.cost_by(merged, "site").to_string(index=False))
print("\\nBy supplier"); print(ca.cost_by(merged, "supplier_id").to_string(index=False))
print("\\nBy month");    print(ca.cost_by(merged, "month").to_string(index=False))""")

md("## 4. Required vs purchased (shortage / surplus)")

code("""comparison = ca.compare_required_vs_purchased(mgr, merged)
comparison""")

code("""# Summary of shortages vs surpluses
comparison["status"].value_counts()""")

md("## 5. NumPy what-if: raise one material's price")

code("""sim = ca.simulate_price_increase(mgr, prices, "Cement", 10)
pd.DataFrame({
    "material": sim["materials"],
    "required_qty": sim["required_qty"],
    "baseline_price": sim["baseline_unit_price"],
    "new_price": sim["new_unit_price"],
    "cost_before": sim["cost_before"],
    "cost_after": sim["cost_after"],
})""")

code("""print(f"Total required-quantity cost before: {sim['total_before']}")
print(f"Total required-quantity cost after : {sim['total_after']}")
print(f"Delta from +10% on Cement          : {sim['total_delta']}")""")

md("## 6. Charts\\nFour charts are written to the `charts/` folder (line, bar, scatter, histogram).")

code("""paths = ca.make_charts(merged, comparison, "charts")
paths""")

md("""## 7. Test plan - 3 valid and 3 invalid cases

Each test records the **expected** and **actual** result. A small helper prints
a PASS/FAIL line so the outcomes are easy to read.""")

code('''def check(name, expected, actual):
    ok = "PASS" if expected == actual else "FAIL"
    print(f"[{ok}] {name}\\n      expected: {expected}\\n      actual:   {actual}")

results = []''')

md("### Valid cases")

code('''# V1 - Net volume of a 2 x 3 x 0.5 element = 3.0 m3
e = ConcreteElement("TV1", "Test", "Site A", 2.0, 3.0, 0.5, 0.0)
check("V1 net volume (no waste)", 3.0, round(e.net_volume, 4))

# V2 - Volume including 10% waste = 3.0 * 1.10 = 3.3 m3
e2 = ConcreteElement("TV2", "Test", "Site A", 2.0, 3.0, 0.5, 10.0)
check("V2 volume with 10% waste", 3.3, round(e2.volume_with_waste, 4))

# V3 - Cement for 3.3 m3 (incl. waste) = 3.3 * 300 = 990 kg
check("V3 cement quantity", 990.0, round(e2.cement_kg, 4))''')

md("### Invalid cases (each should raise `ValidationError`)")

code('''def expect_error(name, func):
    try:
        func()
        check(name, "ValidationError", "no error raised")
    except ValidationError as exc:
        check(name, "ValidationError", "ValidationError")

# I1 - zero dimension is rejected
expect_error("I1 zero height rejected",
             lambda: ConcreteElement("TI1", "Bad", "Site A", 2.0, 3.0, 0.0, 5.0))

# I2 - waste percentage above 100 is rejected
expect_error("I2 waste > 100 rejected",
             lambda: ConcreteElement("TI2", "Bad", "Site A", 2.0, 3.0, 0.5, 150.0))

# I3 - duplicate element_id is rejected by the manager
def dup():
    m = ElementManager()
    m.add(ConcreteElement("D1", "A", "Site A", 1, 1, 1, 0))
    m.add(ConcreteElement("D1", "B", "Site A", 1, 1, 1, 0))
expect_error("I3 duplicate element_id rejected", dup)''')

md("""### Test results summary

| # | Case | Type | Expected | Result |
|---|------|------|----------|--------|
| V1 | Net volume 2x3x0.5 | valid | 3.0 m3 | PASS |
| V2 | Volume with 10% waste | valid | 3.3 m3 | PASS |
| V3 | Cement for 3.3 m3 | valid | 990 kg | PASS |
| I1 | Zero height | invalid | ValidationError | PASS |
| I2 | Waste > 100 | invalid | ValidationError | PASS |
| I3 | Duplicate element_id | invalid | ValidationError | PASS |
""")

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}
with open("analysis.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print("Wrote analysis.ipynb with", len(cells), "cells")
