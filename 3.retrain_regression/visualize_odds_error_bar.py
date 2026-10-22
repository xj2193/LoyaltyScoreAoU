"""Create all pairwise model odds-ratio comparisons.

The coefficient file contains point estimates only, so this script uses a
dumbbell plot rather than error bars or confidence intervals.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter
import numpy as np
import pandas as pd


LOOKBACK_YEAR = 5
SCRIPT_DIR = Path(__file__).resolve().parent
COEFFICIENT_FILE = SCRIPT_DIR / "coeff_all_lookback_years.csv"
COMPARISON_OUTPUT_FILE = (
    SCRIPT_DIR / f"odds_ratio_pairwise_comparisons_{LOOKBACK_YEAR}year.csv"
)
COMBINED_OUTPUT_FILE = (
    SCRIPT_DIR / f"odds_ratio_three_pairwise_panels_{LOOKBACK_YEAR}year.png"
)

MODEL_COLUMNS = {
    "original": ("original_odds", "Original model", "tab:blue"),
    "unweighted": ("aou_odds", "AoU unweighted model", "tab:green"),
    "weighted": ("weighted_aou_odds", "AoU weighted model", "tab:orange"),
}

COMPARISONS = [
    ("original", "unweighted"),
    ("original", "weighted"),
    ("unweighted", "weighted"),
]

FEATURE_LABELS = [
    "Medication (≥1)",
    "Colonoscopy",
    "Pap test",
    "BMI",
    "Diagnoses (≥2)",
    "Routine care",
    "Same-doctor visits (≥2)",
    "Medication (≥2)",
    "Medical exam",
    "ED visit",
    "Diagnoses (≥1)",
    "Flu shot",
    "A1C test",
    "Fecal occult test",
    "Outpatient visits (≥2)",
    "Pneumococcal vaccine",
    "Mammography",
    "Same-doctor visits (≥3)",
    "Any inpatient or outpatient visit",
    "PSA test",
]


def configure_odds_ratio_ticks(axis):
    """Show readable tick labels when odds ratios occupy one log decade."""
    lower_limit, upper_limit = axis.get_xlim()
    exponent_min = int(np.floor(np.log10(lower_limit))) - 1
    exponent_max = int(np.ceil(np.log10(upper_limit))) + 1
    mantissas = (1.0, 1.5, 2.0, 3.0, 5.0, 7.5)
    tick_values = sorted({
        mantissa * 10.0 ** exponent
        for exponent in range(exponent_min, exponent_max + 1)
        for mantissa in mantissas
        if lower_limit <= mantissa * 10.0 ** exponent <= upper_limit
    })

    axis.xaxis.set_major_locator(FixedLocator(tick_values))
    axis.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _: f"{value:g}")
    )
    axis.tick_params(
        axis="x", which="major", bottom=True, labelbottom=True, length=5
    )


def parse_array(value):
    """Parse a NumPy-style array stored as text in the coefficient CSV."""
    cleaned = str(value).replace("\n", " ").strip().strip("[]")
    return np.fromstring(cleaned, sep=" ")


def load_odds_ratios(file_path, lookback_year):
    coefficient_df = pd.read_csv(file_path)
    year_rows = coefficient_df.loc[
        coefficient_df["lookback_year"].eq(lookback_year)
    ]

    if len(year_rows) != 1:
        raise ValueError(
            f"Expected one coefficient row for lookback year {lookback_year}; "
            f"found {len(year_rows)}."
        )

    row = year_rows.iloc[0]
    expected_count = len(FEATURE_LABELS)
    model_odds = {}
    for model_key, (column, _, _) in MODEL_COLUMNS.items():
        odds = parse_array(row[column])
        if len(odds) != expected_count:
            raise ValueError(
                f"Expected {expected_count} {model_key} odds ratios; "
                f"found {len(odds)}."
            )
        if np.any(odds <= 0):
            raise ValueError(
                f"{model_key} odds ratios must be positive for a logarithmic axis."
            )
        model_odds[model_key] = odds

    return pd.DataFrame({"feature": FEATURE_LABELS, **model_odds})


def draw_odds_ratio_comparison(plot_df, first_model, second_model, output_file):
    """Draw and save one pairwise odds-ratio dumbbell plot."""
    _, first_label, first_color = MODEL_COLUMNS[first_model]
    _, second_label, second_color = MODEL_COLUMNS[second_model]
    positions = np.arange(len(plot_df))
    figure, axis = plt.subplots(figsize=(9, 9), constrained_layout=True)

    for position, row in zip(positions, plot_df.itertuples(index=False)):
        axis.plot(
            [getattr(row, first_model), getattr(row, second_model)],
            [position, position],
            color="0.72",
            linewidth=1.5,
            zorder=1,
        )

    axis.scatter(
        plot_df[first_model],
        positions,
        color=first_color,
        label=first_label,
        s=45,
        zorder=2,
    )
    axis.scatter(
        plot_df[second_model],
        positions,
        color=second_color,
        label=second_label,
        s=45,
        zorder=3,
    )

    axis.axvline(1.0, color="black", linewidth=1, linestyle="--")
    axis.set_xscale("log")
    configure_odds_ratio_ticks(axis)
    axis.set_yticks(positions, plot_df["feature"])
    axis.invert_yaxis()
    axis.set_xlabel("Odds ratio (log scale)")
    axis.set_ylabel("")
    axis.set_title(
        f"{first_label} vs {second_label} odds ratios\n"
        f"{LOOKBACK_YEAR}-year lookback"
    )
    axis.grid(axis="x", alpha=0.25)
    axis.legend(frameon=True, loc="best")

    figure.savefig(
        output_file,
        dpi=900,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(figure)


def draw_pairwise_panel_plot(plot_df, output_file):
    """Draw all three pairwise comparisons with shared axes and limits."""
    positions = np.arange(len(plot_df))
    all_odds = plot_df[list(MODEL_COLUMNS)].to_numpy().ravel()
    lower_limit = min(all_odds.min() / 1.15, 1.0 / 1.15)
    upper_limit = max(all_odds.max() * 1.15, 1.0 * 1.15)

    figure, axes = plt.subplots(
        1,
        len(COMPARISONS),
        figsize=(24, 10),
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )

    for axis, (first_model, second_model) in zip(axes, COMPARISONS):
        _, first_label, first_color = MODEL_COLUMNS[first_model]
        _, second_label, second_color = MODEL_COLUMNS[second_model]

        for position, row in zip(positions, plot_df.itertuples(index=False)):
            axis.plot(
                [getattr(row, first_model), getattr(row, second_model)],
                [position, position],
                color="0.72",
                linewidth=1.4,
                zorder=1,
            )

        axis.scatter(
            plot_df[first_model],
            positions,
            color=first_color,
            label=first_label,
            s=42,
            zorder=2,
        )
        axis.scatter(
            plot_df[second_model],
            positions,
            color=second_color,
            label=second_label,
            s=42,
            zorder=3,
        )
        axis.axvline(
            1.0, color="black", linewidth=1, linestyle="--", zorder=0
        )
        axis.set_xscale("log")
        axis.set_xlim(lower_limit, upper_limit)
        configure_odds_ratio_ticks(axis)
        axis.set_yticks(positions, plot_df["feature"])
        axis.set_xlabel("Odds ratio (log scale)")
        axis.set_title(f"{first_label}\nvs {second_label}")
        axis.grid(axis="x", alpha=0.25)
        axis.legend(frameon=True, loc="best", fontsize=9)

    axes[0].invert_yaxis()
    axes[0].set_ylabel("")
    figure.suptitle(
        f"Pairwise model odds-ratio comparisons: "
        f"{LOOKBACK_YEAR}-year lookback",
        fontsize=16,
    )

    figure.savefig(
        output_file,
        dpi=600,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(figure)


def build_odds_ratio_comparison(plot_df, first_model, second_model):
    """Build a table describing the second model relative to the first."""
    _, first_label, _ = MODEL_COLUMNS[first_model]
    _, second_label, _ = MODEL_COLUMNS[second_model]
    comparison_df = plot_df[["feature", first_model, second_model]].copy()
    comparison_df["or_fold_change"] = (
        comparison_df[second_model] / comparison_df[first_model]
    )
    comparison_df["percent_change"] = (
        comparison_df["or_fold_change"] - 1.0
    ) * 100.0
    comparison_df["direction"] = np.select(
        [
            comparison_df["or_fold_change"].gt(1.0),
            comparison_df["or_fold_change"].lt(1.0),
        ],
        ["higher", "lower"],
        default="unchanged",
    )

    comparison_df.insert(0, "comparison", f"{second_label} vs {first_label}")
    comparison_df = comparison_df.rename(columns={
        first_model: "reference_odds_ratio",
        second_model: "comparison_odds_ratio",
    })
    comparison_df.insert(2, "reference_model", first_label)
    comparison_df.insert(4, "comparison_model", second_label)
    return comparison_df


def print_odds_ratio_changes(comparison_df):
    """Print one pairwise odds-ratio comparison table."""
    first_label = comparison_df["reference_model"].iloc[0]
    second_label = comparison_df["comparison_model"].iloc[0]
    display_df = comparison_df.rename(columns={
        "feature": "Feature",
        "reference_odds_ratio": f"{first_label} OR",
        "comparison_odds_ratio": f"{second_label} OR",
        "or_fold_change": "OR fold change",
        "percent_change": "Percent change",
        "direction": "Direction",
    })

    print(f"\n{second_label} versus {first_label} odds-ratio changes")
    print(f"Fold change = {second_label} OR / {first_label} OR\n")
    print(display_df[[
        "Feature", f"{first_label} OR", f"{second_label} OR",
        "OR fold change", "Percent change", "Direction",
    ]].to_string(
        index=False,
        formatters={
            f"{first_label} OR": "{:.3f}".format,
            f"{second_label} OR": "{:.3f}".format,
            "OR fold change": "{:.3f}x".format,
            "Percent change": "{:+.1f}%".format,
        },
    ))


def main():
    odds_ratio_df = load_odds_ratios(COEFFICIENT_FILE, LOOKBACK_YEAR)
    comparison_tables = []

    draw_pairwise_panel_plot(odds_ratio_df, COMBINED_OUTPUT_FILE)
    print(f"Saved: {COMBINED_OUTPUT_FILE}")

    for first_model, second_model in COMPARISONS:
        comparison_df = build_odds_ratio_comparison(
            odds_ratio_df, first_model, second_model
        )
        comparison_tables.append(comparison_df)
        print_odds_ratio_changes(comparison_df)

        output_file = SCRIPT_DIR / (
            f"odds_ratio_{first_model}_vs_{second_model}_"
            f"{LOOKBACK_YEAR}year.png"
        )
        draw_odds_ratio_comparison(
            odds_ratio_df, first_model, second_model, output_file
        )
        print(f"Saved: {output_file}")

    pd.concat(comparison_tables, ignore_index=True).to_csv(
        COMPARISON_OUTPUT_FILE, index=False
    )
    print(f"Saved: {COMPARISON_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
