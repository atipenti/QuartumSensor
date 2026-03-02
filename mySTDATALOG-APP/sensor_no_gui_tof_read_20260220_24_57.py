import time
import json
import logging
import numpy as np
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

# Suppress background logs to keep console clean
logging.getLogger('stdatalog_core').setLevel(logging.ERROR)

def main():
    hsd = HSDLink_v2()
    dev_id = 0
    comp_name = "vl53l8cx_tof"
    
    print(f"--- [ CONFIGURING {comp_name.upper()} ] ---")
    try:
        # 1. INITIALIZE (Exactly like your working raw data script)
        hsd.send_command(dev_id, json.dumps({comp_name: {"resolution": 0}})) 
        hsd.send_command(dev_id, json.dumps({comp_name: {"odr": 15.0}}))
        hsd.send_command(dev_id, json.dumps({comp_name: {"enable": True}}))
        hsd.start_log(dev_id)
        print("Streaming started successfully.")

        # 2. AVERAGING CONFIGURATION
        PACKET_SIZE = 516 
        VALID_STATUS = 5
        REPORT_INTERVAL = 5 # 5 seconds
        dist_buffer = []
        start_timer = time.time()

        print(f"Averaging valid distances (Status {VALID_STATUS})...")
        print("Reports will appear every 5 seconds.")

        while True:
            # res[1] contains the raw bytes we need
            res = hsd.get_sensor_data(dev_id, comp_name, 0)
            
            if res and res[1]:
                raw_bytes = res[1]
                nof_packets = len(raw_bytes) // PACKET_SIZE
                
                for p in range(nof_packets):
                    # Slice the payload (Skipping 4-byte header)
                    start = (p * PACKET_SIZE) + 4
                    payload = raw_bytes[start : start + 512]
                    
                    # Convert bytes to 32-bit integers
                    data = np.frombuffer(payload, dtype=np.uint32)
                    
                    # The data is [Status, Distance, Status, Distance...]
                    # We look at all zones in the packet
                    for i in range(0, len(data) - 1, 2):
                        status = data[i]
                        distance = data[i+1]
                        
                        # Filter for Valid Status and realistic distance
                        if status == VALID_STATUS and 0 < distance < 5000:
                            dist_buffer.append(distance)

            # 3. 5-SECOND REPORTING LOGIC
            if time.time() - start_timer >= REPORT_INTERVAL:
                print(f"\n[{time.strftime('%H:%M:%S')}] --- 5s REPORT ---")
                if dist_buffer:
                    avg_val = np.mean(dist_buffer)
                    print(f"  Average Distance : {avg_val:.2f} mm")
                    print(f"  Valid Pings      : {len(dist_buffer)}")
                    print(f"  Min/Max Range    : {min(dist_buffer)}mm - {max(dist_buffer)}mm")
                else:
                    print("  Status: Waiting for target (No Status 5 data found).")
                
                print("-" * 35)

                # Reset for the next window
                dist_buffer = []
                start_timer = time.time()

            # Low sleep to keep CPU usage low
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopping log and closing connection...")
        hsd.stop_log(dev_id)
    finally:
        hsd.close()

if __name__ == "__main__":
    main()