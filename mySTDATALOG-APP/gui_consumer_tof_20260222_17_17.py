"""
gui_consumer_tof_20260222h.py
══════════════════════════════
GUI: Pygame heatmap display for vl53l8cx_tof via UDP

SMOOTHING STRATEGY (fixes ring buffer rotation artefact):
  The VL53L8CX ring buffer rotates by 1 position per USB packet (10 Hz).
  Zone Z's true measurement appears at raw index Z only once per 16 packets
  (every 1.6 seconds).  Between those appearances the value is stale/wrong.

  FIX: rolling MINIMUM over the last MIN_WINDOW=20 packets per zone.
    - Your zone always shows ~1300 mm  → minimum stays near 1300 mm  ✓
    - Background zones show ~2100 mm  → minimum stays near 2060 mm  ✓
  A window of 20 packets = 2 full ring-buffer cycles.  Each cycle guarantees
  at least one fresh measurement per zone, so the minimum always reflects
  the true current distance within ~2 seconds of latency.

  PRESENCE THRESHOLD: any zone whose rolling minimum < PRESENCE_MM is
  considered occupied and highlighted in the heatmap.

  Adjust:
    MIN_WINDOW       — larger = more stable but more lag
    PRESENCE_MM      — raise if false positives, lower if false negatives
    VALID_STATUSES   — status codes to accept (5=valid, 9=wrap-around valid)
"""

import json
import socket
import time
import numpy as np
from collections import deque
import pygame

# ── UDP receive settings ──────────────────────────────────────────────────────
UDP_IP   = "127.0.0.1"
UDP_PORT = 5005

# ── Smoothing parameters (tune these) ────────────────────────────────────────
MIN_WINDOW      = 20     # rolling minimum window (packets).  ≥16 recommended.
PRESENCE_MM     = 1800   # zones with rolling_min < this are "occupied"
VALID_STATUSES  = {5, 9} # accepted status codes

# ── Display settings ──────────────────────────────────────────────────────────
WINDOW_W, WINDOW_H = 700, 750
GRID_TOP    = 60
GRID_LEFT   = 50
CELL_SIZE   = 140
CELL_PAD    = 8
FPS         = 60
FONT_SIZE   = 22
TITLE_FONT  = 26

BG_COLOR      = (18,  18,  28)
CELL_BG       = (35,  35,  55)
PRESENT_COLOR = (255, 80,  60)   # red-orange: occupied zone
TEXT_COLOR    = (220, 220, 220)
DIM_TEXT      = (120, 120, 140)
TITLE_COLOR   = (200, 200, 255)
BORDER_COLOR  = (60,  60,  90)

# Distance → color gradient  (blue=far, green=mid, red=near)
DIST_MIN_MM = 800
DIST_MAX_MM = 2500

def dist_to_color(d_mm: float, occupied: bool) -> tuple:
    if occupied:
        return PRESENT_COLOR
    t = max(0.0, min(1.0, (d_mm - DIST_MIN_MM) / (DIST_MAX_MM - DIST_MIN_MM)))
    if t < 0.5:
        r = int(255 * (1 - 2 * t))
        g = int(255 * 2 * t)
        b = 0
    else:
        r = 0
        g = int(255 * (2 - 2 * t))
        b = int(255 * (2 * t - 1))
    return (r, g, b)


