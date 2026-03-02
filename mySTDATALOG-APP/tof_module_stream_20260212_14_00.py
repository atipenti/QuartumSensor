import time
import json
import socket
import sys
import logging
import numpy as np

# --- PFAD-KONFIGURATION ---
SDK_BASE_PATH = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK"
if SDK_BASE_PATH not in sys.path:
    sys.path.append(SDK_BASE_PATH)

# --- LOGGING UNTERDRÜCKEN ---
# Verhindert, dass SDK-Meldungen den Datenfluss stören
logging.getLogger().handlers = []
logging.getLogger('stdatalog_core').setLevel(logging.CRITICAL)
logging.getLogger('HSDatalogApp').setLevel(logging.CRITICAL)

try:
    from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2
except ImportError:
    print("FEHLER: ST-SDK nicht gefunden. Pfad prüfen!")
    sys.exit(1)

class ToFBackendIndexed:
    def __init__(self, host="127.0.0.1", port=5005):
        self.host = host
        self.port = port
        self.dev_id = 0
        self.comp = "vl53l8cx_tof"
        self.packet_size = 140 # 4 Bytes Header + 128 Bytes Data + 8 Bytes Footer
        self.hsd = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def start(self):
        try:
            self.hsd = HSDLink_v2()
            # Sensor aktivieren
            self.hsd.send_command(self.dev_id, json.dumps({self.comp: {"enable": True}}))
            self.hsd.start_log(self.dev_id)
            
            print(f"Backend aktiv. Sende ID-gemappte Daten an {self.host}:{self.port}")
            print("Dieses Fenster bleibt leer. Schließe es mit Strg+C.")

            while True:
                res = self.hsd.get_sensor_data(self.dev_id, self.comp, 0)
                
                if res and len(res) > 1 and res[1]:
                    # Synchronisations-Trick: Wir nehmen nur das letzte vollständige Paket
                    # Das verhindert, dass wir alten Daten hinterherlaufen (Lag)
                    data_chunk = res[1]
                    if len(data_chunk) >= self.packet_size:
                        # Die letzten 140 Bytes extrahieren
                        packet = data_chunk[-self.packet_size:]
                        
                        # Byte 4 bis 132 enthalten die ToF Daten (32-bit Integers)
                        payload = np.frombuffer(packet[4:132], dtype=np.uint32)
                        
                        # VL53L8CX liefert: [Status0, Dist0, Status1, Dist1, ...]
                        stat_flat = payload[0::2][:16]
                        dist_flat = payload[1::2][:16]
                        
                        # Wir bauen ein ID-Mapping: "0": {"d": 1200, "s": 5}
                        # Das Frontend nutzt diese IDs, um die Werte fest zu platzieren
                        data_map = {}
                        for i in range(16):
                            data_map[str(i)] = {
                                "d": int(dist_flat[i]),
                                "s": int(stat_flat[i])
                            }
                        
                        # Senden per UDP
                        self.sock.sendto(json.dumps(data_map).encode(), (self.host, self.port))
                
                # Kurze Pause, um die CPU nicht auf 100% zu jagen
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nBackend wird gestoppt...")
        except Exception as e:
            print(f"\nFehler im Backend: {e}")
        finally:
            if self.hsd:
                self.hsd.stop_log(self.dev_id)
                self.hsd.send_command(self.dev_id, json.dumps({self.comp: {"enable": False}}))
                self.hsd.close()
            self.sock.close()

if __name__ == "__main__":
    backend = ToFBackendIndexed()
    backend.start()