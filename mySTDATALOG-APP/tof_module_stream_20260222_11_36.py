import time
import json
import socket
import sys
import logging
import struct
import numpy as np

# --- PFAD-KONFIGURATION ---
SDK_BASE_PATH = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK"
if SDK_BASE_PATH not in sys.path:
    sys.path.append(SDK_BASE_PATH)

# --- LOGGING UNTERDRÜCKEN ---
logging.getLogger().handlers = []
logging.getLogger('stdatalog_core').setLevel(logging.CRITICAL)
logging.getLogger('HSDatalogApp').setLevel(logging.CRITICAL)

try:
    from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2
except ImportError:
    print("FEHLER: ST-SDK nicht gefunden. Pfad prüfen!")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Packet geometry — proven from .dat file analysis
#
# Each packet from get_sensor_data() is 140 bytes:
#   [4 bytes counter (little-endian uint32)] — byte offset counter, increments by 136
#   [128 bytes zone data OR mixed zone+timestamp data]
#   [8 bytes padding/unused at end]
#
# The 4-byte counter = total data bytes sent so far.
# counter // 8 = total zone-pairs written = ring buffer write pointer.
#
# RING BUFFER ROTATION:
# The VL53L8CX outputs zones in a continuous circular stream.
# Each USB packet sends 136/8 = 17 zone-pairs, advancing the ring buffer by 17.
# 17 mod 16 = 1, so the starting zone shifts by -1 each packet.
# Correct unrotation: true_zone = (counter//8 - 15 + raw_index) % 16
#
# EMBEDDED TIMESTAMP:
# Every samples_per_ts=10 samples, an 8-byte double timestamp is inserted
# INSIDE the 128-byte payload at a variable offset.
# Detection: scan bytes 4..132 in 4-byte steps for a plausible double value.
# Plausible = 0.01 < value < 86400 (seconds, up to 24h).
# ---------------------------------------------------------------------------
PACKET_SIZE    = 140
COUNTER_OFFSET = 0    # 4-byte counter at start
DATA_OFFSET    = 4    # zone data starts here
DATA_END       = 132  # 128 bytes of (mostly) zone data
ZONE_PAIRS     = 16   # 16 zones × (status uint32 + distance uint32) = 128 bytes
TS_MIN         = 0.01   # seconds — minimum plausible timestamp
TS_MAX         = 86400  # seconds — maximum plausible timestamp (24h)

# ST GUI orientation transforms (from HSDatalog_v2 __plot_ranging_sensor)
# Applied to convert raw zone order to display coordinates.
# Set APPLY_REMAP = False if you want raw zone order in the GUI.
APPLY_REMAP = True

def _build_zone_remap() -> list:
    """Returns REMAP[true_zone] = display_zone_index."""
    idx = np.arange(16).reshape(4, 4)
    idx = np.rot90(idx, k=3)
    idx = np.flip(idx, axis=0)
    idx = np.swapaxes(idx, 0, 1)
    remap = [0] * 16
    for row in range(4):
        for col in range(4):
            remap[idx[row, col]] = row * 4 + col
    return remap

ZONE_REMAP = _build_zone_remap()


