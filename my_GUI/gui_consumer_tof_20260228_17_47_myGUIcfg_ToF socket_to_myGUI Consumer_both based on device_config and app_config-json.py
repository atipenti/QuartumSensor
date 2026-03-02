import socket
import json
import threading
import numpy as np
import os
import pygame
import math

class MultiSensorConsumer:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        app_cfg_path = os.path.join(self.base_dir, 'app_config.json')
        dev_cfg_path = os.path.join(self.base_dir, 'device_config.json')

        # Load Configs
        with open(app_cfg_path, 'r') as f:
            self.app_config = json.load(f)
        with open(dev_cfg_path, 'r') as f:
            self.dev_config = json.load(f)
            
        # --- DYNAMIC RESOLUTION ---
        self.tof_resolution = self._detect_tof_resolution()
        self.last_matrix = None
        self.lock = threading.Lock()
        
        # Pygame Setup
        self.window_size = 600
        pygame.init()
        self.screen = pygame.display.set_mode((self.window_size, self.window_size))
        pygame.display.set_caption("Multi-Sensor Heatmap Consumer")
        self.font = pygame.font.SysFont('Arial', 18)
        self.small_font = pygame.font.SysFont('Arial', 12)

        print(f"\n[INIT] Loaded from: {self.base_dir}")
        print(f"[*] Detected ToF Resolution: {self.tof_resolution}x{self.tof_resolution}")

    def _detect_tof_resolution(self):
        """Specifically parses the resolution from your device_config.json structure"""
        try:
            for device in self.dev_config.get("devices", []):
                for component in device.get("components", []):
                    # Loop through the keys to find the ToF sensor, even if it has 'cx' in the name
                    for key in component.keys():
                        if "vl53l8" in key and "tof" in key:
                            res = component[key].get("resolution", 0)
                            return 4 if res == 0 else 8
            return 4
        except:
            return 4

    def process_tof(self, payload, settings):
        """Processes and aligns the matrix to match myGUIcfg exactly"""
        data_list = payload["data"]
        
        # 1. Calculate the actual grid size (16 points -> 4x4, 64 points -> 8x8)
        expected_size = len(data_list)
        dim = int(math.sqrt(expected_size))
        
        if dim * dim != expected_size:
            return

        # 2. Load the raw matrix dynamically based on actual size
        matrix = np.array(data_list).reshape((dim, dim))
        
        # 3. Apply Rotation (k=3 is 270 deg Counter-Clockwise)
        # This matches the way ST remaps the indices for 'Rotation 3'
        matrix = np.rot90(matrix, k=settings.get("rotation", 0))
        
        # 4. Apply the Flips (YOUR EXACT LOGIC)
        # To reach the TOP-RIGHT:
        # If flip_x (Horizontal) is True: we flip axis 0 (ST's remapped X)
        if settings.get("flip_x"): 
            matrix = np.flip(matrix, axis=0) 
            
        # If flip_y (Vertical) is False: we leave the baseline flip on axis 1
        if not settings.get("flip_y"): 
            matrix = np.flip(matrix, axis=1)

        with self.lock:
            self.last_matrix = matrix
            self.tof_resolution = dim  # Update the UI resolution to match

    def sensor_worker(self, sensor_name, settings):
        port = settings["port"]
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", port))
        
        print(f"--- [DEBUG] Worker Started for {sensor_name} ---")
        print(f"Target Port: {port} | Rot: {settings.get('rotation')*90} | FX: {settings.get('flip_x')} | FY: {settings.get('flip_y')}")

        while True:
            data, _ = sock.recvfrom(8192)
            try:
                payload = json.loads(data.decode())
                if payload.get("s_id") == sensor_name:
                    self.process_tof(payload, settings)
            except:
                pass

    def draw_heatmap(self, matrix):
        self.screen.fill((15, 15, 15))
        dim = self.tof_resolution
        cell_size = self.window_size // dim

        for row in range(dim):
            for col in range(dim):
                val = matrix[row, col]
                rect = pygame.Rect(col * cell_size, row * cell_size, cell_size - 1, cell_size - 1)
                
                # Dynamic color scaling
                intensity = max(0, min(255, 255 - int(val / 8))) 
                color = (intensity, 40, 255 - intensity)
                
                pygame.draw.rect(self.screen, color, rect)
                
                # Text Scaling
                use_font = self.font if dim == 4 else self.small_font
                txt_surf = use_font.render(f"{int(val)}", True, (255, 255, 255))
                self.screen.blit(txt_surf, txt_surf.get_rect(center=rect.center))

    def run(self):
        tof_settings = self.app_config["network_config"]["sensors"]["VL53L8_ToF"]
        threading.Thread(target=self.sensor_worker, args=("VL53L8_ToF", tof_settings), daemon=True).start()

        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
            
            with self.lock:
                if self.last_matrix is not None:
                    self.draw_heatmap(self.last_matrix)
            
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()

if __name__ == "__main__":
    app = MultiSensorConsumer()
    app.run()