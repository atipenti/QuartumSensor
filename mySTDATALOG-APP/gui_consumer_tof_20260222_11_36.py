import socket
import json
import pygame
import numpy as np
from collections import deque

# ---------------------------------------------------------------------------
# Netzwerk Setup
# ---------------------------------------------------------------------------
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 5005))
sock.setblocking(False)

# ---------------------------------------------------------------------------
# Grafik Setup
# ---------------------------------------------------------------------------
pygame.init()
SIZE     = 640          # Fenstergrösse in Pixel (quadratisch)
CELL_GAP = 6            # Abstand zwischen den Zellen in Pixel
screen   = pygame.display.set_mode((SIZE, SIZE))
pygame.display.set_caption("ToF ST-GUI")
font_dist   = pygame.font.SysFont("Arial", 20, bold=True)
font_label  = pygame.font.SysFont("Arial", 11)
font_status = pygame.font.SysFont("Arial", 11)

# ---------------------------------------------------------------------------
# Sensor / Szenen-Parameter  — hier anpassen falls nötig
# ---------------------------------------------------------------------------
# Sensor hängt an der Decke bei ~2100mm. Du sitzt bei ~1300mm Abstand.
# NEAR_DIST: Untergrenze der Farbskala (= nächstes erwartetes Objekt)
# FAR_DIST:  Obergrenze (= leere Zone, z.B. Boden oder Decken-Hintergrund)
# Zellen ausserhalb [NEAR_DIST, FAR_DIST] werden als inaktiv behandelt.
NEAR_DIST         = 500    # mm — näher als das = "sehr nah" (Rot)
FAR_DIST          = 2200   # mm — weiter als das = "Hintergrund" (grau)
PRESENCE_MARGIN   = 200    # mm — Zelle gilt als "Präsenz" wenn sie um diesen
                            #      Betrag näher ist als der Median aller Zellen

# ---------------------------------------------------------------------------
# Temporale Glättung & Gültigkeitsschutz
# ---------------------------------------------------------------------------
HISTORY           = 8    # Frames für gleitenden Mittelwert (mehr = glatter)
INVALID_THRESHOLD = 8    # Frames mit schlechtem Status bevor Zelle grau wird

dist_history  = {str(i): deque([FAR_DIST] * HISTORY, maxlen=HISTORY) for i in range(16)}
invalid_count = {str(i): 0 for i in range(16)}
last_status   = {str(i): 0 for i in range(16)}   # für Anzeige im Debug-Label

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def dist_to_color(dist_mm: int) -> tuple:
    """
    Farbskala relativ zu [NEAR_DIST, FAR_DIST]:
      Nah  -> Rot    (255,   0,   0)
      Mitte-> Gelb   (255, 200,   0)
      Weit -> Blau   (  0,  80, 255)
    """
    t = max(0.0, min(1.0, (dist_mm - NEAR_DIST) / (FAR_DIST - NEAR_DIST)))

    if t < 0.5:
        s = t * 2.0
        r = 255
        g = int(200 * s)
        b = 0
    else:
        s = (t - 0.5) * 2.0
        r = int(255 * (1.0 - s))
        g = int(200 * (1.0 - s))
        b = int(255 * s)

    return (r, g, b)


def draw_matrix(cells: dict):
    screen.fill((20, 20, 20))
    cell_s = SIZE // 4

    # Geglättete Distanzen aller aktiven Zellen sammeln für Präsenz-Erkennung
    active_dists = []
    smoothed = {}

    for i in range(16):
        key  = str(i)
        cell = cells.get(key, {"d": FAR_DIST, "s": 0})

        status_ok = cell["s"] == 5 and NEAR_DIST <= cell["d"] <= FAR_DIST
        if status_ok:
            dist_history[key].append(cell["d"])
            invalid_count[key] = 0
        else:
            invalid_count[key] += 1

        last_status[key] = cell["s"]
        s_dist = int(np.mean(dist_history[key]))
        smoothed[key]    = s_dist
        cell_active      = invalid_count[key] < INVALID_THRESHOLD

        if cell_active:
            active_dists.append(s_dist)

    # Median der aktiven Zellen: Zellen deutlich darunter = Präsenz
    median_dist = int(np.median(active_dists)) if active_dists else FAR_DIST

    # --- Zeichnen ---
    for i in range(16):
        key  = str(i)
        row, col = divmod(i, 4)
        rect = pygame.Rect(
            col * cell_s + CELL_GAP // 2,
            row * cell_s + CELL_GAP // 2,
            cell_s - CELL_GAP,
            cell_s - CELL_GAP
        )

        cell_active  = invalid_count[key] < INVALID_THRESHOLD
        s_dist       = smoothed[key]
        is_presence  = cell_active and (s_dist < median_dist - PRESENCE_MARGIN)

        if cell_active:
            color = dist_to_color(s_dist)
            pygame.draw.rect(screen, color, rect, border_radius=8)

            # Weisser Rahmen bei Präsenz-Zelle
            if is_presence:
                pygame.draw.rect(screen, (255, 255, 255), rect, width=3, border_radius=8)

            # Distanzwert — mittig
            text = font_dist.render(f"{s_dist} mm", True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=rect.center))

            # Zell-Index oben links
            idx_label = font_label.render(f"#{i}", True, (220, 220, 220))
            screen.blit(idx_label, (rect.x + 5, rect.y + 5))

            # Status-Code oben rechts (hilft beim Diagnose der Parsing-Probleme)
            st_label = font_status.render(f"s{last_status[key]}", True, (180, 255, 180))
            screen.blit(st_label, (rect.right - 28, rect.y + 5))

        else:
            # Inaktive / ungültige Zelle
            pygame.draw.rect(screen, (45, 45, 45), rect, border_radius=8)
            idx_label = font_label.render(f"#{i}", True, (90, 90, 90))
            screen.blit(idx_label, (rect.x + 5, rect.y + 5))
            # Status anzeigen damit man sieht was der Sensor meldet
            st_label = font_status.render(f"s{last_status[key]}", True, (180, 80, 80))
            screen.blit(st_label, (rect.right - 28, rect.y + 5))

    pygame.display.flip()


# ---------------------------------------------------------------------------
# Hauptschleife
# ---------------------------------------------------------------------------
try:
    print("Starte GUI... Drücke ESC oder schliesse das Fenster zum Beenden.")

    last_data    = None
    got_new_data = False

    while True:

        # UDP Socket leeren — immer das neueste Paket behalten
        got_new_data = False
        while True:
            try:
                raw, _ = sock.recvfrom(8192)
                last_data    = json.loads(raw.decode())
                got_new_data = True
            except BlockingIOError:
                break
            except json.JSONDecodeError:
                break

        # Nur neu zeichnen wenn tatsächlich neue Daten angekommen sind
        if got_new_data and last_data is not None:
            cells = last_data if "cells" not in last_data else last_data["cells"]
            draw_matrix(cells)

        # Pygame-Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                raise KeyboardInterrupt

        pygame.time.delay(16)   # ~60 Hz Poll-Deckel

except KeyboardInterrupt:
    print("\nGUI wird beendet.")
    pygame.quit()