import time
import json
import numpy as np
import os
import sys

# Pfade zum SDK
SDK_BASE_PATH = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK"
sys.path.append(SDK_BASE_PATH)
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

def analyze_posture(distances, statuses):
    valid_mask = (statuses == 5)
    clean_data = np.where(valid_mask, distances, 2500)
    grid = clean_data.reshape(4, 4)
    
    left_side = grid[:, :2].mean()
    right_side = grid[:, 2:].mean()
    center = grid[1:3, 1:3].mean()
    
    if center > 1800: return "NIEMAND DA", center
    if abs(left_side - right_side) < 180: return "PERFEKT (Mittig)", center
    return "NACH RECHTS RÜCKEN" if left_side < right_side else "NACH LINKS RÜCKEN", center

def run_live_monitor():
    hsd = HSDLink_v2()
    dev_id, comp = 0, "vl53l8cx_tof"
    
    try:
        hsd.send_command(dev_id, json.dumps({comp: {"enable": True}}))
        hsd.start_log(dev_id)
        
        while True:
            res = hsd.get_sensor_data(dev_id, comp, 0)
            if res and len(res) > 1 and res[1]:
                buffer = res[1]
                
                # Wir suchen das Ende des letzten validen Pakets (140 Bytes)
                # Ein valides Paket endet oft mit einem Zeitstempel oder 0-Padding.
                # Um das "Wandern" zu stoppen, nehmen wir den Buffer und suchen von hinten 
                # nach einem konsistenten Muster (Padding/Header).
                if len(buffer) >= 140:
                    # Wir nehmen die letzten 140 Bytes, aber richten sie aus
                    raw_packet = buffer[-(len(buffer)%140 if len(buffer)%140 != 0 else 140):]
                    # Falls der Rest zu klein ist, nehmen wir das Paket davor
                    raw_packet = buffer[-140:] 
                    
                    payload = np.frombuffer(raw_packet[4:132], dtype=np.uint32)
                    stat = payload[0::2][:16]
                    dist = payload[1::2][:16]

                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"ST-TOF LIVE MONITOR | {time.strftime('%H:%M:%S')}")
                    print("=" * 45)
                    
                    for i in range(0, 16, 4):
                        row = ""
                        for j in range(4):
                            d, s = dist[i+j], stat[i+j]
                            # Filtern von Ausreißern (Riesenzahlen)
                            if s == 5 and d < 4000:
                                row += f" {d:4d}mm |"
                            else:
                                row += "  ---  |"
                        print(row)
                    
                    msg, avg_dist = analyze_posture(dist, stat)
                    print("=" * 45)
                    print(f"HALTUNG: {msg}")
                    print(f"ABSTAND: {avg_dist:.0f} mm")
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nMonitor gestoppt.")
    finally:
        hsd.stop_log(dev_id); hsd.close()

if __name__ == "__main__":
    run_live_monitor()