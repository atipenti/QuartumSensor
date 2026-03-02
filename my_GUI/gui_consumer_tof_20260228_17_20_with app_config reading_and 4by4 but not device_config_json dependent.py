import socket
import json
import threading
import numpy as np
import os
import pygame

class MultiSensorConsumer:
    def __init__(self):
        # --- PATH SETUP ---
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        app_cfg_path = os.path.join(self.base_dir, 'app_config.json')
        dev_cfg_path = os.path.join(self.base_dir, 'device_config.json')

        # 1. Load Application Config (Ports, IP, UI orientation)
        print(f"[INIT] Loading App Config: {app_cfg_path}")
        with open(app_cfg_path, 'r') as f:
            self.app_config = json.load(f)
            
        # 2. Load Device Config (Sensor resolution)
        print(f"[INIT] Loading Device Config: {dev_cfg_path}")
        with open(dev_cfg_path, 'r') as f:
            self.dev_config = json.load(f)
            
        # --- DATA & UI SETUP ---
        self.tof_resolution = self._detect_tof_resolution()
        self.last_matrix = None
        self.lock = threading.Lock()
        
        # Pygame Config
        self.window_size = 600
        pygame.init()
        self.screen = pygame.display.set_mode((self.window_size, self.window_size))
        pygame.display.set_caption(f"🚀 ToF Live Heatmap - {self.tof_resolution}x{self.tof_resolution}")
        self.font = pygame.font.SysFont("Arial", 22, bold=True)
        
        self.threads = []

    def _detect_tof_resolution(self):
        """Detect 4x4 or 8x8 mode from device_config.json"""
        try:
            components = self.dev_config.get("device", {}).get("components", [])
            for comp in components:
                if comp.get("name") == "VL53L8_ToF":
                    res_value = comp.get("content", {}).get("resolution", 0)
                    return 4 if res_value == 0 else 8
        except Exception as e:
            print(f"[ERROR] Resolution detection failed: {e}")
        return 4

    def start(self):
        """Starts background threads and the main UI loop"""
        sensors = self.app_config["network_config"]["sensors"]
        ip = self.app_config["network_config"]["ip"]

        print(f"\n--- SYSTEM READY ---")
        print(f"[*] Detected ToF Resolution: {self.tof_resolution}x{self.tof_resolution}")
        
        # Start UDP listener thread
        for name, settings in sensors.items():
            if settings.get("enabled"):
                t = threading.Thread(target=self.sensor_worker, args=(name, ip, settings))
                t.daemon = True
                t.start()
                self.threads.append(t)
        
        # Main Pygame Loop (Must run in main thread)
        self.run_ui_loop()

    def sensor_worker(self, sensor_name, ip, settings):
        # Print once at startup to verify what was loaded
        print(f"--- [DEBUG] Worker Started for {sensor_name} ---")
        print(f"Target Port: {settings.get('port')}")
        print(f"Orientation: {settings.get('rotation')*90} degrees")
        print(f"Flip X: {settings.get('flip_x')} | Flip Y: {settings.get('flip_y')}")
        
        """Background thread for UDP reception"""
        port = settings["port"]
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((ip, port))
        print(f"[LISTENING] {sensor_name} on port {port}")

        while True:
            try:
                data, addr = sock.recvfrom(8192)
                payload = json.loads(data)
                
                if sensor_name == "VL53L8_ToF" and "data" in payload:
                    self.process_tof(payload, settings)
            except Exception as e:
                print(f"[THREAD ERROR] {sensor_name}: {e}")

    def process_tof(self, payload, settings):
        """Processes and aligns the matrix to match myGUIcfg exactly"""
        data_list = payload["data"]
        dim = self.tof_resolution
        expected_size = dim * dim
        
        if len(data_list) < expected_size:
            return

        # 1. Load the raw matrix
        matrix = np.array(data_list[:expected_size]).reshape((dim, dim))
        
        # 2. Apply Rotation (k=3 is 270 deg Counter-Clockwise)
        # This matches the way ST remaps the indices for 'Rotation 3'
        matrix = np.rot90(matrix, k=settings.get("rotation", 0))
        
        # 3. Apply the Flips
        # To reach the TOP-RIGHT:
        # If flip_x (Horizontal) is True: we flip axis 0 (ST's remapped X)
        if settings.get("flip_x"): 
            matrix = np.flip(matrix, axis=0) 
            
        # If flip_y (Vertical) is False: we leave the baseline flip on axis 1
        if not settings.get("flip_y"): 
            matrix = np.flip(matrix, axis=1)

        with self.lock:
            self.last_matrix = matrix

    def run_ui_loop(self):
        """Handles Heatmap Rendering"""
        clock = pygame.time.Clock()
        running = True
        
        print(f"📡 UI Loop started. Close window to exit.")

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            with self.lock:
                if self.last_matrix is not None:
                    self.draw_heatmap(self.last_matrix)

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()

    def draw_heatmap(self, matrix):
        """Renders the matrix with colors and distance values"""
        self.screen.fill((15, 15, 15))
        dim = self.tof_resolution
        cell_size = self.window_size // dim

        for row in range(dim):
            for col in range(dim):
                val = matrix[row, col]
                
                # Rect calculation
                rect = pygame.Rect(col * cell_size, row * cell_size, cell_size - 2, cell_size - 2)
                
                # Color calculation (Red = Close, Blue = Far)
                # Map 0-2000mm to color range
                intensity = max(0, min(255, 255 - int(val / 8))) 
                color = (intensity, 40, 255 - intensity)
                
                pygame.draw.rect(self.screen, color, rect)
                
                # Display distance text (Always for 4x4, optional for 8x8 if font fits)
                if dim == 4:
                    txt_surf = self.font.render(f"{int(val)}", True, (255, 255, 255))
                    text_rect = txt_surf.get_rect(center=rect.center)
                    self.screen.blit(txt_surf, text_rect)

if __name__ == "__main__":
    consumer = MultiSensorConsumer()
    consumer.start()