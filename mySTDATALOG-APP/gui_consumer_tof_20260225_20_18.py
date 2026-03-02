import socket, json, pygame

UDP_IP, UDP_PORT = "127.0.0.1", 5005
W, CELL = 600, 150

pygame.init()
screen = pygame.display.set_mode((W, W))
pygame.display.set_caption("ST ToF Real-Time Decoder")
font = pygame.font.SysFont("Arial", 26, bold=True)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

def run():
    data = None
    clock = pygame.time.Clock()
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return

        # Vidage du buffer UDP
        try:
            while True:
                msg, _ = sock.recvfrom(4096)
                data = json.loads(msg.decode())
        except: pass

        screen.fill((20, 20, 20))
        if data:
            for i in range(16):
                val = data.get(str(i), {"d": 0})["d"]
                row, col = divmod(i, 4)
                rect = pygame.Rect(col*CELL, row*CELL, CELL-2, CELL-2)
                
                # Couleur proportionnelle à la distance
                color_val = max(40, min(255, 255 - int(val/10)))
                pygame.draw.rect(screen, (0, color_val, 100 if val > 0 else 40), rect)
                
                txt = font.render(f"{int(val)}", True, (255, 255, 255))
                screen.blit(txt, txt.get_rect(center=rect.center))
        else:
            txt = font.render("ATTENTE FLUX BINAIRE...", True, (255, 0, 0))
            screen.blit(txt, (W//4, W//2))

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    run()