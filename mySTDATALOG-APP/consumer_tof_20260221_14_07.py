import socket
import json
import time
import sys

UDP_IP = "127.0.0.1"
UDP_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

# Die feste Anordnung der Zellen (Mapping)
# Damit "Zelle 0" immer oben links steht und sich nichts verschiebt
GRID_MAP = [
    [0, 1, 2, 3],
    [4, 5, 6, 7],
    [8, 9, 10, 11],
    [12, 13, 14, 15]
]

def draw_stable_grid(data):
    # Cursor nach oben links (verhindert Scrollen/Flimmern)
    output = "\033[H" 
    output += "=== STABILER MATRIX MONITOR (ST-GUI STYLE) ===\n"
    output += "-----------------------------------------------\n"
    
    for row in GRID_MAP:
        line = " | "
        for cell_id in row:
            val = data.get(str(cell_id), {"d": 2500, "s": 0})
            d, s = val["d"], val["s"]
            
            # Nur Werte anzeigen, die nicht der Boden sind (> 2000mm)
            if s in [5, 9] and d < 2000:
                line += f"{int(d):4d}mm | "
            else:
                line += "  ....  | " # Boden/Leere Zelle
        output += line + "\n"
    
    output += "-----------------------------------------------\n"
    output += f"Letztes Update: {time.strftime('%H:%M:%S')}\n"
    
    sys.stdout.write(output)
    sys.stdout.flush()

print("\033[2J") # Bildschirm einmalig leeren
try:
    while True:
        last_packet = None
        # WICHTIG: Buffer leeren, um nur das aktuellste Bild zu zeigen
        while True:
            try:
                raw, _ = sock.recvfrom(4096)
                last_packet = json.loads(raw.decode())
            except (BlockingIOError, socket.error):
                break
        
        if last_packet:
            draw_stable_grid(last_packet)
        
        # Update-Rate auf 10Hz begrenzen für Auge und CPU
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nBeendet.")