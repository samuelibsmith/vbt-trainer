"""
VBT Trainer - calibration and session plotting
Samuel Smith - Spring 2026

How calibration is split in this script (two jobs, kept separate on purpose):

  1. PULLS set the scale. You pull the cord through distances you measured
     with a tape and record the encoder counts. Nothing moves fast, no
     dynamics are involved, so the fit gives a clean mm_per_pulse.
  2. DROPS only check the result. A falling mass also has to spin the
     spool up, so drop velocities always read lower than the ideal
     free-fall formula. That gap is physics, not scale error, so drops
     are used to measure the spool's inertia and validate the whole
     measurement chain - never to adjust mm_per_pulse.

Usage (run from anywhere; paths are arguments, not hardcoded):

  # Plot a logged session
  python python/analysis/calibration.py plot data/sessions/2026-05-31_19-05_raw.csv

  # Primary calibration: fit mm per pulse from known-distance pulls.
  # pulls.csv columns: distance_mm,counts,direction   (direction: out / in)
  python python/analysis/calibration.py pulls data/calibration/pulls.csv

  # Cross-check: drop test with spool-inertia correction.
  # A known mass falls a known height unwinding the spool; the recorded
  # peak velocity is compared against v = sqrt(2 g h / (1 + I/(m r^2))).
  python python/analysis/calibration.py drops \
      --heights 0.25 0.50 0.75 1.00 \
      --velocities <peak v of each drop, m/s> \
      --mass-kg 5.0
"""

import argparse
import datetime
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

G = 9.803  # gravitational acceleration, m/s^2
COUNTS_PER_REV = 2400  # 600 PPR encoder, x4 quadrature decoding
DEFAULT_SPOOL_RADIUS_MM = 18.735  # SPOOL_DIAMETER_MM 37.47 in config.h, / 2


def initialize_data(raw_path, rep_path=None):
    """
    Load the raw sample CSV and (optionally) the rep summary CSV.

    Used by the 'plot' command. The firmware/logger timestamps are in
    milliseconds since the logger started; plotting wants seconds from
    the first sample, so a 'time_s' column is added here.

    Args:
        raw_path: path to the *_raw.csv file (required)
        rep_path: path to the *_reps.csv file (optional)

    Returns:
        (raw_df, rep_df) - rep_df is None if no rep file was given or found.
        raw_df gains a 'time_s' column: seconds since the first sample.
    """
    raw_df = pd.read_csv(raw_path)
    # Subtract the first timestamp so time starts at 0, then ms -> s.
    raw_df["time_s"] = (raw_df["timestamp_ms"] - raw_df["timestamp_ms"].iloc[0]) / 1000.0

    # The rep file is optional: only load it if a path was given AND it exists.
    rep_df = None
    if rep_path and os.path.exists(rep_path):
        rep_df = pd.read_csv(rep_path)

    return raw_df, rep_df


def plot_session_velocity(raw_df):
    """
    Plot raw and smoothed velocity for a session, shading each detected rep.

    The raw trace is drawn faint (it is noisy at 200 Hz), the smoothed
    trace on top of it. Each rep the firmware detected gets a shaded
    band so you can see at a glance whether rep detection lined up
    with the actual lifts.
    """
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(raw_df["time_s"], raw_df["raw_velocity"],
            linewidth=0.4, color="lightgray", alpha=0.6, label="Raw velocity")
    ax.plot(raw_df["time_s"], raw_df["smooth_velocity"],
            linewidth=0.8, color="steelblue", label="Smoothed velocity")

    # rep_num == 0 means no rep in progress; shade the concentric (v > 0) part of each rep
    for rep_id in sorted(raw_df["rep_num"].unique()):
        if rep_id == 0:
            continue
        rep_data = raw_df[(raw_df["rep_num"] == rep_id) & (raw_df["raw_velocity"] > 0)]
        if rep_data.empty:
            continue
        ax.axvspan(rep_data["time_s"].min(), rep_data["time_s"].max(), alpha=0.25)

    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Velocity (m/s)")
    ax.legend()
    plt.tight_layout()
    plt.show()


# ── Primary calibration: known-distance pulls ────────────────────────────────

