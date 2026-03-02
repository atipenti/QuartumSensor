import time
import json
import numpy as np
import os
import sys
import logging

# 1. SDK LOGGING DEAKTIVIEREN (Wichtig gegen das Wandern/Zerschießen)
logging.getLogger('HSDatalogApp').setLevel(logging.WARNING)
logging.getLogger('stdatalog_core').setLevel(logging.WARNING)

# SDK Pfad
SDK_BASE_PATH = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK"
sys.path.append(SDK_BASE_PATH)
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

def run_professional_monitor():
    hsd = HSDLink_v2()
    dev_id = 0
    comp = "vl53l8cx_tof"
    WALL_THRESHOLD = 1600 # Filtert alles hinter 1,6m weg
    
    # Initialisierung der Variablen (verhindert NameError)
    grid = np.zeros((4, 4))
    stat = np.zeros((4, 4))
    
    # Hardware Aktivierung via PnPL
    hsd.send_command(dev_id, json.dumps({comp: {"enable": True}}))
    hsd.start_log(dev_id)

    packet_size = 140 
    stream_buffer = bytearray()

    # ANSI Escape: Cursor verstecken
    print("\033[?25l", end="") 

    try:
        while True:
            res = hsd.get_sensor_data(dev_id, comp, 0)
            
            if res and len(res) > 1 and res[1]:
                stream_buffer.extend(res[1])
                
                while len(stream_buffer) >= packet_size:
                    packet = stream_buffer[:packet_size]
                    stream_buffer = stream_buffer[packet_size:]
                    
                    payload = np.frombuffer(packet[4:132], dtype=np.uint32)
                    
                    # Rohdaten (Paare aus Status und Distanz)
                    dist_raw = payload[1::2][:16]
                    stat_raw = payload[0::2][:16]
                    
                    # In 4x4 Grid wandeln
                    grid_tmp = dist_raw.reshape(4, 4)
                    stat_tmp = stat_raw.reshape(4, 4)

                    # --- TRANSFORMATION ---
                    # 1. Rotation 270°
                    grid_tmp = np.rot90(grid_tmp, k=3)
                    stat_tmp = np.rot90(stat_tmp, k=3)
                    # 2. Horizontal Flip
                    grid = np.fliplr(grid_tmp)
                    stat = np.fliplr(stat_tmp)

                    # --- ANZEIGE (Flicker-frei) ---
                    # Wir nutzen os.system('cls') um SDK-Reste wegzuputzen
                    os.system('cls' if os.name == 'nt' else 'clear')
                    
                    print(f"ST-TOF SILHOUETTE | {time.strftime('%H:%M:%S')}")
                    print(f"Filter: < {WALL_THRESHOLD}mm | Rotation: 270 | Flip: H")
                    print("=" * 48)
                    
                    for r in range(4):
                        row_str = "  "
                        for c in range(4):
                            d, s = grid[r, c], stat[r, c]
                            # Filter: Status OK und Distanz kleiner als Wand
                            if s in [5, 9] and d < WALL_THRESHOLD and d > 0:
                                row_str += f"{int(d):4d} mm  | "
                            else:
                                row_str += "        | "
                        print(row_str)
                    print("=" * 48)
                    print("Drücke Strg+C zum Beenden...")
                    
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\033[?25h") 
        print("\nMonitor gestoppt.")
    finally:
        hsd.stop_log(dev_id)
        hsd.send_command(dev_id, json.dumps({comp: {"enable": False}}))
        hsd.close()

if __name__ == "__main__":
    run_professional_monitor()