import time
import json
import socket
import sys
import struct
import numpy as np

# SDK Pfad anpassen
sys.path.append(r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK")
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

class ToFSTFinalBackend:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.UDP_IP = "127.0.0.1"
        self.UDP_PORT = 5005
        
        self.COMP_NAME = "vl53l8cx_tof"
        self.LOG_FILENAME = "tof_st_format_final.dat"
        self.USB_DPS = 136    
        self.DIMENSIONS = 11  # Festgelegt durch device_config.json
        self.hsd = None
        self.total_bytes_logged = 0

    def start(self):
        try:
            self.hsd = HSDLink_v2()
            self.hsd.send_command(0, json.dumps({self.COMP_NAME: {"enable": True}}))
            self.hsd.start_log(0)
            print(f"Backend aktiv. Sende an {self.UDP_PORT}...")

            with open(self.LOG_FILENAME, "wb") as log_file:
                while True:
                    res = self.hsd.get_sensor_data(0, self.COMP_NAME, 0)
                    if res and len(res) > 1 and res[1]:
                        raw_payload = res[1]

                        # 1. ST-FORMAT SPEICHERUNG (Wichtig für Validator)
                        for i in range(0, len(raw_payload), self.USB_DPS):
                            chunk = raw_payload[i : i + self.USB_DPS]
                            if len(chunk) == self.USB_DPS:
                                header = struct.pack("<I", self.total_bytes_logged)
                                log_file.write(header + chunk)
                                self.total_bytes_logged += self.USB_DPS

                        # 2. KORRIGIERTE EXTRAKTION
                        # Der Validator-Fehler zeigt: Distanz und Status sind vertauscht oder verschoben.
                        # Wir nutzen np.frombuffer ab Byte 8 (hinter dem Zeitstempel)
                        if len(raw_payload) > 8:
                            payload_data = raw_payload[8:]
                            float_data = np.frombuffer(payload_data, dtype=np.float32)
                            
                            zones = {}
                            # Wir haben 16 Zonen (4x4)
                            for z in range(16):
                                # Basierend auf dem Validator-Log: 
                                # Wenn 'd': 5 und 's': 2185 steht, ist Index 0 der Status 
                                # und Index 1 die Distanz innerhalb des Zonen-Blocks.
                                base = z * self.DIMENSIONS
                                if base + 1 < len(float_data):
                                    # TAUSCH: Wir setzen den Wert, der vorher 2185 war (Distanz), in 'd'
                                    dist = float(float_data[base + 1]) 
                                    stat = int(float_data[base + 0])
                                    
                                    zones[z] = {"d": dist, "s": stat}
                            
                            if zones:
                                self.sock.sendto(json.dumps(zones).encode(), (self.UDP_IP, self.UDP_PORT))

                    time.sleep(0.005)
        except KeyboardInterrupt:
            print("\nStop.")
        finally:
            if self.hsd:
                self.hsd.stop_log(0)
                self.hsd.close()

if __name__ == "__main__":
    backend = ToFSTFinalBackend()
    backend.start()