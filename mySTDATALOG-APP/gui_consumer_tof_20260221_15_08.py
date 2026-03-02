import socket, json, pygame

# Netzwerk Setup
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 5005))
sock.setblocking(False)

# Grafik Setup
pygame.init()
size = 600 # Etwas größer für bessere Lesbarkeit
screen = pygame.display.set_mode((size, size))
pygame.display.set_caption("ToF ST-GUI Clone")
font = pygame.font.SysFont('Arial', 24, bold=True)

def draw_matrix(data):
    screen.fill((30, 30, 30)) # Dunkler Hintergrund
    cell_s = size // 4
    
    cells = data if "cells" not in data else data["cells"]
    
    for i in range(16):
        cell = cells.get(str(i), {"d": 2500, "s": 0})
        dist = cell["d"]
        
        row, col = divmod(i, 4)
        rect = pygame.Rect(col * cell_s, row * cell_s, cell_s - 4, cell_s - 4)
        
        # Farbe bestimmen (Blau -> Grün -> Gelb je nach Nähe)
        if cell["s"] in [5, 9] and dist < 2200:
            color_intensity = max(0, min(255, 255 - (dist // 10)))
            color = (0, color_intensity, 255 - color_intensity)
            pygame.draw.rect(screen, color, rect)
            
            # Text einfügen
            text = font.render(f"{dist}mm", True, (255, 255, 255))
            text_rect = text.get_rect(center=rect.center)
            screen.blit(text, text_rect)
        else:
            pygame.draw.rect(screen, (60, 60, 60), rect) # Inaktiv

    pygame.display.flip()

try:
    print("Starte GUI... Drücke ESC zum Beenden.")
    while True:
        last_data = None
        while True:
            try:
                raw, _ = sock.recvfrom(8192)
                last_data = json.loads(raw.decode())
            except: break
        
        if last_data:
            draw_matrix(last_data)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                raise KeyboardInterrupt
        pygame.time.delay(20)

except KeyboardInterrupt:
    pygame.quit()