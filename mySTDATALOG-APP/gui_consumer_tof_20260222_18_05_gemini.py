import socket, json, pygame

# --- Setup ---
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
W = 600
CELL = W // 4

pygame.init()
screen = pygame.display.set_mode((W, W))
pygame.display.set_caption("ToF Live View")
font = pygame.font.SysFont("Arial", 20)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

# Mapping: Zone 0 ist bei ST oft unten links
REMAP = [12, 13, 14, 15, 8, 9, 10, 11, 4, 5, 6, 7, 0, 1, 2, 3]

def run_gui():
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False

        # 1. Nur das ALLERLETZTE Paket vom Stack lesen (verhindert Geisterbilder)
        data = None
        while True:
            try:
                packet, _ = sock.recvfrom(4096)
                data = json.loads(packet.decode())
            except: break 

        # 2. Zeichnen
        if data:
            screen.fill((30, 30, 30))
            for i, zone_id in enumerate(REMAP):
                z = data.get(str(zone_id), {"d": 4000, "s": 255})
                dist = z["d"]
                status = z["s"]

                row, col = divmod(i, 4)
                rect = pygame.Rect(col*CELL, row*CELL, CELL-2, CELL-2)

                # Logik: Nur zeichnen, wenn Status OK (5/9) und Distanz plausibel
                if status in [5, 6, 9] and 100 < dist < 1800:
                    # Je näher, desto heller das Blau
                    color_val = max(50, min(255, 255 - (dist // 8)))
                    pygame.draw.rect(screen, (0, color_val//2, color_val), rect)
                    
                    txt = font.render(f"{dist}mm", True, (255,255,255))
                    screen.blit(txt, txt.get_rect(center=rect.center))
                else:
                    pygame.draw.rect(screen, (50, 50, 50), rect)
            
            pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    run_gui()