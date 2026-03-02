import sys
import os
import argparse
import time
import winsound

# --- SDK PATH ---
sdk_root = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK\stdatalog_core"
if sdk_root not in sys.path:
    sys.path.insert(0, sdk_root)

try:
    from stdatalog_core.HSD_utils.DataReader import DataReader
    from stdatalog_core.HSD_link.HSDLink import HSDLink
except ImportError:
    print("SDK Not Found.")
    sys.exit(1)

os.system('') # ANSI Fix

class DataPacketWrapper:
    def __init__(self, raw_bytes):
        self.data = raw_bytes

# CONFIG
RES = 8 
PEAK_THRESHOLD = 400  # 40cm
LAST_BEEP_TIME = 0
MIN_DIST_DETECTED = 9999

def my_output_function(data_packet):
    global LAST_BEEP_TIME, MIN_DIST_DETECTED
    comp_name = data_packet.comp_name
    data_dict = data_packet.data
    
    # Home Cursor
    print("\033[H", end="") 
    
    if "tof" in comp_name:
        print(f"--- [ ToF {RES}x{RES} LIVE DEPTH MAP ] ---")
        grid_output = ""
        valid_distances = []
        alert_triggered = False
        
        for i in range(RES * RES):
            dist = data_dict[i][0] if i in data_dict else 0
            
            if 10 < dist < 4000:
                valid_distances.append(dist)
                # Logic for Beep/Alert
                if dist < PEAK_THRESHOLD:
                    alert_triggered = True
                    symbol = "!!" 
                elif dist < 300:     symbol = "██" 
                elif dist < 800:     symbol = "▓▓" 
                elif dist < 2000:    symbol = "░░" 
                else:                symbol = ".. " 
            else:
                symbol = "   "
            
            grid_output += symbol + " "
            if (i + 1) % RES == 0: grid_output += "\n"
        
        # Update Min Distance for debugging
        if valid_distances:
            MIN_DIST_DETECTED = min(valid_distances)
        
        print(grid_output)
        
        # Visual Alarm Message
        if alert_triggered:
            print(f"\033[1;41;37m !!! PEAK DETECTED !!! \033[0m   ") # White on Red
            if (time.time() - LAST_BEEP_TIME > 0.6):
                winsound.Beep(500, 200) 
                LAST_BEEP_TIME = time.time()
        else:
            print(" Monitoring...           ")

    elif "tmos" in comp_name:
        presence = "DETECTED" if data_dict.get(1, [0])[0] > 0 else "empty   "
        v_pos = 14 if RES == 8 else 10
        print(f"\033[{v_pos};0H>> [TMOS] Presence: {presence} | [DEBUG] Min ToF Dist: {MIN_DIST_DETECTED:4.0f}mm    ")

    elif "als" in comp_name:
        lux_value = data_dict.get(4, [0])[0]
        v_pos = 15 if RES == 8 else 11
        print(f"\033[{v_pos};0H>> [ALS] Light Level: {lux_value:6.0f} lux              ")

def main():
    global RES
    parser = argparse.ArgumentParser()
    parser.add_argument('--res', type=int, choices=[4, 8], default=4)
    args = parser.parse_args()
    RES = args.res

    hsd_factory = HSDLink()
    hsd_link = hsd_factory.create_hsd_link()
    
    if hsd_link is None: return
    
    device_id = 0
    res_enum = 1 if RES == 8 else 0

    try:
        HSDLink.set_property(hsd_link, device_id, res_enum, "vl53l8cx_tof", "resolution")
    except: pass

    # Data Readers
    tof_dr = DataReader(my_output_function, "vl53l8cx_tof", 0, (RES*RES)*2, 2, 'H')
    tmos_dr = DataReader(my_output_function, "sths34pf80_tmos", 0, 3, 2, 'h')
    als_dr = DataReader(my_output_function, "vd6283tx_als", 0, 6, 4, 'I')

    print("\033[2J\033[H", end="") # Clear
    hsd_link.start_log(device_id)
    
    try:
        while True:
            # Poll Sensors
            r_t = hsd_link.get_sensor_data(device_id, "vl53l8cx_tof", 0)
            if r_t and len(r_t) > 1 and r_t[1]: tof_dr.feed_data(DataPacketWrapper(r_t[1]))
            
            r_m = hsd_link.get_sensor_data(device_id, "sths34pf80_tmos", 0)
            if r_m and len(r_m) > 1 and r_m[1]: tmos_dr.feed_data(DataPacketWrapper(r_m[1]))

            r_a = hsd_link.get_sensor_data(device_id, "vd6283tx_als", 0)
            if r_a and len(r_a) > 1 and r_a[1]: als_dr.feed_data(DataPacketWrapper(r_a[1]))
            
            time.sleep(0.005)
    except KeyboardInterrupt:
        hsd_link.stop_log(device_id)

if __name__ == "__main__":
    main()