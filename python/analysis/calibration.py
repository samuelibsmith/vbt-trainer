###
# VBT Trainer Project - Samuel Smith - Spring 2026
# sibsmith@bu.edu | sibsmith.ithaca@gmail.com
###

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd 
import sys
import os 

# Paths to data
raw_path = "data/sessions/2026-05-31_19-05_raw.csv"
rep_path = "data/sessions/2026-05-31_19-05_reps.csv"

# FUNCTIONS
def initialize_data(raw_path, rep_path=None):
    """
    Loads raw sample and rep summary CSVs into pandas DataFrames.
 
    Args:
        raw_path : path to the _raw.csv file (required)
        rep_path : path to the _reps.csv file (optional - defaults to none)
 
    Returns:
        (raw_df, rep_df) — rep_df is None if no rep file given
    """

    raw_df = pd.read_csv(raw_path) # Create the raw DataFrame 
    # Create a new time_s columb that is relative time in seconds from the first data point
    raw_df["time_s"] = (raw_df['timestamp_ms'] - raw_df['timestamp_ms'].iloc[0]) / 1000.0 

    rep_df = None
    
    # if a file is requested as an arguement at the path exists, create the rep DataFrame
    if rep_path and os.path.exists(rep_path):
        rep_df = pd.read_csv(rep_path)

    return raw_df, rep_df

def plot_session_velocity(raw_df, rep_df=None):
    """
    Plots smoothed velocity over time for the entire set of reps
    (Optional: overlays rep detection markers)
    """
    fig, ax = plt.subplots(figsize=(8,4))
    # plot the smoothed and raw velocities
    ax.plot(raw_df['time_s'], raw_df['smooth_velocity'], linewidth=0.8, color='steelblue', label='Smoothed velocity')
    ax.plot(raw_df['time_s'], raw_df['raw_velocity'], linewidth=0.4, color='lightgray', alpha=0.6, label='Raw velocity')
    # Create shaded area during each rep time interval
    # GOALS: 
    # - Shade area where each rep took place
    #   - Create a list of lists where 
    # - Highlight peak velocity (with a label)
    # - Create a horizontal line spanning the rep at the height of the MCV
    # if rep_df is not None and len(rep_df) > 0:
        
    # iterates for each rep ('rep_id') and gets the starting and ending times
    for rep_id in sorted(raw_df['rep_num'].unique()): 
        
        if rep_id == 0: # if first rep has not started, continue
            continue
            
        rep_data = raw_df[(raw_df['rep_num'] == rep_id) & (raw_df['raw_velocity'] > 0)] # gets all rows of raw_df for that rep_id


        start_time = rep_data['time_s'].min()  # retrieves the smallest time in the list 
        end_time = rep_data['time_s'].max() # retrieves the largest time in the list for the rep
        ax.axvspan(start_time, end_time, alpha=0.25) # creates a vertical span over the rep with a 75% transparency
    
        ax.set_ylabel('Velocity (meters/second)')
        ax.set_xlabel('Time (seconds')

    plt.show()

def least_squares_calibration(drop_heights_m, measured_velocities):
    """
    Computes the least squares scale factor between measured and 
    theoretical free-fall velocities. Returns a dictionary containing 
    calibration results.

    Arguments:
        drop_heights_m: list of drop heights in meters.
        measured_velocities: list of peak velocities from the device
                                with peak at the culmination of drop.

    Returns: 
        dictionary with keys:
            - k_scale_factor >> The factor relating v_m to v_i
            - rmse_ms >> root mean squared in ms
            - error_pct_per_drop >> 
            - v_theoretical >> the list of the theoretical impact velocities
            - v_measured >> the list of measured peak velocities
            - drop_heights >> the list of drop heights
    """

    g = 9.803 # gravitational acceleration
    # Returns a list of theoretical velocities from drop heights defined
    # uses v_f^2 = 2 g h^2 solved for v_f which is the peak or final velocity
    # so v = sqrt(2gh)
    v_theoretical = np.sqrt(2*g*np.array(drop_heights_m))
    v_measured = np.array(measured_velocities) # translate list to NumPy array
    # ___ LEAST SQUARES SOLUTION ___
    # Uses dot product to compute
    # Numerator: v_t[0]*v_m[0] + v_t[1]*v_m[1] + ... +
    # Deonminator: v_t[0]*v_t[0] + v_t[1]*v_t[1] + ... +
    k = np.dot(v_theoretical, v_measured) / np.dot(v_theoretical, v_theoretical)
    
    # calculate the residuals
    residuals = v_measured - k * v_theoretical
    
    # compute the Root Mean Squared Error (RMSE)
    # np.mean(residuals**2) to get average of squared residuals
    # np.sqre(result of mean squared) too get proper m/s units
    # RMSE will provide the a representation of the average error of our measured
    # velocities in m/s
    rmse = np.sqrt(np.mean(residuals**2))
    
    # Compute the Percent Error Per Drop
    # Positive reading means reading too hight
    # negative reading means reading too low
    error_pct = ((v_measured- v_theoretical) / (v_theoretical)) * 100
    
    # print analysis as a dictionary
    return {
        'k_scale_factor'     : k,
        'rmse_ms'            : rmse,
        'error_pct_per_drop' : error_pct.tolist(),
        # .tolist() converts NumPy arrays back to Python lists
        'v_theoretical'      : v_theoretical.tolist(),
        'v_measured'         : v_measured.tolist(),
        'drop_heights'       : drop_heights_m,
    }

def print_calibration_report(cal_results):
    """
    Prints a formatted calibration report to the terminal for easier analysis
    """

    # unpack dictionary
    k = cal_results['k_scale_factor']
    rmse = cal_results['rmse_ms']

    print('\n_______________ Calibration Report_________________')

    print(f"    Scale factor k  : {k:.4f}")
    print(f"    RMSE            : {rmse:.4} (m/s)")
    print(f"    Overall error   : {(k-1) * 100:+.2f}%")
    print()
    
if __name__ == '__main__':
    # Drop heights are the heights in METERS for each drop
    drop_heights = [0.25, 0.50, 0.75, 1.00]
    # The measured peak velocities of each according to the VBT
    measured_velocities = []

    # _____ LOAD AND PLOT A SESSION MODE
    raw_df, rep_df = initialize_data(raw_path, rep_path)
    plot_session_velocity(raw_df, rep_df)