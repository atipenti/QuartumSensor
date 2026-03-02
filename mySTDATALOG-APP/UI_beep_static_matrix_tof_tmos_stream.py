import sys, os, time, struct, logging
import numpy as np

logging.getLogger('stdatalog_core').setLevel(logging.ERROR)
sdk_root = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK\stdatalog_core"
if sdk_root not in sys.path: sys.path.insert(0, sdk_root)
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

def get_latest_synced_frame(raw_data):
    """
    Scans the buffer from the end to find the most recent 136-byte packet.
    Matches the Status 5 pattern to ensure Zone 0 is always Index 0.
    """
    # Packet is 136 bytes. We need at least that much.
    if len(raw_data) < 136: return None
    
    # Scan backwards to get the 'newest' data
    for i in range(len(raw_data) - 136, -1, -1):
        # STWIN VL53L8CX structure: [Header(4b), Status0(4b), Dist0(4b), ...]
        # We look for Status 5 in the first zone (offset i+4)
        s, d = struct.unpack('<II', raw_data[i+4:i+12])
        if s == 5 and 100 < d < 4500:
            # Found a sync lock! Extract 16 zones.
            frame = []
            for z in range(16):
                z_off = i + 4 + (z * 8)
                stat, dist = struct.unpack('<II', raw_data[z_off : z_off+8])
                frame.append(dist if stat == 5 else 2200)
            return frame
    return None

def apply_gui_orientation(frame_list):
    """270 deg rotation + Horizontal Flip"""
    grid = np.array(frame_list).reshape(4, 4)
    grid = np.rot90(grid, k=3) # 270 deg
    grid = np.fliplr(grid)      # Horizontal Flip
    return grid

def main():
    hsd_link = HSDLink_v2()
    devices = hsd_link.get_devices()
    dev_id = 0 if isinstance(devices, list) else list(devices.keys())[0]
    hsd_link.start_log(dev_id)
    
    print("HARD-SYNC ACTIVE. Waiting for snapshot...")

    try:
        while True:
            # 1. Grab everything currently in the USB buffer
            res = hsd_link.get_sensor_data(dev_id, "vl53l8cx_tof", 0)
            
            if res and res[1]:
                # 2. Extract the newest packet using pattern matching
                frame = get_latest_synced_frame(res[1])
                
                if frame:
                    # 3. Orient to match your GUI view
                    oriented_grid = apply_gui_orientation(frame)
                    
                    os.system('cls')
                    print(f"--- [ SYNC-LOCKED VIEW | {time.strftime('%H:%M:%S')} ] ---")
                    print("Status: Fixed Alignment (No Jumping)\n")
                    
                    for r in range(4):
                        row_str = ""
                        for c in range(4):
                            val = oriented_grid[r, c]
                            # Only show if below 1900mm
                            if val < 1900:
                                row_str += f" {val:4d}  "
                            else:
                                row_str += " ....  "
                        print(row_str + "\n")
                    print("-" * 38)

            # Snapshot interval
            time.sleep(3)

    except KeyboardInterrupt:
        hsd_link.stop_log(dev_id)

if __name__ == "__main__":
    main()