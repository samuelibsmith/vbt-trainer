"""
VBT Trainer - calibration and session plotting
Samuel Smith - Spring 2026

Usage (run from anywhere; paths are arguments, not hardcoded):

  # Plot a logged session
  python python/analysis/calibration.py plot data/sessions/2026-05-31_19-05_raw.csv

  # Fit the scale factor k from free-fall drops
  python python/analysis/calibration.py fit \
      --heights 0.25 0.50 0.75 1.00 \
      --velocities <peak v of each drop, m/s>
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

G = 9.803  # gravitational acceleration, m/s^2


def initialize_data(raw_path, rep_path=None):
    """
    Load the raw sample CSV and (optionally) the rep summary CSV.

    Args:
        raw_path: path to the *_raw.csv file (required)
        rep_path: path to the *_reps.csv file (optional)

    Returns:
        (raw_df, rep_df) - rep_df is None if no rep file was given or found.
        raw_df gains a 'time_s' column: seconds since the first sample.
    """
    raw_df = pd.read_csv(raw_path)
    raw_df["time_s"] = (raw_df["timestamp_ms"] - raw_df["timestamp_ms"].iloc[0]) / 1000.0

    rep_df = None
    if rep_path and os.path.exists(rep_path):
        rep_df = pd.read_csv(rep_path)

    return raw_df, rep_df


def plot_session_velocity(raw_df):
    """Plot raw and smoothed velocity for a session, shading each detected rep."""
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


def least_squares_calibration(drop_heights_m, measured_velocities):
    """
    Least-squares scale factor between measured and theoretical free-fall velocities.

    Theory: v = sqrt(2 g h) for a drop of height h.
    Model:  v_measured = k * v_theoretical, so k = (v_t . v_m) / (v_t . v_t).
    k > 1 means the device reads high; k < 1 means it reads low.

    Args:
        drop_heights_m: drop heights in meters
        measured_velocities: peak velocity the device recorded for each drop (m/s)

    Returns:
        dict with k_scale_factor, rmse_ms, error_pct_per_drop,
        v_theoretical, v_measured, drop_heights
    """
    v_theoretical = np.sqrt(2 * G * np.array(drop_heights_m))
    v_measured = np.array(measured_velocities)

    k = np.dot(v_theoretical, v_measured) / np.dot(v_theoretical, v_theoretical)
    residuals = v_measured - k * v_theoretical
    rmse = np.sqrt(np.mean(residuals ** 2))  # average error, m/s
    error_pct = (v_measured - v_theoretical) / v_theoretical * 100  # + = reads high

    return {
        "k_scale_factor": k,
        "rmse_ms": rmse,
        "error_pct_per_drop": error_pct.tolist(),
        "v_theoretical": v_theoretical.tolist(),
        "v_measured": v_measured.tolist(),
        "drop_heights": list(drop_heights_m),
    }


def print_calibration_report(cal):
    """Print a formatted calibration report."""
    print("\n_______________ Calibration Report _______________")
    print(f"  Scale factor k : {cal['k_scale_factor']:.4f}")
    print(f"  RMSE           : {cal['rmse_ms']:.4f} m/s")
    print(f"  Overall error  : {(cal['k_scale_factor'] - 1) * 100:+.2f}%")
    print("\n  Height (m)   Theoretical (m/s)   Measured (m/s)   Error (%)")
    for h, vt, vm, e in zip(cal["drop_heights"], cal["v_theoretical"],
                            cal["v_measured"], cal["error_pct_per_drop"]):
        print(f"  {h:>9.2f}   {vt:>17.3f}   {vm:>14.3f}   {e:>+8.2f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="VBT calibration and session plotting")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plot = sub.add_parser("plot", help="plot a logged session")
    p_plot.add_argument("raw", help="path to a *_raw.csv file")
    p_plot.add_argument("--reps", help="optional path to the matching *_reps.csv file")

    p_fit = sub.add_parser("fit", help="fit scale factor from free-fall drops")
    p_fit.add_argument("--heights", type=float, nargs="+", required=True,
                       help="drop heights in meters")
    p_fit.add_argument("--velocities", type=float, nargs="+", required=True,
                       help="measured peak velocity per drop (m/s), same order as --heights")

    args = parser.parse_args()

    if args.command == "plot":
        raw_df, _ = initialize_data(args.raw, args.reps)
        plot_session_velocity(raw_df)
    else:
        if len(args.heights) != len(args.velocities):
            parser.error("--heights and --velocities must have the same number of values")
        print_calibration_report(least_squares_calibration(args.heights, args.velocities))


if __name__ == "__main__":
    main()
