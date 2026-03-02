import time, json, sys, struct
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2

# Konfiguration
SDK_PATH = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK"
sys.path.append(SDK_PATH)

FILENAME = "sensor_v2.dat"
PACKET_PAYLOAD_SIZE = 136 

class STDataRecorderV2:
    def __init__(self):
        self.hsd = HSDLink_v2()
        self.total_bytes_written = 0

    def start(self):
        self.hsd.send_command(0, json.dumps({"vl53l8cx_tof": {"enable": True}}))
        self.hsd.start_log(0)
        
        print(f"Recording gestartet -> {FILENAME}")
        print("BEWEGE dich vor dem Sensor (Hand nähern/entfernen)!")

        with open(FILENAME, "wb") as f:
            try:
                while True:
                    res = self.hsd.get_sensor_data(0, "vl53l8cx_tof", 0)
                    if res and len(res) > 1 and res[1]:
                        raw_payload = res[1]
                        for i in range(0, len(raw_payload), PACKET_PAYLOAD_SIZE):
                            chunk = raw_payload[i:i+PACKET_PAYLOAD_SIZE]
                            if len(chunk) == PACKET_PAYLOAD_SIZE:
                                header = struct.pack("<I", self.total_bytes_written)
                                f.write(header)
                                f.write(chunk)
                                self.total_bytes_written += PACKET_PAYLOAD_SIZE
                time.sleep(0.001)
            except KeyboardInterrupt:
                print(f"\nFertig! {self.total_bytes_written} Bytes geschrieben.")
                self.hsd.stop_log(0)
                self.hsd.close()

if __name__ == "__main__":
    STDataRecorderV2().start()