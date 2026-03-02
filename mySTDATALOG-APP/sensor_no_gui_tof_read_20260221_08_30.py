/* it caputures my movement 1200 data points (15hz) x 4x4 x 5 sec, displayed each 5sec*/

import time
import json
import logging
import sys
import numpy as np
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

logging.getLogger('stdatalog_core').setLevel(logging.ERROR)

def main():
    hsd = HSDLink_v2()
    dev_id = 0
    comp_name = "vl53l8cx_tof"
    
    print(f"--- [ BRUTE FORCE DATA RECOVERY ] ---", flush=True)
    
    try:
        # Proven initialization
        hsd.send_command(dev_id, json.dumps({comp_name: {"resolution": 0}})) 
        hsd.send_command(dev_id, json.dumps({comp_name: {"odr": 15.0}}))
        hsd.send_command(dev_id, json.dumps({comp_name: {"enable": True}}))
        hsd.start_log(dev_id)

        PACKET_SIZE = 516 
        REPORT_INTERVAL = 5 
        
        dist_buffer = []
        start_timer = time.time()

        while True:
            res = hsd.get_sensor_data(dev_id, comp_name, 0)
            
            if res and len(res) > 1 and res[1]:
                print(".", end="", flush=True)
                raw_bytes = res[1]
                
                # Treat the whole chunk as uint32 to find ANY valid distances
                # We skip the very first 4 bytes of the whole chunk (header)
                data = np.frombuffer(raw_bytes[4:], dtype=np.uint32).copy()
                
                for val in data:
                    # Look for numbers that look like distances (100mm to 4000mm)
                    # and are NOT status codes (which are usually < 255)
                    if 150 < val < 5000:
                        dist_buffer.append(val)

            # 5-SECOND REPORT
            if time.time() - start_timer >= REPORT_INTERVAL:
                timestamp = time.strftime('%H:%M:%S')
                print(f"\n\n[{timestamp}] --- 5s REPORT ---")
                
                if dist_buffer:
                    # Use Median to filter out stray status codes that might look like distances
                    avg_val = np.median(dist_buffer)
                    print(f"  Average Distance : {avg_val:.2f} mm")
                    print(f"  Data Points Found: {len(dist_buffer)}")
                    print(f"  Sample Snippet   : {dist_buffer[:5]}")
                else:
                    print("  Status: No numbers between 150 and 5000 found in stream.")
                    if res and res[1]:
                        print(f"  Raw Byte Count: {len(res[1])}")
                
                print("-" * 35, flush=True)
                dist_buffer = []
                start_timer = time.time()

            time.sleep(0.05)

    except KeyboardInterrupt:
        hsd.stop_log(dev_id)
    finally:
        hsd.close()

if __name__ == "__main__":
    main()