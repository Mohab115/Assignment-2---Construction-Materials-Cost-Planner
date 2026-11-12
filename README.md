# Construction Materials Cost Planner

**Author:** Mohab Nasser Ahmed
**Course:** C60 – Assignment 2 (Python Project)

A Python application that calculates construction material quantities and
analyzes purchases and costs. It is built as two connected modules driven by a
single menu in `main.py`.

## Project description

### Module 1 — Material Quantity Calculator (`material_calculator.py`)
- Models a concrete element (ID, name, site, length, width, height, waste %).
- Add, list, search, and update elements.
- Computes net volume, volume including waste, and the required cement, sand,
  and aggregate per element and per site.
- Saves element data and calculated quantities to CSV.

**Formulas**
- Net volume (m³) = length × width × height
- Volume including waste (m³) = net volume × (1 + waste % ÷ 100)
- Per m³ including waste: **300 kg** cement, **0.5 m³** sand, **0.8 m³** aggregate

### Module 2 — Purchase and Cost Analysis (`cost_analysis.py`)
- Reads the price file (supplier, material, unit, unit price) and the purchase
  file (transaction, element, supplier, material, date, quantity).
- Cleans the data with **pandas**: handles missing values, removes duplicates,
  and merges tables by their IDs.
- Calculates purchase cost per **site**, **supplier**, and **month**
  (cost = quantity × unit price).
- Compares required vs purchased quantities per element and material and flags
  **shortages/surpluses**, keeping units consistent (Cement in kg; Sand and
  Aggregate in m³).
- Uses **NumPy** to compare the estimated cost of required quantities before and
  after increasing a chosen material's price by a given percentage (baseline =
  the lowest available price per material).
- Produces four **Matplotlib** charts (line, bar, scatter, histogram) with
  titles and units.
- Exports CSV reports and PNG charts.

## Repository layout

```
.
├── main.py                 # menu connecting both modules
├── material_calculator.py  # Module 1
├── cost_analysis.py        # Module 2
├── build_notebook.py       # regenerates the notebook
├── analysis.ipynb          # explained analysis + test plan (3 valid / 3 invalid)
├── requirements.txt
├── data/
│   ├── elements.csv        # 8 elements across 2 sites
│   ├── prices.csv          # 2 suppliers per material
│   └── purchases.csv       # 38 transactions over 2 months (with dirty rows)
├── reports/                # generated CSV reports
└── charts/                 # generated PNG charts
```

## Required libraries

- Python 3.10+
- pandas
- numpy
- matplotlib
- (notebook only) jupyter / nbformat

Install everything with:

```bash
pip install -r requirements.txt
```

## How to run

**Interactive application**
```bash
python main.py
```
Use the menu to add/list/search/update elements, run the full purchase & cost
analysis (writes reports and charts), and run the price what-if.

**Run a module on its own (quick check)**
```bash
python material_calculator.py   # loads elements and prints quantities
python cost_analysis.py         # runs the full pipeline on the sample data
```

**Notebook**
```bash
jupyter notebook analysis.ipynb
```

## Outputs

- `reports/element_quantities.csv` — elements with all calculated quantities
- `reports/cost_by_site.csv`, `cost_by_supplier.csv`, `cost_by_month.csv`
- `reports/required_vs_purchased.csv` — shortage/surplus per element & material
- `charts/line_monthly_cost.png`, `bar_cost_per_site.png`,
  `scatter_qty_vs_cost.png`, `hist_line_costs.png`

## Validation rules

- Dimensions, prices, and purchase quantities must be greater than zero.
- Waste percentage must be between 0 and 100.
- Duplicate record IDs are rejected; purchases referencing unknown element or
  supplier IDs are dropped during cleaning.
