import time
import json
import logging
import csv
import os
import numpy as np
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

# --- 1. SILENCE SDK LOGS ---
logging.getLogger('stdatalog_core').setLevel(logging.ERROR)

def main():
    hsd = HSDLink_v2()
    dev_id = 0
    comp_name = "vl53l8cx_tof"
    csv_filename = "tof_5s_averages.csv"
    
    print(f"\n" + "="*50)
    print(f" STWIN.BOX TOF MONITOR - PRO VERSION")
    print(f" Target: {comp_name.upper()} | Mode: 4x4 @ 15Hz")
    print(f"="*50)

    try:
        # --- 2. INITIALIZATION (PROVEN) ---
        hsd.send_command(dev_id, json.dumps({comp_name: {"resolution": 0}})) 
        hsd.send_command(dev_id, json.dumps({comp_name: {"odr": 15.0}}))
        hsd.send_command(dev_id, json.dumps({comp_name: {"enable": True}}))
        hsd.start_log(dev_id)
        
        # Initialize CSV Header
        if not os.path.exists(csv_filename):
            with open(csv_filename, 'w', newline='') as f:
                csv.writer(f).writerow(["Timestamp", "Avg_Distance_mm", "Samples", "Min_mm", "Max_mm"])

        REPORT_INTERVAL = 5 
        dist_buffer = []
        start_timer = time.time()

        print(f"Streaming... Saving to {csv_filename}")
        print("Monitoring distance (dots show incoming data clusters):")

        while True:
            res = hsd.get_sensor_data(dev_id, comp_name, 0)
            
            # Check for raw bytes in the second element of the response
            if res and len(res) > 1 and res[1]:
                print(".", end="", flush=True)
                raw_bytes = res[1]
                
                # Convert buffer to 32-bit integers, skipping the 4-byte header
                data = np.frombuffer(raw_bytes[4:], dtype=np.uint32).copy()
                
                # Brute force filter: 150mm to 5000mm (ignores status codes 0-15)
                for val in data:
                    if 150 < val < 5000:
                        dist_buffer.append(val)

            # --- 3. 5-SECOND SUMMARY ENGINE ---
            if time.time() - start_timer >= REPORT_INTERVAL:
                timestamp = time.strftime('%H:%M:%S')
                
                if dist_buffer:
                    # Median is used to ignore any stray outlier 'status' values
                    avg_val = float(np.median(dist_buffer))
                    min_val = int(np.min(dist_buffer))
                    max_val = int(np.max(dist_buffer))
                    samples = len(dist_buffer)

                    print(f"\n\n[{timestamp}] REPORT")
                    print(f"  Average  : {avg_val:.1f} mm")
                    print(f"  Range    : {min_val} - {max_val} mm")
                    print(f"  Samples  : {samples}")
                    print("-" * 30)

                    # Log to CSV
                    with open(csv_filename, 'a', newline='') as f:
                        csv.writer(f).writerow([timestamp, f"{avg_val:.1f}", samples, min_val, max_val])
                else:
                    print(f"\n[{timestamp}] No valid target detected.")

                dist_buffer = []
                start_timer = time.time()

            # Maintain the 50ms heartbeat for stability
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nShutting down safely...")
        hsd.stop_log(dev_id)
    finally:
        hsd.close()
        print("Connection closed.")

if __name__ == "__main__":
    main()