def fit_mm_per_pulse(pulls_df):
    """
    Fit mm_per_pulse from known-distance pulls, least squares through the origin.

    Model: distance_mm = mm_per_pulse * counts. Zero counts must mean zero
    distance, so the fit has no intercept. Minimising sum((d - s*n)^2)
    over s gives s = (d.n) / (n.n).

    Fits the whole table, then each direction separately: if out and in
    disagree, that is backlash or cord seating and it should be seen,
    not averaged away silently.

    Args:
        pulls_df: DataFrame with distance_mm, counts, direction columns

    Returns:
        dict with mm_per_pulse, rms_mm, max_error_pct, implied_diameter_mm,
        residuals_mm (array), by_direction {name: (mm_per_pulse, n_pulls)}
    """
    def fit(d, n):
        # One fit of the model d = s * n, used for the whole table and
        # again per direction below.
        # np.dot(d, n) is sum(d_i * n_i) and np.dot(n, n) is sum(n_i^2):
        # this is the least-squares slope through the origin.
        s = np.dot(d, n) / np.dot(n, n)
        # Residuals: how far each measured distance sits from the fitted
        # line, in mm. Their size (RMS) and pattern (see the plot) are
        # the quality check on the fit.
        resid = d - s * n
        # Return (fitted constant, RMS residual in mm, worst per-pull error in %)
        return s, np.sqrt(np.mean(resid ** 2)), np.max(np.abs(resid / d)) * 100

    # Pull the columns out as plain float arrays for the maths.
    d = pulls_df["distance_mm"].to_numpy(dtype=float)
    n = pulls_df["counts"].to_numpy(dtype=float)
    s, rms_mm, max_pct = fit(d, n)

    # Refit each direction on its own rows. groupby splits the table
    # into one sub-table per direction value ('out', 'in', ...).
    by_direction = {}
    for direction, group in pulls_df.groupby("direction"):
        gd = group["distance_mm"].to_numpy(dtype=float)
        gn = group["counts"].to_numpy(dtype=float)
        by_direction[direction] = (fit(gd, gn)[0], len(group))

    return {
        "mm_per_pulse": s,
        "rms_mm": rms_mm,
        "max_error_pct": max_pct,
        # One revolution is COUNTS_PER_REV counts, so the fitted constant
        # implies a spool circumference; / pi turns it into a diameter
        # that can be compared against the config.h / caliper value.
        "implied_diameter_mm": s * COUNTS_PER_REV / np.pi,
        "residuals_mm": d - s * n,
        "n_pulls": len(pulls_df),
        "by_direction": by_direction,
    }


