"""
Module 2 - Purchase and Cost Analysis
=====================================

Reads the price and purchase files, cleans them with pandas (missing values,
duplicates), merges them with the element data from Module 1, and produces:

  * purchase cost per site, per supplier and per month (cost = qty x unit price);
  * a required-vs-purchased comparison per element and material (shortage /
    surplus), with units kept consistent;
  * a NumPy "what-if" that re-prices required quantities after raising one
    material's price by a chosen percentage (baseline = lowest price/material);
  * four Matplotlib charts (line, bar, scatter, histogram);
  * CSV reports and PNG charts.
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")  # headless backend so charts save without a display
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from material_calculator import MATERIAL_UNITS, ElementManager


# =============================================================================
# Loading and cleaning
# =============================================================================
def load_prices(path: str) -> pd.DataFrame:
    """Load the price table and drop invalid / duplicate supplier-material rows."""
    prices = pd.read_csv(path)
    prices["material"] = prices["material"].str.strip().str.title()
    prices["unit_price"] = pd.to_numeric(prices["unit_price"], errors="coerce")

    before = len(prices)
    prices = prices.dropna(subset=["unit_price"])
    prices = prices[prices["unit_price"] > 0]  # prices must be > 0
    prices = prices.drop_duplicates(subset=["supplier_id", "material"])
    removed = before - len(prices)
    if removed:
        print(f"  [prices]   removed {removed} invalid/duplicate price row(s).")
    return prices.reset_index(drop=True)


def load_purchases(path: str, valid_elements: set[str] | None = None,
                   valid_suppliers: set[str] | None = None) -> pd.DataFrame:
    """Load and clean purchases.

    Cleaning steps:
      * strip text, title-case materials, parse dates and quantities;
      * drop fully duplicated rows;
      * drop rows with a missing/invalid (<= 0) quantity;
      * drop rows referencing unknown element or supplier IDs.
    """
    purchases = pd.read_csv(path)
    purchases["material"] = purchases["material"].str.strip().str.title()
    purchases["supplier_id"] = purchases["supplier_id"].str.strip()
    purchases["element_id"] = purchases["element_id"].str.strip()
    purchases["quantity"] = pd.to_numeric(purchases["quantity"], errors="coerce")
    purchases["date"] = pd.to_datetime(purchases["date"], errors="coerce")

    report = {"start": len(purchases)}

    # 1) exact duplicate rows
    purchases = purchases.drop_duplicates()
    report["after_dupe_rows"] = len(purchases)

    # 2) missing / non-positive quantity (quantities must be > 0)
    purchases = purchases.dropna(subset=["quantity", "date"])
    purchases = purchases[purchases["quantity"] > 0]
    report["after_bad_qty"] = len(purchases)

    # 3) duplicate transaction IDs that survived (keep the first occurrence)
    purchases = purchases.drop_duplicates(subset=["transaction_id"], keep="first")
    report["after_dupe_ids"] = len(purchases)

    # 4) unknown references
    if valid_elements is not None:
        purchases = purchases[purchases["element_id"].isin(valid_elements)]
    if valid_suppliers is not None:
        purchases = purchases[purchases["supplier_id"].isin(valid_suppliers)]
    report["after_unknown_refs"] = len(purchases)

    print(
        "  [purchases] {start} -> {after_dupe_rows} (dup rows) "
        "-> {after_bad_qty} (bad qty) -> {after_dupe_ids} (dup IDs) "
        "-> {after_unknown_refs} (unknown refs)".format(**report)
    )
    return purchases.reset_index(drop=True)


# =============================================================================
# Merging and cost calculation
# =============================================================================
def build_cost_table(purchases: pd.DataFrame, prices: pd.DataFrame,
                     manager: ElementManager) -> pd.DataFrame:
    """Merge purchases + prices + element sites and add a line cost column."""
    elements_df = pd.DataFrame(
        [{"element_id": e.element_id, "site": e.site}
         for e in manager.list_elements()]
    )

    merged = (
        purchases
        .merge(prices[["supplier_id", "material", "unit", "unit_price"]],
               on=["supplier_id", "material"], how="left")
        .merge(elements_df, on="element_id", how="left")
    )
    merged = merged.dropna(subset=["unit_price"])  # drop unpriced lines
    merged["cost"] = merged["quantity"] * merged["unit_price"]
    merged["month"] = merged["date"].dt.to_period("M").astype(str)
    return merged


def cost_by(merged: pd.DataFrame, key: str) -> pd.DataFrame:
    """Total purchase cost grouped by a single key (site / supplier_id / month)."""
    out = (
        merged.groupby(key, as_index=False)["cost"]
        .sum()
        .sort_values(key)
        .reset_index(drop=True)
    )
    out["cost"] = out["cost"].round(2)
    return out


# =============================================================================
# Required vs purchased comparison
# =============================================================================
def required_quantities_long(manager: ElementManager) -> pd.DataFrame:
    """One row per (element, material) with the required quantity and unit."""
    rows = []
    for el in manager.list_elements():
        rows.append(("Cement", el.cement_kg, el))
        rows.append(("Sand", el.sand_m3, el))
        rows.append(("Aggregate", el.aggregate_m3, el))
    return pd.DataFrame(
        {
            "element_id": [el.element_id for _, _, el in rows],
            "site": [el.site for _, _, el in rows],
            "material": [m for m, _, _ in rows],
            "unit": [MATERIAL_UNITS[m] for m, _, _ in rows],
            "required_qty": [round(q, 4) for _, q, _ in rows],
        }
    )


def compare_required_vs_purchased(manager: ElementManager,
                                  merged: pd.DataFrame) -> pd.DataFrame:
    """Shortage/surplus per element and material (units kept consistent)."""
    required = required_quantities_long(manager)
    purchased = (
        merged.groupby(["element_id", "material"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "purchased_qty"})
    )
    comp = required.merge(purchased, on=["element_id", "material"], how="left")
    comp["purchased_qty"] = comp["purchased_qty"].fillna(0.0).round(4)
    # balance > 0 => surplus (bought more than needed); < 0 => shortage
    comp["balance"] = (comp["purchased_qty"] - comp["required_qty"]).round(4)
    comp["status"] = np.where(
        comp["balance"] < 0, "SHORTAGE",
        np.where(comp["balance"] > 0, "SURPLUS", "BALANCED"),
    )
    return comp.sort_values(["element_id", "material"]).reset_index(drop=True)


# =============================================================================
# NumPy price-increase simulation
# =============================================================================
def baseline_prices(prices: pd.DataFrame) -> dict[str, float]:
    """Lowest available unit price for each material."""
    return (
        prices.groupby("material")["unit_price"].min().to_dict()
    )


def simulate_price_increase(manager: ElementManager, prices: pd.DataFrame,
                            material: str, pct: float) -> dict:
    """Re-cost total required quantities after raising one material's price.

    Uses NumPy arrays for the vectorised before/after cost computation and the
    lowest price per material as the baseline.
    """
    material = material.strip().title()
    materials = np.array(["Cement", "Sand", "Aggregate"])

    base = baseline_prices(prices)
    base_price = np.array([base.get(m, 0.0) for m in materials], dtype=float)

    required = manager.required_by_site()
    qty = np.zeros(3, dtype=float)
    for site_totals in required.values():  # sum across all sites
        qty += np.array([site_totals[m] for m in materials], dtype=float)

    # Vectorised price adjustment: only the selected material changes.
    factor = np.where(materials == material, 1 + pct / 100.0, 1.0)
    new_price = base_price * factor

    cost_before = qty * base_price
    cost_after = qty * new_price

    return {
        "materials": materials.tolist(),
        "required_qty": qty.round(4).tolist(),
        "baseline_unit_price": base_price.round(4).tolist(),
        "new_unit_price": new_price.round(4).tolist(),
        "cost_before": cost_before.round(2).tolist(),
        "cost_after": cost_after.round(2).tolist(),
        "total_before": float(cost_before.sum().round(2)),
        "total_after": float(cost_after.sum().round(2)),
        "total_delta": float((cost_after.sum() - cost_before.sum()).round(2)),
        "material_changed": material,
        "pct": pct,
    }


# =============================================================================
# Charts
# =============================================================================
def make_charts(merged: pd.DataFrame, comparison: pd.DataFrame,
                charts_dir: str) -> list[str]:
    """Create the four required charts and return their file paths."""
    os.makedirs(charts_dir, exist_ok=True)
    paths = []

    # 1) LINE - monthly purchase cost trend
    monthly = cost_by(merged, "month")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(monthly["month"], monthly["cost"], marker="o")
    ax.set_title("Monthly Purchase Cost")
    ax.set_xlabel("Month")
    ax.set_ylabel("Cost (currency units)")
    ax.grid(True, alpha=0.3)
    p = os.path.join(charts_dir, "line_monthly_cost.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig); paths.append(p)

    # 2) BAR - total cost per site
    by_site = cost_by(merged, "site")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(by_site["site"], by_site["cost"], color=["#4C72B0", "#DD8452"])
    ax.set_title("Total Purchase Cost per Site")
    ax.set_xlabel("Site")
    ax.set_ylabel("Cost (currency units)")
    for i, v in enumerate(by_site["cost"]):
        ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom")
    p = os.path.join(charts_dir, "bar_cost_per_site.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig); paths.append(p)

    # 3) SCATTER - purchased quantity vs line cost, coloured by material
    fig, ax = plt.subplots(figsize=(8, 5))
    for material, grp in merged.groupby("material"):
        ax.scatter(grp["quantity"], grp["cost"], label=material, alpha=0.7)
    ax.set_title("Purchase Quantity vs Line Cost")
    ax.set_xlabel("Quantity (kg for Cement, m3 for Sand/Aggregate)")
    ax.set_ylabel("Line cost (currency units)")
    ax.legend(title="Material")
    ax.grid(True, alpha=0.3)
    p = os.path.join(charts_dir, "scatter_qty_vs_cost.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig); paths.append(p)

    # 4) HISTOGRAM - distribution of per-transaction line costs
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(merged["cost"], bins=12, color="#55A868", edgecolor="white")
    ax.set_title("Distribution of Transaction Line Costs")
    ax.set_xlabel("Line cost (currency units)")
    ax.set_ylabel("Number of transactions")
    p = os.path.join(charts_dir, "hist_line_costs.png")
    fig.tight_layout(); fig.savefig(p, dpi=120); plt.close(fig); paths.append(p)

    return paths


# =============================================================================
# Report export
# =============================================================================
def export_reports(merged: pd.DataFrame, comparison: pd.DataFrame,
                   reports_dir: str) -> list[str]:
    """Write the CSV reports and return their paths."""
    os.makedirs(reports_dir, exist_ok=True)
    paths = []
    tables = {
        "cost_by_site.csv": cost_by(merged, "site"),
        "cost_by_supplier.csv": cost_by(merged, "supplier_id"),
        "cost_by_month.csv": cost_by(merged, "month"),
        "required_vs_purchased.csv": comparison,
    }
    for name, df in tables.items():
        path = os.path.join(reports_dir, name)
        df.to_csv(path, index=False)
        paths.append(path)
    return paths


def run_full_analysis(manager: ElementManager, prices_path: str,
                      purchases_path: str, reports_dir: str,
                      charts_dir: str) -> dict:
    """Convenience pipeline used by main.py and the notebook."""
    prices = load_prices(prices_path)
    purchases = load_purchases(
        purchases_path,
        valid_elements={e.element_id for e in manager.list_elements()},
        valid_suppliers=set(prices["supplier_id"]),
    )
    merged = build_cost_table(purchases, prices, manager)
    comparison = compare_required_vs_purchased(manager, merged)
    report_paths = export_reports(merged, comparison, reports_dir)
    chart_paths = make_charts(merged, comparison, charts_dir)
    return {
        "prices": prices,
        "purchases": purchases,
        "merged": merged,
        "comparison": comparison,
        "report_paths": report_paths,
        "chart_paths": chart_paths,
    }


if __name__ == "__main__":
    from material_calculator import load_elements_csv

    mgr = load_elements_csv(os.path.join("data", "elements.csv"))
    res = run_full_analysis(
        mgr,
        os.path.join("data", "prices.csv"),
        os.path.join("data", "purchases.csv"),
        "reports",
        "charts",
    )
    print("\nCost by site:\n", res["comparison"].head())
    sim = simulate_price_increase(mgr, res["prices"], "Cement", 10)
    print(f"\nWhat-if +10% Cement: {sim['total_before']} -> {sim['total_after']} "
          f"(delta {sim['total_delta']})")
    print("Reports:", res["report_paths"])
    print("Charts:", res["chart_paths"])
