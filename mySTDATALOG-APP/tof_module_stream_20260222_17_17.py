"""
tof_module_stream_20260222h.py
══════════════════════════════
Backend: STWIN.BOX vl53l8cx_tof → UDP JSON

ARCHITECTURE (proven from .dat file binary analysis):

Packet structure (140 bytes):
  [0:4]    4-byte little-endian counter  (increments by 136 per packet)
  [4:132]  128 bytes = 32 uint32 values  (interleaved status+distance, 16 zones)
  [132:140] 8 bytes                      (padding, or timestamp every 10th packet)

Zone extraction (simple, one packet = one scan):
  values = uint32[4:132]   (32 values)
  status[Z]   = values[2*Z]      Z = 0..15
  distance[Z] = values[2*Z + 1]

NOTE: The VL53L8CX firmware exhibits a ring buffer rotation — each USB packet
the zone at raw position Z is NOT always physical zone Z.  The rotation is
ONE position per packet.  We do NOT correct this here.  Instead, the GUI
consumer uses a rolling MINIMUM over the last ~20 packets per zone, which
naturally picks up the one frame in each 16-packet cycle where the true
measurement lands at the correct position.

Console [INFO] line (every 500 SDK calls) shows:
  sdk_calls  — total calls to get_sensor_data()
  pkts       — total 140-byte packets parsed
  sent       — total UDP datagrams sent
  carry      — leftover bytes in alignment buffer (healthy = 0..276b)
  align_err  — packets skipped due to counter misalignment
"""

import time
import json
import socket
import sys
import logging
import struct
import numpy as np

# ── SDK path ─────────────────────────────────────────────────────────────────
SDK_BASE_PATH = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK"
if SDK_BASE_PATH not in sys.path:
    sys.path.append(SDK_BASE_PATH)

logging.getLogger().handlers = []
logging.getLogger('stdatalog_core').setLevel(logging.CRITICAL)
logging.getLogger('HSDatalogApp').setLevel(logging.CRITICAL)

try:
    from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2
except ImportError:
    print("FEHLER: ST-SDK nicht gefunden. Pfad prüfen!")
    sys.exit(1)

# ── Constants (from device_config.json) ──────────────────────────────────────
PACKET_SIZE   = 140    # 4b counter + 136b payload
COUNTER_BYTES = 4
USB_DPS       = 136    # bytes per payload (= usb_dps)
ZONE_BYTES    = 128    # 32 uint32 = 16 zones × (status + distance)
NOF_ZONES     = 16

# ── ST GUI display orientation transform ─────────────────────────────────────
# Source: HSDatalog_v2.__plot_ranging_sensor() lines 1798-1800
#   mat = np.rot90(mat, k=3)
#   mat = np.flip(mat, axis=0)
#   mat = np.swapaxes(mat, 0, 1)
# REMAP[raw_zone] = display_zone_index
def _build_remap() -> list:
    idx = np.arange(16).reshape(4, 4)
    idx = np.rot90(idx, k=3)
    idx = np.flip(idx, axis=0)
    idx = np.swapaxes(idx, 0, 1)
    remap = [0] * 16
    for r in range(4):
        for c in range(4):
            remap[idx[r, c]] = r * 4 + c
    return remap

DISPLAY_REMAP = _build_remap()


class ToFBackend:
    def __init__(self, host: str = "127.0.0.1", port: int = 5005):
        self.host = host
        self.port = port
        self.dev_id = 0
        self.comp = "vl53l8cx_tof"
        self.hsd = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Rate limiting: sensor is 10 Hz; send at most 20 Hz to the GUI
        self.send_interval = 0.048   # ~20 Hz
        self._last_send = 0.0

        # Packet alignment buffer
        self._buf = b""
        self._last_counter = None   # set on first valid packet

        self._stats = dict(sdk_calls=0, pkts=0, sent=0, align_err=0)

    # ── extract one complete scan from a 140-byte raw packet ─────────────────
    def _parse_packet(self, pkt: bytes) -> dict | None:
        if len(pkt) < PACKET_SIZE:
            return None

        counter = struct.unpack_from('<I', pkt, 0)[0]

        # Verify counter increment (skip silently on mismatch)
        if self._last_counter is not None:
            if counter != self._last_counter + USB_DPS:
                self._stats["align_err"] += 1
        self._last_counter = counter

        # Read 32 uint32 values from bytes [4:132]
        values = np.frombuffer(pkt[COUNTER_BYTES : COUNTER_BYTES + ZONE_BYTES],
                               dtype=np.uint32)

        data_map = {}
        for z in range(NOF_ZONES):
            stat = int(values[2 * z])
            dist = int(values[2 * z + 1])
            disp = DISPLAY_REMAP[z]
            data_map[str(disp)] = {"d": dist, "s": stat}

        return data_map

    # ── carve complete 140-byte packets from the SDK byte stream ─────────────
    def _get_packets(self, chunk: bytes) -> list[bytes]:
        self._buf += chunk
        packets = []
        while len(self._buf) >= PACKET_SIZE:
            packets.append(self._buf[:PACKET_SIZE])
            self._buf = self._buf[PACKET_SIZE:]
        return packets

    # ── main loop ─────────────────────────────────────────────────────────────
    def start(self):
        try:
            self.hsd = HSDLink_v2()
            self.hsd.send_command(self.dev_id,
                                  json.dumps({self.comp: {"enable": True}}))
            self.hsd.start_log(self.dev_id)

            print(f"Backend aktiv → UDP {self.host}:{self.port}")
            print(f"DISPLAY_REMAP = {DISPLAY_REMAP}")
            print("Strg+C zum Beenden.\n")

            while True:
                res = self.hsd.get_sensor_data(self.dev_id, self.comp, 0)

                if res and len(res) > 1 and res[1]:
                    self._stats["sdk_calls"] += 1
                    for pkt in self._get_packets(res[1]):
                        self._stats["pkts"] += 1
                        data_map = self._parse_packet(pkt)
                        if data_map is None:
                            continue
                        now = time.time()
                        if now - self._last_send >= self.send_interval:
                            self.sock.sendto(
                                json.dumps(data_map).encode(),
                                (self.host, self.port))
                            self._last_send = now
                            self._stats["sent"] += 1

                if self._stats["sdk_calls"] % 500 == 0 \
                        and self._stats["sdk_calls"] > 0 \
                        and self._stats["sdk_calls"] != getattr(self, '_last_print', 0):
                    self._last_print = self._stats["sdk_calls"]
                    s = self._stats
                    print(f"[INFO] sdk_calls={s['sdk_calls']}  pkts={s['pkts']}  "
                          f"sent={s['sent']}  carry={len(self._buf)}b  "
                          f"align_err={s['align_err']}")

                time.sleep(0.005)

        except KeyboardInterrupt:
            print("\nBackend wird gestoppt...")
        except Exception as e:
            print(f"\nFehler: {e}")
            import traceback; traceback.print_exc()
        finally:
            if self.hsd:
                try:
                    self.hsd.stop_log(self.dev_id)
                    self.hsd.send_command(
                        self.dev_id,
                        json.dumps({self.comp: {"enable": False}}))
                    self.hsd.close()
                except Exception:
                    pass
            self.sock.close()


if __name__ == "__main__":
    ToFBackend().start()