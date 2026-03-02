import sys
import os
import time
import json

# Pfade zu deinem SDK
SDK_BASE_PATH = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK"
sys.path.append(SDK_BASE_PATH)
sys.path.append(os.path.join(SDK_BASE_PATH, "HSDatalogApp"))

from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

def run_tui_style_logger(duration=10):
    # 1. Initialisierung wie in TUI (HSDLink_v2)
    hsd_link = HSDLink_v2()
    dev_id = 0
    comp_name = "vl53l8cx_tof"
    output_file = "my_manual_test_tof.dat"

    print(f"--- [ TUI CALL-CHAIN REPLICA ] ---")

    try:
        # 2. Konfiguration (PnPL)
        # TUI sendet diese Befehle via hsd_link.send_command
        hsd_link.send_command(dev_id, json.dumps({comp_name: {"resolution": 0}})) # 4x4
        hsd_link.send_command(dev_id, json.dumps({comp_name: {"enable": True}}))
        
        # 3. Start Log
        hsd_link.start_log(dev_id)
        print(f"Logging gestartet für {duration}s...")

        with open(output_file, "wb") as f:
            start_time = time.time()
            while (time.time() - start_time) < duration:
                # Hier kopieren wir die TUI-Logik: 
                # get_sensor_data(..., 0) liefert die nackten USB-Pakete
                res = hsd_link.get_sensor_data(dev_id, comp_name, 0)
                
                if res and len(res) > 1 and res[1] is not None:
                    # res[1] enthält die Roh-Bytes des USB-Streams
                    f.write(res[1])
                
                time.sleep(0.01) # Kleiner Sleep wie in der TUI-Loop

        print(f"Logging beendet. Datei gespeichert: {output_file}")

    finally:
        hsd_link.stop_log(dev_id)
        hsd_link.close()

if __name__ == "__main__":
    run_tui_style_logger(10)