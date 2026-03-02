import time, json, socket, sys
import numpy as np

# Pfad zum SDK
sys.path.append(r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK")
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

class ToFBackendFast:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.FRAME_SIZE = 1288 
        self.hsd = None

    def start(self):
        try:
            self.hsd = HSDLink_v2()
            self.hsd.send_command(0, json.dumps({"vl53l8cx_tof": {"enable": True}}))
            self.hsd.start_log(0)
            print("Fast-Sync Backend aktiv. Springe immer zum neuesten Frame...")

            buffer = bytearray()
            while True:
                res = self.hsd.get_sensor_data(0, "vl53l8cx_tof", 0)
                if res and len(res) > 1 and res[1]:
                    buffer.extend(res[1])
                    
                    # Wenn sich zu viele Daten stauen (> 3 Frames), löschen wir den alten Ballast
                    if len(buffer) > self.FRAME_SIZE * 3:
                        # Behalte nur die letzten 1288 Bytes
                        buffer = buffer[-self.FRAME_SIZE:]

                    if len(buffer) >= self.FRAME_SIZE:
                        # Wir nehmen exakt einen Frame vom Ende
                        frame = buffer[-self.FRAME_SIZE:]
                        buffer.clear() # Puffer für den nächsten USB-Read leeren

                        # Sample 9 (das aktuellste) extrahieren
                        sample_bytes = frame[1152:1280]
                        data = np.frombuffer(sample_bytes, dtype=np.uint32)
                        
                        zones = {}
                        for z in range(16):
                            v1, v2 = int(data[2*z]), int(data[2*z+1])
                            # Smart Swap: Status ist klein, Distanz groß
                            status, dist = (v1, v2) if v1 < 255 else (v2, v1)
                            zones[str(z)] = {"s": status, "d": dist}
                        
                        self.sock.sendto(json.dumps(zones).encode(), ("127.0.0.1", 5005))
                
                # Sehr kurze Pause, um die CPU nicht zu grillen, aber schneller als der Sensor
                time.sleep(0.002) 

        except Exception as e:
            print(f"Fehler: {e}")
        finally:
            if self.hsd: self.hsd.close()

if __name__ == "__main__":
    ToFBackendFast().start()