def plot_pulls_fit(pulls_df, result, out_path):
    """
    Save the two-panel pulls figure.

    Left panel: distance vs counts with the fitted line. Tight points on
    the line = the constant explains the data.
    Right panel: residuals vs distance. This is the diagnostic panel:
    random scatter around zero is healthy; a fan split by direction
    means the directions disagree; a smooth curve means the effective
    radius changes with extension (cord layering).
    """
    d = pulls_df["distance_mm"].to_numpy(dtype=float)
    n = pulls_df["counts"].to_numpy(dtype=float)
    directions = sorted(pulls_df["direction"].unique())
    colors = {"out": "steelblue", "in": "darkorange"}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    for direction in directions:
        # Boolean mask selecting just this direction's rows.
        m = pulls_df["direction"].to_numpy() == direction
        ax1.scatter(n[m], d[m], s=18, color=colors.get(direction, "gray"),
                    label=f"{direction} pulls")
        ax2.scatter(d[m], result["residuals_mm"][m], s=18,
                    color=colors.get(direction, "gray"), label=direction)
    # The fitted line, drawn slightly past the largest count.
    xs = np.linspace(0, n.max() * 1.05, 10)
    ax1.plot(xs, result["mm_per_pulse"] * xs, "k-", linewidth=1.2,
             label=f"fit through origin: {result['mm_per_pulse']:.5f} mm/pulse")
    ax1.set_xlabel("Encoder counts")
    ax1.set_ylabel("Known distance (mm)")
    ax1.set_title("Pulls fit")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    ax2.axhline(0, color="k", linewidth=1)
    ax2.set_xlabel("Known distance (mm)")
    ax2.set_ylabel("Residual (mm)")
    ax2.set_title(f"Residuals (RMS {result['rms_mm']:.2f} mm)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def print_pulls_report(result):
    """
    Print the pulls calibration report, including a one-line record.

    The report leads with the number that matters (MM_PER_PULSE, ready
    to paste into config.h) and ends with a single-line CALIBRATION
    RECORD: date, method, sample count and residual. Save that line
    with the result - it is what any future accuracy claim rests on.
    """
    print("\n_______________ Pulls Calibration Report _______________")
    print(f"  MM_PER_PULSE     : {result['mm_per_pulse']:.5f} mm/pulse   <- paste into config.h")
    print(f"  Implied diameter : {result['implied_diameter_mm']:.2f} mm "
          f"(SPOOL_DIAMETER_MM equivalent)")
    print(f"  Residual RMS     : {result['rms_mm']:.3f} mm over {result['n_pulls']} pulls")
    print(f"  Max error        : {result['max_error_pct']:.2f}%")
    print("  By direction     :")
    for direction, (s, count) in sorted(result["by_direction"].items()):
        print(f"    {direction:>4} : {s:.5f} mm/pulse  ({count} pulls)")
    dirs = [s for s, _ in result["by_direction"].values()]
    if len(dirs) > 1:
        # How far apart the direction constants are, as % of the overall
        # constant. Over ~0.2% is more than fit noise: worth a look at
        # the mechanics before trusting a single constant.
        spread = (max(dirs) - min(dirs)) / result["mm_per_pulse"] * 100
        print(f"  Direction spread : {spread:.2f}%  "
              f"({'investigate backlash / cord seating' if spread > 0.2 else 'ok'})")
    print(f"\n  CALIBRATION RECORD: {datetime.date.today().isoformat()} "
          f"method=known_distance pulls={result['n_pulls']} "
          f"mm_per_pulse={result['mm_per_pulse']:.5f} rms_mm={result['rms_mm']:.3f}")
    print()


# ── Cross-check: drop test with spool-inertia correction ─────────────────────

def analyze_drops(drop_heights_m, measured_velocities, mass_kg,
                  spool_radius_mm=DEFAULT_SPOOL_RADIUS_MM, inertia_kg_m2=None):
    """
    Drop-test cross-check with the spool-inertia-corrected model.

    Energy: m g h = 1/2 m v^2 + 1/2 I omega^2 with omega = v / r, so
        v = sqrt(2 g h / (1 + I / (m r^2))).
    The ideal sqrt(2 g h) is recovered only as I / (m r^2) -> 0.

    Two things are extracted from the data:
      - Regressing v^2 against h gives slope = 2 g / (1 + I/(m r^2)),
        so the slope measures the spool's effective inertia.
      - The regression intercept should be ~0. A clearly negative
        intercept indicates constant losses (bearing/cord friction,
        release effects) rather than inertia.

    The old-style k (measured vs ideal fit) is reported for reference
    only. It mixes inertia into the scale and must NOT be used to
    correct mm_per_pulse; the pulls fit owns the scale.

    Args:
        drop_heights_m: drop heights in meters
        measured_velocities: peak velocity the device recorded per drop (m/s)
        mass_kg: mass of the dropped weight
        spool_radius_mm: spool radius (defaults to config.h spool / 2)
        inertia_kg_m2: optional known spool inertia; if given, the
            corrected model is also predicted from it independently
            of the regression fit

    Returns:
        dict with slope, intercept, inertia_ratio_fit, inertia_fit,
        v_ideal, v_corrected_fit, v_measured, error_pct_vs_corrected,
        old_k, and (if inertia given) v_corrected_given, error_pct_vs_given
    """
    h = np.array(drop_heights_m, dtype=float)
    v_m = np.array(measured_velocities, dtype=float)
    r = spool_radius_mm / 1000.0  # mm -> m; SI units from here on

    # The no-spool theory, and the original script's k against it.
    # k is kept only so old and new results can be compared side by side.
    v_ideal = np.sqrt(2 * G * h)
    old_k = np.dot(v_ideal, v_m) / np.dot(v_ideal, v_ideal)

    # The core regression. Squaring the corrected model gives
    #     v^2 = (2 g / (1 + I/(m r^2))) * h
    # which is a straight line in h. A is the design matrix: each row
    # is [h_i, 1], so lstsq solves for [slope, intercept] in one call.
    # Fitting WITH an intercept is deliberate: forcing it to zero would
    # hide exactly the friction signal the intercept is there to expose.
    A = np.vstack([h, np.ones_like(h)]).T
    slope, intercept = np.linalg.lstsq(A, v_m ** 2, rcond=None)[0]
    # Invert slope = 2 g / (1 + I/(m r^2))  ->  I/(m r^2) = 2 g/slope - 1
    ratio_fit = 2 * G / slope - 1
    # And I itself, from I = (I/(m r^2)) * m * r^2.
    inertia_fit = ratio_fit * mass_kg * r ** 2
    # The corrected model's prediction at each drop height, using the
    # fitted inertia. Per-drop errors against THIS (not the ideal) are
    # the honest verdict on the device.
    v_corr_fit = np.sqrt(2 * G * h / (1 + ratio_fit))

    result = {
        "drop_heights": h.tolist(),
        "v_measured": v_m.tolist(),
        "v_ideal": v_ideal.tolist(),
        "slope": slope,
        "intercept": intercept,
        "inertia_ratio_fit": ratio_fit,
        "inertia_fit": inertia_fit,
        "v_corrected_fit": v_corr_fit.tolist(),
        "error_pct_vs_corrected": ((v_m - v_corr_fit) / v_corr_fit * 100).tolist(),
        "old_k": old_k,
        "v_corrected_given": None,
        "error_pct_vs_given": None,
    }
    if inertia_kg_m2 is not None:
        # Independent check: predict from a separately known inertia
        # (e.g. calculated from spool geometry) instead of the fitted
        # one. If these errors are also small, the fit and the geometry
        # agree, which is much stronger evidence than either alone.
        ratio_given = inertia_kg_m2 / (mass_kg * r ** 2)
        v_given = np.sqrt(2 * G * h / (1 + ratio_given))
        result["v_corrected_given"] = v_given.tolist()
        result["error_pct_vs_given"] = ((v_m - v_given) / v_given * 100).tolist()
    return result


def plot_drops_check(result, out_path):
    """
    Save the two-panel drop-test figure.

    Left panel: measured peak velocity vs height, against the ideal
    curve (dashed) and the inertia-corrected curve (green). Points
    should hug the green curve and sag below the dashed one by a
    constant factor.
    Right panel: the v^2 regression itself. The green line should sit
    parallel below the dashed ideal slope 2g; the vertical gap between
    the slopes IS the inertia, and where the green line crosses h = 0
    is the friction intercept.
    """
    h = np.array(result["drop_heights"])
    v_m = np.array(result["v_measured"])
    hh = np.linspace(0, h.max() * 1.05, 50)
    ratio = result["inertia_ratio_fit"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    ax1.plot(hh, np.sqrt(2 * G * hh), "k--", linewidth=1.2,
             label="ideal sqrt(2gh): no spool")
    ax1.plot(hh, np.sqrt(2 * G * hh / (1 + ratio)), "g-", linewidth=1.2,
             label="inertia-corrected model")
    ax1.scatter(h, v_m, s=35, color="steelblue", zorder=5, label="measured peaks")
    ax1.set_xlabel("Drop height (m)")
    ax1.set_ylabel("Peak velocity (m/s)")
    ax1.set_title("Drop test cross-check")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    ax2.scatter(h, v_m ** 2, s=35, color="steelblue", zorder=5, label="measured v^2")
    ax2.plot(hh, result["slope"] * hh + result["intercept"], "g-", linewidth=1.2,
             label="regression v^2 = slope*h + c")
    ax2.plot(hh, 2 * G * hh, "k--", linewidth=1, label="ideal slope 2g")
    ax2.set_xlabel("Drop height (m)")
    ax2.set_ylabel("v^2 (m^2/s^2)")
    ax2.set_title("Slope gives inertia, intercept gives friction")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def print_drops_report(result, mass_kg):
    """
    Print the drop-test cross-check report.

    Reading it: the fitted I/(m r^2) says how much of the ideal
    velocity the spool's inertia eats; the intercept verdict says
    whether friction/release losses are also present; the per-drop
    error column is measured against the corrected model, so small
    errors there mean the device + model agree.
    """
    print("\n_______________ Drop Test Cross-Check _______________")
    print(f"  Drop mass        : {mass_kg:.2f} kg")
    print(f"  Fitted I/(m r^2) : {result['inertia_ratio_fit']:.3f}")
    print(f"  Fitted inertia I : {result['inertia_fit']:.3e} kg m^2")
    print(f"  Intercept        : {result['intercept']:+.3f} m^2/s^2  "
          f"({'ok, losses negligible' if result['intercept'] > -0.1 else 'negative: friction / release losses present'})")
    print(f"  Old-style k      : {result['old_k']:.4f}  (reference only - do NOT correct the scale with this)")
    print("\n  Height (m)   Ideal (m/s)   Corrected (m/s)   Measured (m/s)   Error vs corrected (%)")
    for h, vi, vc, vm, e in zip(result["drop_heights"], result["v_ideal"],
                                result["v_corrected_fit"], result["v_measured"],
                                result["error_pct_vs_corrected"]):
        print(f"  {h:>9.2f}   {vi:>11.3f}   {vc:>15.3f}   {vm:>14.3f}   {e:>+8.2f}")
    if result["v_corrected_given"] is not None:
        errs = result["error_pct_vs_given"]
        print(f"\n  Vs independently specified inertia: "
              f"max |error| {np.max(np.abs(errs)):.2f}%")
    print()


# ── CLI ──────────────────────────────────────────────────────────────────────
# Command-line wiring only: parse the arguments, call the function for
# the chosen subcommand, print its report, save its figure.

def main():
    parser = argparse.ArgumentParser(description="VBT calibration and session plotting")
    sub = parser.add_subparsers(dest="command", required=True)

    # plot: the original session viewer, unchanged.
    p_plot = sub.add_parser("plot", help="plot a logged session")
    p_plot.add_argument("raw", help="path to a *_raw.csv file")
    p_plot.add_argument("--reps", help="optional path to the matching *_reps.csv file")

    # pulls: primary calibration from a bench CSV.
    p_pulls = sub.add_parser("pulls", help="fit mm_per_pulse from known-distance pulls")
    p_pulls.add_argument("csv", help="pulls CSV with distance_mm,counts,direction columns")
    p_pulls.add_argument("--out", help="figure output path (default: <csv>_fit.png)")

    # drops: cross-check from drop heights + recorded peak velocities.
    p_drops = sub.add_parser("drops", help="drop-test cross-check with inertia correction")
    p_drops.add_argument("--heights", type=float, nargs="+", required=True,
                         help="drop heights in meters")
    p_drops.add_argument("--velocities", type=float, nargs="+", required=True,
                         help="measured peak velocity per drop (m/s), same order as --heights")
    p_drops.add_argument("--mass-kg", type=float, required=True,
                         help="mass of the dropped weight in kg")
    p_drops.add_argument("--spool-radius-mm", type=float, default=DEFAULT_SPOOL_RADIUS_MM,
                         help="spool radius in mm (default: config.h spool diameter / 2)")
    p_drops.add_argument("--inertia", type=float, default=None,
                         help="optional known spool inertia in kg m^2, checked independently")
    p_drops.add_argument("--out", help="figure output path (default: drops_check.png)")

    args = parser.parse_args()

    if args.command == "plot":
        raw_df, _ = initialize_data(args.raw, args.reps)
        plot_session_velocity(raw_df)

    elif args.command == "pulls":
        pulls_df = pd.read_csv(args.csv)
        # Fail loudly and specifically if the bench CSV is malformed;
        # fitting the wrong columns would produce a confident wrong number.
        missing = {"distance_mm", "counts"} - set(pulls_df.columns)
        if missing:
            parser.error(f"pulls CSV is missing columns: {sorted(missing)}")
        if "direction" not in pulls_df.columns:
            # Direction is strongly recommended (it exposes backlash),
            # but a single-direction table is still fittable.
            pulls_df["direction"] = "all"
        result = fit_mm_per_pulse(pulls_df)
        print_pulls_report(result)
        out = args.out or os.path.splitext(args.csv)[0] + "_fit.png"
        plot_pulls_fit(pulls_df, result, out)
        print(f"  Figure saved: {out}\n")

    else:  # drops
        if len(args.heights) != len(args.velocities):
            parser.error("--heights and --velocities must have the same number of values")
        if args.mass_kg <= 0:
            parser.error("--mass-kg must be positive")
        result = analyze_drops(args.heights, args.velocities, args.mass_kg,
                               spool_radius_mm=args.spool_radius_mm,
                               inertia_kg_m2=args.inertia)
        print_drops_report(result, args.mass_kg)
        out = args.out or "drops_check.png"
        plot_drops_check(result, out)
        print(f"  Figure saved: {out}\n")


if __name__ == "__main__":
    main()
