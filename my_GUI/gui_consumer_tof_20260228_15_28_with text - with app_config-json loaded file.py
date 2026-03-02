import socket
import json
import threading
import numpy as np
import os

class MultiSensorConsumer:
    def __init__(self):
        # --- PATH SETUP ---
        # Get the directory where THIS script is located
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        app_cfg_path = os.path.join(self.base_dir, 'app_config.json')
        dev_cfg_path = os.path.join(self.base_dir, 'device_config.json')

        # 1. Load Application Config (Ports, IP, UI orientation)
        print(f"[INIT] Loading App Config: {app_cfg_path}")
        with open(app_cfg_path, 'r') as f:
            self.app_config = json.load(f)
            
        # 2. Load Device Config (Sensor resolution: 4x4 or 8x8)
        print(f"[INIT] Loading Device Config: {dev_cfg_path}")
        with open(dev_cfg_path, 'r') as f:
            self.dev_config = json.load(f)
            
        self.threads = []
        # Detect if we are in 4x4 or 8x8 mode from the device_config
        self.tof_resolution = self._detect_tof_resolution()

    def _detect_tof_resolution(self):
        """
        Parses device_config.json to find VL53L8 resolution.
        ST Convention: 0 = 4x4, 1 = 8x8
        """
        try:
            components = self.dev_config.get("device", {}).get("components", [])
            for comp in components:
                if comp.get("name") == "VL53L8_ToF":
                    res_value = comp.get("content", {}).get("resolution", 0)
                    actual_dim = 4 if res_value == 0 else 8
                    return actual_dim
        except Exception as e:
            print(f"[ERROR] Resolution detection failed: {e}")
        
        return 4 # Default fallback

    def start_listening(self):
        sensors = self.app_config["network_config"]["sensors"]
        ip = self.app_config["network_config"]["ip"]

        print(f"\n--- SYSTEM READY ---")
        print(f"[*] Detected ToF Resolution: {self.tof_resolution}x{self.tof_resolution}")
        
        for name, settings in sensors.items():
            if settings.get("enabled"):
                t = threading.Thread(target=self.sensor_worker, args=(name, ip, settings))
                t.daemon = True
                t.start()
                self.threads.append(t)
        
        print(f"[*] Consumer Running. Press Enter to stop...\n")
        input()

    def sensor_worker(self, sensor_name, ip, settings):
        """Background thread for UDP reception"""
        port = settings["port"]
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((ip, port))
        print(f"[LISTENING] {sensor_name} on port {port}")

        while True:
            try:
                data, addr = sock.recvfrom(8192)
                payload = json.loads(data)
                
                if sensor_name == "VL53L8_ToF":
                    if "data" in payload:
                        self.process_tof(payload, settings)
            except Exception as e:
                print(f"[THREAD ERROR] {sensor_name}: {e}")

    def process_tof(self, payload, settings):
        """Processes the list into a matrix and applies UI transforms"""
        data_list = payload["data"]
        
        dim = self.tof_resolution
        expected_size = dim * dim
        
        # Security: ensure we have enough data for the matrix
        if len(data_list) < expected_size:
            return

        # Take primary targets and reshape
        matrix = np.array(data_list[:expected_size]).reshape((dim, dim))
        
        # 1. Apply Rotation (k = number of 90 deg steps)
        matrix = np.rot90(matrix, k=settings.get("rotation", 0))
        
        # 2. Apply Flips
        if settings.get("flip_x"): matrix = np.flip(matrix, axis=0)
        if settings.get("flip_y"): matrix = np.flip(matrix, axis=1)
        
        # 3. Print Results (Center zone and Average)
        avg_dist = np.mean(matrix)
        center_val = matrix[dim//2, dim//2]
        print(f"[{dim}x{dim}] Avg: {avg_dist:.1f}mm | Center: {center_val:.0f}mm")

if __name__ == "__main__":
    consumer = MultiSensorConsumer()
    consumer.start_listening()