class ToFDisplay:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("VL53L8CX ToF  |  rolling-min smoothed")
        self.clock = pygame.time.Clock()
        self.font  = pygame.font.SysFont("monospace", FONT_SIZE)
        self.tfont = pygame.font.SysFont("monospace", TITLE_FONT, bold=True)
        self.sfont = pygame.font.SysFont("monospace", 16)

        # Per-zone rolling buffers
        # Index = display_zone_index (0..15), matching what the backend sends
        self.dist_buf   = {str(i): deque([DIST_MAX_MM] * MIN_WINDOW,
                                         maxlen=MIN_WINDOW) for i in range(16)}
        self.valid_buf  = {str(i): deque([False] * MIN_WINDOW,
                                         maxlen=MIN_WINDOW) for i in range(16)}

        # Stats
        self.n_recv  = 0
        self.n_total = 0
        self.last_ts = time.time()
        self.fps_est = 0.0

    # ── UDP socket (non-blocking) ─────────────────────────────────────────────
    def make_socket(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind((UDP_IP, UDP_PORT))
        s.setblocking(False)
        return s

    # ── Feed one UDP packet into the rolling buffers ──────────────────────────
    def feed(self, data_map: dict):
        for zone_key, vals in data_map.items():
            dist = vals.get("d", DIST_MAX_MM)
            stat = vals.get("s", 0)
            ok   = (stat in VALID_STATUSES) and (0 < dist < 10000)
            self.dist_buf[zone_key].append(dist if ok else DIST_MAX_MM)
            self.valid_buf[zone_key].append(ok)

        self.n_recv += 1
        self.n_total += 1
        now = time.time()
        if now - self.last_ts >= 1.0:
            self.fps_est = self.n_recv / (now - self.last_ts)
            self.n_recv  = 0
            self.last_ts = now

    # ── Compute display values (rolling minimum per zone) ─────────────────────
    def get_display_values(self):
        result = {}
        for i in range(16):
            k = str(i)
            buf = self.dist_buf[k]
            vbuf = self.valid_buf[k]
            valid_dists = [d for d, v in zip(buf, vbuf) if v]
            if valid_dists:
                d_min = min(valid_dists)
            else:
                d_min = DIST_MAX_MM
            occupied = d_min < PRESENCE_MM
            result[k] = (d_min, occupied)
        return result

    # ── Draw the 4×4 grid ─────────────────────────────────────────────────────
    def draw(self, display_values: dict):
        self.screen.fill(BG_COLOR)

        # Title
        title = self.tfont.render("VL53L8CX  4×4  ToF  Heatmap", True, TITLE_COLOR)
        self.screen.blit(title, (WINDOW_W // 2 - title.get_width() // 2, 12))

        n_occupied = sum(1 for (_, occ) in display_values.values() if occ)
        presence_txt = f"Präsenz: {'JA  (' + str(n_occupied) + ' Zone' + ('n)' if n_occupied>1 else ')') if n_occupied else 'nein'}"
        pcol = PRESENT_COLOR if n_occupied else DIM_TEXT
        ptxt = self.font.render(presence_txt, True, pcol)
        self.screen.blit(ptxt, (WINDOW_W // 2 - ptxt.get_width() // 2, 36))

        for row in range(4):
            for col in range(4):
                zone_idx = row * 4 + col
                k = str(zone_idx)
                d_min, occupied = display_values.get(k, (DIST_MAX_MM, False))

                x = GRID_LEFT + col * (CELL_SIZE + CELL_PAD)
                y = GRID_TOP  + row * (CELL_SIZE + CELL_PAD)
                rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)

                # Background cell
                color = dist_to_color(d_min, occupied)
                pygame.draw.rect(self.screen, color, rect, border_radius=10)
                pygame.draw.rect(self.screen, BORDER_COLOR, rect, width=2, border_radius=10)

                # Distance label
                dist_str = f"{d_min:4d} mm"
                dtxt = self.font.render(dist_str, True,
                                        (255, 255, 255) if occupied else TEXT_COLOR)
                self.screen.blit(dtxt, (x + CELL_SIZE//2 - dtxt.get_width()//2,
                                        y + CELL_SIZE//2 - dtxt.get_height()//2))

                # Zone index (small, corner)
                ztxt = self.sfont.render(f"Z{zone_idx}", True, DIM_TEXT)
                self.screen.blit(ztxt, (x + 6, y + 6))

                # Occupied indicator
                if occupied:
                    itxt = self.sfont.render("●", True, (255, 255, 255))
                    self.screen.blit(itxt, (x + CELL_SIZE - 20, y + 6))

        # Footer stats
        footer = (f"pkts recv: {self.n_total}   "
                  f"fps: {self.fps_est:.1f}   "
                  f"window: {MIN_WINDOW} pkts   "
                  f"thresh: {PRESENCE_MM} mm")
        ftxt = self.sfont.render(footer, True, DIM_TEXT)
        self.screen.blit(ftxt, (WINDOW_W//2 - ftxt.get_width()//2,
                                WINDOW_H - 28))

        pygame.display.flip()

    # ── Main loop ─────────────────────────────────────────────────────────────
    def run(self):
        sock = self.make_socket()
        print(f"GUI lauscht auf UDP {UDP_IP}:{UDP_PORT}")
        print(f"MIN_WINDOW={MIN_WINDOW} Pakete  |  PRESENCE_MM={PRESENCE_MM} mm")
        print("Fenster schließen oder ESC zum Beenden.\n")

        while True:
            # Drain all pending UDP packets
            got_new = False
            while True:
                try:
                    raw, _ = sock.recvfrom(65535)
                    data_map = json.loads(raw.decode())
                    self.feed(data_map)
                    got_new = True
                except BlockingIOError:
                    break
                except json.JSONDecodeError as e:
                    print(f"[WARN] JSON parse error: {e}")
                    break

            if got_new:
                self.draw(self.get_display_values())

            # Events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    # Press 'r' to reset rolling buffers
                    if event.key == pygame.K_r:
                        for i in range(16):
                            k = str(i)
                            self.dist_buf[k]  = deque([DIST_MAX_MM]*MIN_WINDOW, maxlen=MIN_WINDOW)
                            self.valid_buf[k] = deque([False]*MIN_WINDOW, maxlen=MIN_WINDOW)
                        print("[INFO] Puffer zurückgesetzt")

            self.clock.tick(FPS)

        sock.close()
        pygame.quit()


if __name__ == "__main__":
    ToFDisplay().run()
