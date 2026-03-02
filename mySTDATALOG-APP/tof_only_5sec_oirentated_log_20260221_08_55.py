import time
import json
import logging
import sys
import os
import numpy as np
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

# 1. SETUP
logging.getLogger('stdatalog_core').setLevel(logging.ERROR)

def main():
    hsd = HSDLink_v2()
    dev_id = 0
    comp_name = "vl53l8cx_tof"
    
    # Hide the cursor for a cleaner look
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        # 2. INITIALIZATION
        hsd.send_command(dev_id, json.dumps({comp_name: {"resolution": 0}})) # 4x4
        hsd.send_command(dev_id, json.dumps({comp_name: {"odr": 15.0}}))
        hsd.send_command(dev_id, json.dumps({comp_name: {"enable": True}}))
        hsd.start_log(dev_id)

        # Buffer to hold one full frame (16 zones)
        current_grid = np.zeros((4, 4))
        
        print("--- [ VL53L8CX LIVE 4x4 GRID ] ---")
        print("Orientation: 270° Rot + H-Flip (Transpose)")
        print("Press Ctrl+C to stop.\n")

        while True:
            res = hsd.get_sensor_data(dev_id, comp_name, 0)
            
            if res and len(res) > 1 and res[1]:
                raw_bytes = res[1]
                # A 4x4 frame is 16 pairs of (Status, Distance) = 128 bytes
                # 512 byte payload contains 4 frames.
                data = np.frombuffer(raw_bytes[4:], dtype=np.uint32).copy()
                
                # We extract the latest frame from the packet
                # Distances are at indices 1, 3, 5... up to 31
                if len(data) >= 32:
                    frame_distances = data[1:32:2] # Take 16 distance values
                    
                    # 1. Shape into native 4x4
                    native_grid = frame_distances.reshape((4, 4))
                    
                    # 2. Apply Orientation (Transpose for 270° Rot + H-Flip)
                    current_grid = native_grid.T 

            # 3. RENDER THE GRID (5Hz Update)
            # Use ANSI Home code \033[H to reset cursor to top of the grid area
            output = "\033[H" 
            output += f"Time: {time.strftime('%H:%M:%S')} | Target: ~2100mm\n"
            output += "+" + "------+" * 4 + "\n"
            
            for row in current_grid:
                row_str = "|"
                for val in row:
                    # Color coding: Green if < 1000mm (Object detected)
                    color = "\033[92m" if 0 < val < 1200 else "\033[0m"
                    row_str += f" {color}{int(val):4d}\033[0m |"
                output += row_str + "\n+" + "------+" * 4 + "\n"
            
            sys.stdout.write(output)
            sys.stdout.flush()

            # Balanced sleep: Fast enough for UI, slow enough for CPU
            time.sleep(0.1)

    except KeyboardInterrupt:
        # Show the cursor again on exit
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        print("\nStopping...")
        hsd.stop_log(dev_id)
    finally:
        hsd.close()

if __name__ == "__main__":
    main()