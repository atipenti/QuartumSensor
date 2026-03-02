import sys
import os
import argparse
import time

# --- SDK PATH CONFIGURATION ---
sdk_root = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK\stdatalog_core"
if sdk_root not in sys.path:
    sys.path.insert(0, sdk_root)

try:
    from stdatalog_core.HSD_utils.DataReader import DataReader
    from stdatalog_core.HSD_link.HSDLink import HSDLink
except ImportError as e:
    print(f"Error: Could not find SDK components. Path: {sdk_root}")
    sys.exit(1)

os.system('') # Enable ANSI for Windows

class DataPacketWrapper:
    def __init__(self, raw_bytes):
        self.data = raw_bytes

RES = 8 

def my_output_function(data_packet):
    comp_name = data_packet.comp_name
    data_dict = data_packet.data
    print("\033[H", end="") # Home cursor
    
    if "tof" in comp_name:
        print(f"--- [ ToF {RES}x{RES} LIVE DEPTH MAP ] ---")
        grid_output = ""
        valid_distances = []
        num_zones = RES * RES
        for i in range(num_zones):
            dist = data_dict[i][0] if i in data_dict else 0
            if 10 < dist < 4000:
                valid_distances.append(dist)
                if dist < 300:     symbol = "██" 
                elif dist < 800:   symbol = "▓▓" 
                elif dist < 2000:  symbol = "░░" 
                else:              symbol = ".. " 
            else:
                symbol = "   "
            grid_output += symbol + " "
            if (i + 1) % RES == 0: grid_output += "\n"
        print(grid_output)
        avg = sum(valid_distances)/len(valid_distances) if valid_distances else 0
        print(f"Avg Dist: {avg:4.0f} mm | Active Zones: {len(valid_distances)}/{num_zones}      ")

    elif "tmos" in comp_name:
        presence = "DETECTED" if data_dict.get(1, [0])[0] > 0 else "empty   "
        motion   = "MOVING  " if data_dict.get(2, [0])[0] > 0 else "STILL   "
        v_pos = 13 if RES == 8 else 9
        print(f"\033[{v_pos};0H>> [TMOS] Presence: {presence} | Activity: {motion}          ")

def main():
    global RES
    parser = argparse.ArgumentParser()
    parser.add_argument('--res', type=int, choices=[4, 8], default=4)
    args = parser.parse_args()
    RES = args.res

    # 1. Properly initialize the link using the Factory method
    hsd_factory = HSDLink()
    hsd_link = hsd_factory.create_hsd_link() # This returns HSDLink_v2 for STWIN.box
    
    if hsd_link is None:
        print("Device not found. Please re-plug the STWIN.box.")
        return
    
    device_id = 0
    res_enum = 1 if RES == 8 else 0

    # 2. Set Resolution using the static method correctly
    # Note: Your HSDLink.py @staticmethod set_property(self, ...) is a bit unusual,
    # we pass 'hsd_link' as the first argument to satisfy that 'self' parameter.
    try:
        HSDLink.set_property(hsd_link, device_id, res_enum, "vl53l8cx_tof", "resolution")
    except Exception as e:
        print(f"Hardware Config Note: {e}")

    # 3. Setup Readers
    # samples_per_ts = 0 is mandatory for raw bytes (avoids 8-byte timestamp shift)
    tof_dr = DataReader(my_output_function, "vl53l8cx_tof", 0, (RES*RES)*2, 2, 'H')
    tmos_dr = DataReader(my_output_function, "sths34pf80_tmos", 0, 3, 2, 'h')

    print("\033[2J\033[H", end="") # Clear
    hsd_link.start_log(device_id)
    
    try:
        while True:
            # Poll ToF
            res_tof = hsd_link.get_sensor_data(device_id, "vl53l8cx_tof", 0)
            if res_tof and len(res_tof) > 1 and res_tof[1] is not None:
                tof_dr.feed_data(DataPacketWrapper(res_tof[1]))
                
            # Poll TMOS
            res_tmos = hsd_link.get_sensor_data(device_id, "sths34pf80_tmos", 0)
            if res_tmos and len(res_tmos) > 1 and res_tmos[1] is not None:
                tmos_dr.feed_data(DataPacketWrapper(res_tmos[1]))
                
            time.sleep(0.005)
    except KeyboardInterrupt:
        hsd_link.stop_log(device_id)
        print("\nStream stopped.")

if __name__ == "__main__":
    main()