import sys
import os
import time
import json
from datetime import datetime
import pandas as pd

# SDK Pfade
SDK_BASE_PATH = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK"
sys.path.append(SDK_BASE_PATH)
sys.path.append(os.path.join(SDK_BASE_PATH, "HSDatalogApp"))

from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2
from stdatalog_core.HSD_pnpl.DeviceConfig import DeviceConfig # GUI Komponente

def main():
    hsd_link = HSDLink_v2()
    dev_id = 0
    comp_name = "vl53l8cx_tof"

    print("--- [ INITIALIZING ST GUI PIPELINE ] ---")

    try:
        # 1. Wir holen uns das 'Device Model' direkt vom Board
        # Das ist das, was die GUI beim Laden des "Devices" macht.
        device_template = hsd_link.get_device_info(dev_id)
        
        # 2. KONFIGURATION (PnPL Standard)
        # Wir schicken die Befehle, die GUI nutzt intern dieselbe Syntax
        hsd_link.send_command(dev_id, json.dumps({comp_name: {"resolution": 0}}))
        hsd_link.send_command(dev_id, json.dumps({comp_name: {"enable": True}}))
        
        # 3. STREAMING START
        hsd_link.start_log(dev_id)
        
        print("Pipeline stabil. Starte Datenextraktion...")
        
        all_data = []
        start_time = time.time()

        while (time.time() - start_time) < 15:
            # DER ENTSCHEIDENDE PUNKT:
            # Wir rufen get_sensor_data OHNE den Rohdaten-Parameter (0) auf.
            # Das SDK nutzt dann automatisch den internen Parser, der zum 
            # DeviceModel passt, das wir oben mit get_device_info getriggert haben.
            data_list = hsd_link.get_sensor_data(dev_id, comp_name)
            
            if data_list:
                for sample in data_list:
                    # Das SDK liefert hier nun fertig geparste Objekte (Dictionaries)
                    # Die Schlüssel 'distance' und 'status' kommen aus der DTDL!
                    if isinstance(sample, dict) and 'distance' in sample:
                        dist_values = sample['distance']
                        status_values = sample.get('status', [])
                        
                        # Wir filtern nur nach Status 5 (wie die GUI-Anzeige)
                        # und lassen das SDK die Arbeit machen.
                        clean_frame = [
                            d if (len(status_values) > i and status_values[i] == 5) else 2100 
                            for i, d in enumerate(dist_values)
                        ]
                        
                        ts = datetime.now().strftime("%H:%M:%S.%f")
                        all_data.append([ts] + clean_frame[:16])
            
            time.sleep(0.01)

        # 4. SPEICHERN
        if all_data:
            df = pd.DataFrame(all_data, columns=["Time"] + [f"z{i}" for i in range(16)])
            df.to_csv(f"ST_GUI_STYLE_LOG_{datetime.now().strftime('%H%M%S')}.csv", index=False)
            print(f"\nErfolg! {len(df)} Zeilen via GUI-Pipeline extrahiert.")
        else:
            print("\nFehler: Die Pipeline liefert keine geparsten Daten.")

    finally:
        hsd_link.stop_log(dev_id)
        hsd_link.close()

if __name__ == "__main__":
    main()