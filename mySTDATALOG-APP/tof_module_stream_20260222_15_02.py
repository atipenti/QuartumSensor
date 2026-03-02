import time
import json
import socket
import sys
import logging
import struct
import numpy as np

# --- PFAD-KONFIGURATION ---
SDK_BASE_PATH = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK"
if SDK_BASE_PATH not in sys.path:
    sys.path.append(SDK_BASE_PATH)

logging.getLogger('stdatalog_core').setLevel(logging.CRITICAL)

try:
    from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2
except ImportError:
    print("FEHLER: ST-SDK nicht gefunden.")
    sys.exit(1)

class TofStreamer:
    def __init__(self, host="127.0.0.1", port=5005):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.hsd = HSDLink_v2()
        self.dev_id = 0
        self.comp = "vl53l8cx_tof"
        self.send_interval = 0.05 # 20 Hz für stabile Anzeige
        self.last_send = 0
        
        # ZONE_REMAP: Passt die Sensor-Reihenfolge an das 4x4 GUI-Grid an
        # ST-Sensor schickt oft von unten nach oben oder gespiegelt.
        self.ZONE_REMAP = [12,13,14,15, 8,9,10,11, 4,5,6,7, 0,1,2,3]

    def start(self):
        print(f"[START] Streaming auf {self.host}:{self.port}...")
        self.hsd.send_command(self.dev_id, json.dumps({self.comp: {"enable": True}}))
        self.hsd.start_log(self.dev_id)

        try:
            while True:
                res = self.hsd.get_sensor_data(self.dev_id, self.comp, 0)
                if res and len(res) > 1 and res[1]:
                    # Wir nehmen den aktuellsten Datenblock (140 Bytes)
                    raw_data = res[1]
                    # Die relevanten 128 Bytes liegen zwischen Byte 4 und 132
                    # (Byte 0-3 ist der Counter, 132-140 ist Padding)
                    payload = np.frombuffer(raw_data[-140:][4:132], dtype=np.uint32)

                    if len(payload) >= 32:
                        data_map = {}
                        # Wir lesen die 16 Zonen strikt sequentiell aus
                        for i in range(16):
                            # In den Rohdaten: Index 2*i = Status, 2*i+1 = Distanz
                            s = int(payload[i*2])
                            d = int(payload[i*2 + 1])
                            
                            # Mapping auf die GUI-Anordnung
                            display_idx = self.ZONE_REMAP[i]
                            data_map[str(display_idx)] = {"d": d, "s": s}

                        # Zeitgesteuertes Senden (verhindert Buffer-Stau)
                        now = time.time()
                        if now - self.last_send >= self.send_interval:
                            self.sock.sendto(json.dumps(data_map).encode(), (self.host, self.port))
                            self.last_send = now

                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nBackend gestoppt.")
        finally:
            self.hsd.stop_log(self.dev_id)
            self.hsd.close()

if __name__ == "__main__":
    TofStreamer().start()