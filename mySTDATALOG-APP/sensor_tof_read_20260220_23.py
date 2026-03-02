import sys, os, time, logging
import numpy as np
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

logging.getLogger('stdatalog_core').setLevel(logging.ERROR)

def main():
    try:
        hsd = HSDLink_v2()
        dev_id, sensor_name = 0, "vl53l8cx_tof"
        hsd.start_log(dev_id)
    except Exception:
        print("ERROR: DLL Locked. Re-plug the board.")
        return

    print("--- [ INITIALIZING 8x8 HIGH-RES VIEW ] ---")

    try:
        while True:
            # Drain buffer to get the latest burst
            latest_data = None
            while True:
                res = hsd.get_sensor_data(dev_id, sensor_name, 0)
                if res and res[1]:
                    latest_data = res[1]
                else:
                    break
            
            if latest_data:
                # 8x8 mode sends 64 zones. 64 zones * 8 values = 512 integers.
                raw_ints = np.frombuffer(bytearray(latest_data), dtype=np.uint32)
                
                # Check for an 8x8 frame (512 integers)
                if len(raw_ints) >= 512:
                    # Grab the last complete 64-zone frame
                    frame = raw_ints[-512:]
                    
                    # Distance is at index 5 of every 8-word block
                    distances = frame[5::8]
                    
                    if len(distances) == 64:
                        # Create 8x8 grid
                        grid = np.array(distances).reshape(8, 8)
                        
                        # Apply physical rotation
                        grid = np.fliplr(np.rot90(grid, k=3))
                        
                        os.system('cls' if os.name == 'nt' else 'clear')
                        print(f"--- [ 8x8 GRID | {time.strftime('%H:%M:%S')} ] ---")
                        print("Filter: > 2000mm hidden. Viewing 64 zones.\n")
                        
                        for r in range(8):
                            row = ""
                            for c in range(8):
                                v = int(grid[r, c])
                                # Show value only if within 2 meters
                                if 10 < v < 2000:
                                    row += f"{v:4d} "
                                else:
                                    row += " ..  "
                            print(row)
            
            time.sleep(1) # Refresh rate

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        hsd.stop_log(dev_id)

if __name__ == "__main__":
    main()