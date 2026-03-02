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
        self.last_tmos_data = None # Php 20260301 - NEW: Storage for TMOS list
        self.lock = threading.Lock()
        
        # INCREASED WIDTH: 600 (ToF) + 250 (TMOS) = 850
        self.win_w = 850
        self.win_h = 600
        pygame.init()
        self.screen = pygame.display.set_mode((self.win_w, self.win_h))
        pygame.display.set_caption("Multi-Sensor Heatmap & TMOS Dashboard")
        self.font = pygame.font.SysFont('Arial', 18)
        self.small_font = pygame.font.SysFont('Arial', 14, bold=True)
        self.title_font = pygame.font.SysFont('Arial', 24, bold=True)

        print(f"\n[INIT] Loaded from: {self.base_dir}")
        print(f"[*] Detected ToF Resolution: {self.tof_resolution}x{self.tof_resolution}")

    def _detect_tof_resolution(self):
        """Meticulously finds resolution from device_config.json"""
        for comp in self.dev_config['devices'][0]['components']:
            if "vl53l8cx_tof" in comp:
                # 0 = 4x4, 1 = 8x8
                return 4 if comp["vl53l8cx_tof"]["resolution"] == 0 else 8
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

    def draw_tmos_dashboard(self, data):
        # Index mapping from your FIXED HSDPlotTMOSWidget.py:
        # data[1] = ObjTemp (e.g. -3100), data[4] = Presence, data[6] = Motion
        obj_temp = data[1]
        presence = data[4] > 0
        motion = data[6] > 0
        center_x = 725 

        # 1. Presence Indicator (Cyan)
        p_col = (0, 255, 255) if presence else (20, 40, 40)
        pygame.draw.circle(self.screen, p_col, (center_x - 50, 100), 30)
        self.screen.blit(self.small_font.render("PRESENCE", True, (200,200,200)), (center_x - 85, 140))

        # 2. Motion Indicator (Red)
        m_col = (255, 0, 0) if motion else (40, 20, 20)
        pygame.draw.circle(self.screen, m_col, (center_x + 50, 100), 30)
        self.screen.blit(self.small_font.render("MOTION", True, (200,200,200)), (center_x + 25, 140))

        # 3. Heat Intensity Gauge
        # Your "Quiet" state is ~ -3100. Your "Active" state is ~ -1900.
        # We map that range to 0-100%
        gauge_val = ((obj_temp - (-3500)) / 2000) * 100
        gauge_val = max(0, min(100, gauge_val))
        
        self.draw_gauge(center_x, 350, gauge_val)


    def draw_gauge(self, x, y, value):
        radius = 85
        rect = pygame.Rect(x - radius, y - radius, radius * 2, radius * 2)
        pygame.draw.arc(self.screen, (100, 100, 100), rect, 0, math.pi, 4)
        
        # Angle maps 0-100 to PI to 0
        angle = math.pi - (value / 100.0 * math.pi)
        
        end_x = x + (radius - 15) * math.cos(angle)
        end_y = y - (radius - 15) * math.sin(angle)
        
        pygame.draw.line(self.screen, (255, 255, 255), (x, y), (end_x, end_y), 3)
        pygame.draw.circle(self.screen, (150, 150, 150), (x, y), 8)
        
        # Changed label to "Heat Intensity" to match your visual
        txt = self.font.render(f"Heat: {value:.1f}%", True, (255, 255, 255))
        self.screen.blit(txt, (x - 45, y + 20))

    def sensor_worker(self, sensor_name, settings):
        port = settings.get("port")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Add these two lines to allow sharing the port
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            sock.bind(("0.0.0.0", port)) # Bind to all interfaces
        except Exception as e:
            print(f"❌ Could not bind {sensor_name} to port {port}: {e}")
            return
        
        # Php 20260301 - With UDP Boradcaster
        print(f"--- [DEBUG] Worker Started for {sensor_name} on Port: {port} ---")
        while True:
            try:
                data, _ = sock.recvfrom(65535)
                payload = json.loads(data.decode())
                
                incoming_id = payload.get("s_id")
                print(f"Incoming ID: {payload.get('s_id')} on Port {port}")
                
                # Check if the payload ID matches the worker's assigned sensor
                if incoming_id == sensor_name:
                    if sensor_name == "vl53l8cx_tof":
                        self.process_tof(payload, settings)
                    elif sensor_name == "sths34pf80_tmos":
                        # DEBUG: Confirm we are actually getting TMOS data
                        # print(f"✅ TMOS Data: {payload['data']}") 
                        with self.lock:
                            self.last_tmos_data = payload["data"]
                else:
                    # CRITICAL DEBUG: This will tell us if the names don't match!
                    print(f"⚠️ ID Mismatch on Port {port}: Expected '{sensor_name}', but got '{incoming_id}'")
                            
            except Exception as e:
                print(f"⚠️ Error in {sensor_name} worker: {e}")
#end of

    def draw_heatmap(self, matrix):
        dim = self.tof_resolution
        # 600 is hardcoded to lock the heatmap to the left side of the screen
        cell_size = 600 // dim

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
        sensors_cfg = self.app_config["network_config"]["sensors"]
        for name, settings in sensors_cfg.items():
            if settings.get("enabled", False):
                threading.Thread(target=self.sensor_worker, args=(name, settings), daemon=True).start()

        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
            
            # 1. Clear the screen ONCE per frame
            self.screen.fill((10, 10, 10))
            
            # 2. Draw both parts inside the same lock session
            with self.lock:
                if self.last_matrix is not None:
                    self.draw_heatmap(self.last_matrix)
                
                if self.last_tmos_data is not None:
                    d = self.last_tmos_data
                    # FIXED PRINT: Reach the actual values received from the Broadcaster
                    print(f"ObjTemp: {d[1]:.1f} | Presence: {d[4]} | Motion: {d[6]}")
                    self.draw_tmos_dashboard(self.last_tmos_data)
                else:
                    # DRAW A PLACEHOLDER: If no data, show a message so we know the dashboard logic is alive
                    msg = self.font.render("Waiting for TMOS data...", True, (100, 100, 100))
                    self.screen.blit(msg, (620, 280))
            
            # 3. Draw the vertical divider line
            pygame.draw.line(self.screen, (60, 60, 60), (600, 0), (600, 600), 2)
            
            # 4. Flip the display ONCE per frame
            pygame.display.flip()
            clock.tick(30)
        pygame.quit()

if __name__ == "__main__":
    app = MultiSensorConsumer()
    app.run()