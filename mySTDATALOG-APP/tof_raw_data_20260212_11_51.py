import time
import json
import numpy as np
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

hsd = HSDLink_v2()
dev_id = 0
comp = "vl53l8cx_tof"

# Sensor frisch starten
hsd.send_command(dev_id, json.dumps({comp: {"enable": True}}))
hsd.start_log(dev_id)

print("SUCHE DICH... (Bewege deine Hand vor dem Sensor)")

try:
    while True:
        # Wir holen die Rohdaten
        res = hsd.get_sensor_data(dev_id, comp, 0)
        if res and len(res) > 1 and res[1]:
            payload = res[1][-140:] # Hol das letzte Paket
            data = np.frombuffer(payload[4:132], dtype=np.uint32)
            dist = data[1::2]
            stat = data[0::2]
            
            # Zeichne 4x4 Grid
            output = "\033[H" # Terminal Cursor nach oben
            for i in range(0, 16, 4):
                row = ""
                for j in range(4):
                    d, s = dist[i+j], stat[i+j]
                    row += f"{d:4d}({s}) | " # Zeigt Distanz und Status in Klammern
                print(row)
            print("-" * 30)
        time.sleep(0.5)
except KeyboardInterrupt:
    hsd.stop_log(dev_id)
    hsd.close()