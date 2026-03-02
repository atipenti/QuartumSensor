import time
import json
import numpy as np
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

def main():
    hsd = HSDLink_v2()
    dev_id = 0
    comp_name = "vl53l8cx_tof"
    
    print("Configuring STWIN.box...")
    try:
        hsd.send_command(dev_id, json.dumps({comp_name: {"resolution": 0}})) 
        hsd.send_command(dev_id, json.dumps({comp_name: {"odr": 15.0}}))
        hsd.send_command(dev_id, json.dumps({comp_name: {"enable": True}}))
        hsd.start_log(dev_id)
        print("--- [ SYSTEM ONLINE ] ---")

        PACKET_SIZE = 516 

        while True:
            res = hsd.get_sensor_data(dev_id, comp_name, 0)
            if res and res[1]:
                raw_bytes = res[1]
                nof_packets = len(raw_bytes) // PACKET_SIZE
                
                for p in range(nof_packets):
                    # Slice the 512-byte payload
                    start = (p * PACKET_SIZE) + 4
                    payload = raw_bytes[start : start + 512]
                    
                    # Convert to 32-bit integers
                    data = np.frombuffer(payload, dtype=np.uint32).copy()
                    
                    # --- DEBUG: PRINT RAW DATA BLOCK ---
                    # We print the first 8 integers to see the structure of Zone 0
                    print(f"Raw Zone 0 Data: {data[:8].tolist()}")
                    
                    # Look for a number that changes when you move your hand
                    # If data[5] is always 0, try data[1], etc.
            else:
                print(".", end="", flush=True) # Heartbeat
                
            time.sleep(0.05)

    except KeyboardInterrupt:
        hsd.stop_log(dev_id)

if __name__ == "__main__":
    main()