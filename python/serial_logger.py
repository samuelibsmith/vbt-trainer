import serial
import serial.tools.list_ports
import csv 
import os
import time
from datetime import datetime

BAUD_RATE = 115200 # baude rate means bits per second
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'sessions') # build sessions directory
#where data will be stored in vbt-trainer/data/sessions
HEADER_ROW = ["timestamp_ms", "raw_velocity", "smooth_velocity", "rep_num"]
# defines header row in csv. Must match serial output

def find_esp32_port():
    """
    Automatically finds the port which the ESP32 is connected to.
    """
    ports = serial.tools.list_ports.comports() #finds and lists all ports visible

    for port in ports:
        desc = port.description.lower() # gets the human-readable description of each port, in lower case
        if any(chip in desc for chip in ['cp210', 'ch340', 'uart', 'esp32']):
            print(f"Found ESP32 on {port.device} ({port.description})")

            return port.device
    
    print("Could not auto-detect ESP32") # in case detection fails

    # The followings a manual method from the user

    for i, port in enumerate(ports):
        print(f" [{i}] {port.device} - {port.description}")

    choice = int(input("Enter port number: "))
    
    return ports[choice].device

def create_session_files():
    """
    Creates the output directory if it doesn't exists, the builds timestamped
    file paths for this session's raw data and rep data
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True) # creates the directory, and any missing parent directories

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    # gets the current date and time formatted as Year-Month-Day_Hour-Minute

    # builds the raw and rep paths with timestamp formatted names

    raw_path = os.path.join(OUTPUT_DIR, f"{timestamp}_raw.csv")
    rep_path = os.path.join(OUTPUT_DIR, f"{timestamp}_reps.csv")

    return raw_path, rep_path

def parse_rep_summary(line):

    """
    Parses the data from each rep and writes it into the csv
    """
    parts = line.replace('# REP,', '').split(',') # replaces the # rep identifier and splits the line by commas

    try:
        rep_num, mcv, peak, vl= [float(p) for p in parts]
        return [int(rep_num), mcv, peak, vl]
    
    except ValueError as e:
        print(f" Warning: malformed rep line: {line} ({e})")
        return None
    

def run_logger(port):
    """
    Main logging loop:
    1. connects to the ESP32 on given port 
    2. reads lines until Ctrl+C inputted
    3. saves data to timestamped CSV files
    """

    raw_path, rep_path = create_session_files() # creates the output files and gets their paths

    # Provide user with information on where data will be stored
    print(F"\nLogging to:")
    print(F"Raw samples: {raw_path}")
    print(F"Rep samples: {rep_path}")
    print(F"\nPress Ctrl+C to stop.\n")


    raw_file = open(raw_path, 'w', newline='') # opens file for writing 
    rep_file = open(rep_path, 'w', newline='')

    raw_writer = csv.writer(raw_file) # wraps the file object so writing can be done to it
    rep_writer = csv.writer(rep_file)

    raw_writer.writerow(HEADER_ROW)
    rep_writer.writerow(['rep_num', 'mcv', 'peak_velocity', 'vl_percent'])

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2.5)
        ser.reset_input_buffer()
        #ser = serial.Serial(port, BAUD_RATE, timeout=1) #Opens the serial port connection to ESP32
        print(f"Connected to {port} at {BAUD_RATE}\n") #Alert user of connection success
        
        while True:
            #Reads line fron serial until a \n is read
            line = ser.readline().decode('utf-8', errors='replace').strip()
            if '# REP' in line:
                print(f"REP LINE: {repr(line)}")
    
            if not line:
                continue # if readline times out we want the program to continue running

            # --- Branch 1: Rep summary lines ---
            if line.startswith('# REP,'):
                
                print(f' {line}\n')
                parsed = parse_rep_summary(line) # parse the line into a list of values
                # if parsed condition verifies parsing is succeeding before writing values
                if parsed:
                    rep_writer.writerow(parsed)
                    rep_file.flush() # flush() forces Python to write its internal buffer 
                    # to disc immediately, rather than waiting for the buffer to fill up
                    # ensuring data ins't lost if the program crashes
                               
            # --- Branch 2: Other comment lines ---
            # These may be useful, so print them, but don't write to csv
            elif line.startswith('#'):
                print(f" {line}")
                continue

            # --- Branch 3: raw data lines ---
            # These lines should be raw data:
            # 1111, 3.333, 2.222, 0 
            else:
                # this try/except logic prevents more malformed lines from slipping through
                try:
                    parts = line.split(',') # splits line into a list by commas

                    if len(parts) == 4: #ensures there are only the 4 items we expect
                        raw_writer.writerow(parts)

                        if int(parts[0]) % 1250 == 0:
                            raw_file.flush() # flush file every 250 samples
                except ValueError:
                    pass
    
    except KeyboardInterrupt:
        # runs when Ctrl+c is pressed
        print("\n\nLogging stopped.")
        print(f"Session saved to: {OUTPUT_DIR}")

    finally: # finally will always run

        # flush remaining data
        raw_file.flush()
        rep_file.flush()
        # close data
        raw_file.close()
        rep_file.close()

        if 'ser' in locals() and ser.is_open: # closes the serial connection if it was opened
            ser.close()
            print("Serial port closed.")


# This logic verifies that this is the file being run, rather 
# than other files using functions imported from this file
if __name__ == '__main__':
    #STEP 1: find which port the ESP32 is on
    port = find_esp32_port()
    #STEP 2: start the logging process
    run_logger(port)