class ToFBackend:
    def __init__(self, host="127.0.0.1", port=5005):
        self.host          = host
        self.port          = port
        self.dev_id        = 0
        self.comp          = "vl53l8cx_tof"
        self.hsd           = None
        self.sock          = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_interval = 0.05   # 20 Hz max UDP send rate
        self.last_send     = 0.0
        self._carry        = b""    # leftover bytes between SDK calls
        self._stats        = {"chunks": 0, "packets": 0, "sent": 0, "ts_stripped": 0}

    # -----------------------------------------------------------------------
    # Packet splitter: carve complete 140-byte packets from the SDK byte stream
    # -----------------------------------------------------------------------
    def _get_packets(self, chunk: bytes) -> list[bytes]:
        """
        Split incoming SDK byte stream into complete 140-byte packets.
        Uses the 4-byte counter field to detect alignment:
        consecutive packets must have counters differing by exactly 136.
        Carries over incomplete data between calls.
        """
        buf = self._carry + chunk
        packets = []

        while len(buf) >= PACKET_SIZE * 2:
            # Verify alignment: check two consecutive packet counters
            ca = struct.unpack_from('<I', buf, 0)[0]
            cb = struct.unpack_from('<I', buf, PACKET_SIZE)[0]
            if cb == ca + 136:
                # Aligned — take first packet
                packets.append(buf[:PACKET_SIZE])
                buf = buf[PACKET_SIZE:]
            else:
                # Misaligned — skip 4 bytes and retry
                buf = buf[4:]

        # Keep remainder for next call
        if len(buf) >= PACKET_SIZE:
            # One complete packet at end (can't verify with next, trust it)
            packets.append(buf[:PACKET_SIZE])
            self._carry = buf[PACKET_SIZE:]
        else:
            self._carry = buf

        return packets

    # -----------------------------------------------------------------------
    # Timestamp detector: find embedded 8-byte timestamp in payload
    # -----------------------------------------------------------------------
    def _find_timestamp(self, packet: bytes) -> int | None:
        """
        Every samples_per_ts=10 packets, an 8-byte double timestamp is inserted
        inside the 128-byte zone data payload at a variable byte offset.
        Returns the byte offset from packet start, or None if not found.
        """
        for off in range(DATA_OFFSET, DATA_END - 4, 4):
            if off + 8 > len(packet):
                break
            val = struct.unpack_from('<d', packet, off)[0]
            if TS_MIN < val < TS_MAX:
                return off
        return None

    # -----------------------------------------------------------------------
    # Zone extractor: apply ring buffer unrotation and produce data_map
    # -----------------------------------------------------------------------
    def _extract_zones(self, packet: bytes) -> dict | None:
        """
        Parse one 140-byte packet into a {display_zone_str: {d, s}} dict.

        Steps:
        1. Read counter → compute ring buffer write pointer.
        2. Check for embedded timestamp → strip it to get clean 128 bytes.
        3. Apply ring buffer unrotation: true_zone = (ptr - 15 + raw_i) % 16
        4. Apply ST GUI orientation remap: display_zone = ZONE_REMAP[true_zone]
        """
        if len(packet) < PACKET_SIZE:
            return None

        counter = struct.unpack_from('<I', packet, COUNTER_OFFSET)[0]
        ptr = counter // 8  # absolute ring buffer write pointer

        # --- Strip embedded timestamp if present ---
        ts_off = self._find_timestamp(packet)
        if ts_off is not None:
            part1 = packet[DATA_OFFSET : ts_off]
            part2 = packet[ts_off + 8 : PACKET_SIZE]
            payload = part1 + part2
            self._stats["ts_stripped"] += 1
        else:
            payload = packet[DATA_OFFSET : DATA_END]

        if len(payload) < 128:
            return None

        values = np.frombuffer(payload[:128], dtype=np.uint32)
        if len(values) < 32:
            return None

        # --- Ring buffer unrotation + optional display remap ---
        data_map = {}
        for raw_i in range(16):
            true_zone   = (ptr - 15 + raw_i) % 16
            display_zone = ZONE_REMAP[true_zone] if APPLY_REMAP else true_zone
            stat_val     = int(values[raw_i * 2])
            dist_val     = int(values[raw_i * 2 + 1])
            data_map[str(display_zone)] = {"d": dist_val, "s": stat_val}

        return data_map

    # -----------------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------------
    def start(self):
        try:
            self.hsd = HSDLink_v2()
            self.hsd.send_command(self.dev_id, json.dumps({self.comp: {"enable": True}}))
            self.hsd.start_log(self.dev_id)

            print(f"Backend aktiv → {self.host}:{self.port}")
            print(f"APPLY_REMAP={APPLY_REMAP}  ZONE_REMAP={ZONE_REMAP}")
            print("Strg+C zum Beenden.\n")

            while True:
                res = self.hsd.get_sensor_data(self.dev_id, self.comp, 0)

                if res and len(res) > 1 and res[1]:
                    chunk = res[1]
                    self._stats["chunks"] += 1

                    for packet in self._get_packets(chunk):
                        self._stats["packets"] += 1
                        data_map = self._extract_zones(packet)

                        if data_map is not None:
                            now = time.time()
                            if now - self.last_send >= self.send_interval:
                                self.sock.sendto(
                                    json.dumps(data_map).encode(),
                                    (self.host, self.port)
                                )
                                self.last_send = now
                                self._stats["sent"] += 1

                # Status print every ~5 seconds
                if self._stats["chunks"] % 500 == 0 and self._stats["chunks"] > 0:
                    s = self._stats
                    carry_b = len(self._carry)
                    print(f"[INFO] chunks={s['chunks']}  packets={s['packets']}  "
                          f"sent={s['sent']}  ts_stripped={s['ts_stripped']}  "
                          f"carry={carry_b}b")

                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\nBackend wird gestoppt...")
        except Exception as e:
            print(f"\nFehler: {e}")
            import traceback; traceback.print_exc()
        finally:
            if self.hsd:
                self.hsd.stop_log(self.dev_id)
                self.hsd.send_command(
                    self.dev_id,
                    json.dumps({self.comp: {"enable": False}})
                )
                self.hsd.close()
            self.sock.close()


if __name__ == "__main__":
    ToFBackend().start()
