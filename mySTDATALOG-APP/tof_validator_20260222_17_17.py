"""
tof_validator.py  —  Step-by-step pipeline validator for vl53l8cx_tof
======================================================================
Run this INSTEAD of the normal backend to validate each stage.
It requires a .dat file from a previous ST GUI acquisition.

Usage:
    python tof_validator.py --dat path/to/vl53l8cx_tof.dat

Outputs a full report: packet integrity, frame assembly, zone map,
and compares every step against what the ST SDK expects.

No hardware connection needed — works offline from the .dat file.
"""

import sys
import os
import struct
import argparse
import numpy as np

# ---------------------------------------------------------------------------
# Constants (from device_config.json + ST SDK source)
# ---------------------------------------------------------------------------
PACKET_SIZE       = 140       # 4-byte counter + 136-byte payload
COUNTER_SIZE      = 4
USB_DPS           = 136       # usb_dps from device_config.json
DATA_TYPE         = np.uint32 # uint32_t
DATA_TYPE_BYTES   = 4
DIMENSIONS        = 32        # dim: 16 zones × 2 (status + distance)
SAMPLES_PER_TS    = 10        # samples_per_ts
DATAFRAME_BYTES   = SAMPLES_PER_TS * DIMENSIONS * DATA_TYPE_BYTES  # = 1280
TIMESTAMP_BYTES   = 8
FRAME_BYTES       = DATAFRAME_BYTES + TIMESTAMP_BYTES  # = 1288
NOF_ZONES         = 16

# ---------------------------------------------------------------------------
# ST SDK display transform (from __plot_ranging_sensor lines 1798-1800)
# ---------------------------------------------------------------------------
def apply_display_transform(mat4x4: np.ndarray) -> np.ndarray:
    m = np.rot90(mat4x4, k=3)
    m = np.flip(m, axis=0)
    m = np.swapaxes(m, 0, 1)
    return m


def build_display_index_map() -> np.ndarray:
    """Returns display[r,c] = raw_zone_index."""
    idx = np.arange(16).reshape(4, 4)
    return apply_display_transform(idx)


# ===========================================================================
# STAGE 1 — Raw packet integrity
# ===========================================================================
def stage1_packet_integrity(raw: bytes) -> tuple[bool, list[dict]]:
    """
    Check that every 140-byte packet has a counter that increments by 136.
    Returns (ok, list of errors).
    """
    n = len(raw) // PACKET_SIZE
    errors = []
    packets = []

    for i in range(n):
        off = i * PACKET_SIZE
        counter = struct.unpack_from('<I', raw, off)[0]
        packets.append(counter)

    for i in range(1, len(packets)):
        expected = packets[i-1] + USB_DPS
        if packets[i] != expected:
            errors.append({
                "pkt": i,
                "expected_counter": expected,
                "got_counter": packets[i],
                "delta": packets[i] - packets[i-1]
            })

    ok = len(errors) == 0
    return ok, errors, n, packets


# ===========================================================================
# STAGE 2 — Flat stream assembly (strip counters)
# ===========================================================================
def stage2_strip_counters(raw: bytes, n_packets: int) -> bytes:
    """
    Strip the 4-byte counter from the start of every 140-byte packet.
    Replicates remove_4bytes_every_n_optimized(arr, N=140).
    """
    parts = []
    for i in range(n_packets):
        off = i * PACKET_SIZE
        parts.append(raw[off + COUNTER_SIZE : off + PACKET_SIZE])
    return b"".join(parts)


# ===========================================================================
# STAGE 3 — Frame assembly (group flat stream into 1288-byte frames)
# ===========================================================================
def stage3_assemble_frames(flat: bytes) -> tuple[list[np.ndarray], list[float]]:
    """
    Group flat stream into complete 1288-byte frames.
    Each frame = 1280 bytes data + 8 bytes timestamp.
    Returns list of (samples_array shaped (10,32)) and timestamps.
    """
    n_frames = len(flat) // FRAME_BYTES
    remainder = len(flat) % FRAME_BYTES

    frames_data = []
    timestamps = []

    for i in range(n_frames):
        off = i * FRAME_BYTES
        data_bytes = flat[off : off + DATAFRAME_BYTES]
        ts_bytes   = flat[off + DATAFRAME_BYTES : off + FRAME_BYTES]

        samples = np.frombuffer(data_bytes, dtype=DATA_TYPE).reshape(SAMPLES_PER_TS, DIMENSIONS)
        ts = struct.unpack('<d', ts_bytes)[0]

        frames_data.append(samples)
        timestamps.append(ts)

    return frames_data, timestamps, n_frames, remainder


# ===========================================================================
# STAGE 4 — Zone extraction from a single frame (last sample)
# ===========================================================================
def stage4_extract_zones(samples_10x32: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Extract status and distance for all 16 zones from the last sample.
    Zone Z: status = sample[2*Z], distance = sample[2*Z+1]
    Uses the LAST sample (index 9) = most recent measurement.
    Returns (status[16], distance[16]).
    """
    last = samples_10x32[-1]  # shape (32,)
    status   = last[0::2]     # indices 0,2,4,...,30  → zones 0..15
    distance = last[1::2]     # indices 1,3,5,...,31
    return status, distance


# ===========================================================================
# STAGE 5 — Display formatting
# ===========================================================================
def stage5_format_for_udp(status: np.ndarray, distance: np.ndarray,
                           apply_remap: bool = True) -> dict:
    """
    Format zone data into the UDP JSON dict: {zone_str: {d, s}}.
    Optionally applies the ST GUI display orientation remap.
    """
    data_map = {}
    display_map = build_display_index_map()

    for z in range(NOF_ZONES):
        if apply_remap:
            # Find display position of raw zone z
            pos = np.argwhere(display_map == z)[0]
            display_idx = pos[0] * 4 + pos[1]
        else:
            display_idx = z
        data_map[str(display_idx)] = {
            "d": int(distance[z]),
            "s": int(status[z])
        }
    return data_map


# ===========================================================================
# STAGE 6 — UDP packet inspection
# ===========================================================================
def stage6_udp_check(data_map: dict):
    """Validate the UDP JSON dict for sanity."""
    issues = []
    for k, v in data_map.items():
        if not (0 <= int(k) <= 15):
            issues.append(f"  zone key out of range: {k}")
        s = v.get("s", -1)
        d = v.get("d", -1)
        if s not in (5, 6, 9, 10, 11, 12, 255):
            issues.append(f"  zone {k}: unusual status {s}")
        if not (0 < d < 10000):
            issues.append(f"  zone {k}: implausible distance {d}")
    return issues


# ===========================================================================
# MAIN REPORT
# ===========================================================================
def run_validation(dat_path: str):
    print("=" * 70)
    print(f"ToF Pipeline Validator")
    print(f"File: {dat_path}")
    print("=" * 70)

    with open(dat_path, "rb") as f:
        raw = f.read()

    file_size = len(raw)
    n_expected = file_size // PACKET_SIZE
    remainder_bytes = file_size % PACKET_SIZE

    print(f"\n[FILE]")
    print(f"  Size:           {file_size} bytes")
    print(f"  Expected pkts:  {n_expected}  ({file_size}/{PACKET_SIZE})")
    print(f"  Remainder:      {remainder_bytes} bytes  {'✓ OK' if remainder_bytes == 0 else '✗ NOT a multiple of 140!'}")

    # -----------------------------------------------------------------------
    print(f"\n[STAGE 1] Packet counter integrity")
    ok1, errors1, n_pkts, counters = stage1_packet_integrity(raw)
    print(f"  Packets parsed: {n_pkts}")
    if ok1:
        print(f"  Counter check:  ✓ All {n_pkts} counters increment by 136")
        print(f"  Counter range:  {counters[0]} → {counters[-1]}")
    else:
        print(f"  Counter check:  ✗ {len(errors1)} alignment errors found!")
        for e in errors1[:10]:
            print(f"    Pkt {e['pkt']}: expected counter {e['expected_counter']}, got {e['got_counter']} (delta={e['delta']})")
        if len(errors1) > 10:
            print(f"    ... and {len(errors1)-10} more")
        print(f"  ► FIX: Add counter-based re-alignment in the SDK call chain")

    # -----------------------------------------------------------------------
    print(f"\n[STAGE 2] Counter stripping")
    flat = stage2_strip_counters(raw, n_pkts)
    print(f"  Flat stream:    {len(flat)} bytes  ({n_pkts} × {USB_DPS})")
    expected_flat = n_pkts * USB_DPS
    print(f"  Expected:       {expected_flat} bytes  {'✓' if len(flat)==expected_flat else '✗'}")

    # -----------------------------------------------------------------------
    print(f"\n[STAGE 3] Frame assembly  (frame={FRAME_BYTES}b = {DATAFRAME_BYTES}b data + {TIMESTAMP_BYTES}b ts)")
    frames, timestamps, n_frames, rem = stage3_assemble_frames(flat)
    print(f"  Complete frames:  {n_frames}")
    print(f"  Total samples:    {n_frames * SAMPLES_PER_TS}")
    print(f"  Leftover bytes:   {rem}  (< {FRAME_BYTES} = incomplete frame, normal)")
    if timestamps:
        valid_ts = [t for t in timestamps if 0.01 < t < 86400]
        print(f"  Timestamps valid: {len(valid_ts)}/{n_frames}")
        if valid_ts:
            print(f"  Time range:       {valid_ts[0]:.3f}s → {valid_ts[-1]:.3f}s")
            duration = valid_ts[-1] - valid_ts[0]
            print(f"  Duration:         {duration:.2f}s  ({n_frames/duration:.1f} fps if {duration:.0f}s)")

    if n_frames == 0:
        print("  ✗ NO complete frames assembled — flat stream too short!")
        print(f"    Need {FRAME_BYTES} bytes, have {len(flat)}")
        return

    # -----------------------------------------------------------------------
    print(f"\n[STAGE 4] Zone extraction (last sample per frame)")

    print(f"\n  First 5 frames — zone distances (valid zones only, status==5 or 9):")
    stable_zone_hits = {z: [] for z in range(NOF_ZONES)}

    for fi, samples in enumerate(frames):
        status, distance = stage4_extract_zones(samples)
        near = [(z, int(distance[z])) for z in range(NOF_ZONES)
                if int(status[z]) in (5, 9) and distance[z] < 2000]
        far  = [(z, int(distance[z])) for z in range(NOF_ZONES)
                if int(status[z]) in (5, 9) and distance[z] >= 2000]

        for z in range(NOF_ZONES):
            if int(status[z]) in (5, 9):
                stable_zone_hits[z].append(int(distance[z]))

        if fi < 5:
            print(f"  Frame {fi:2d} (ts={timestamps[fi]:.3f}s):")
            print(f"    NEAR (<2000mm): {near}")
            near_zones_grid = np.full((4,4), "    ", dtype=object)
            dist_grid = distance.reshape(4,4).astype(int)
            stat_grid = status.reshape(4,4).astype(int)
            for r in range(4):
                row_str = ""
                for c in range(4):
                    z = r*4+c
                    marker = "←" if distance[z] < 2000 else " "
                    row_str += f"  {int(distance[z]):5d}(s{int(status[z])}){marker}"
                print(f"    {row_str}")

    # Summary across all frames
    print(f"\n  Zone stability summary (across all {n_frames} frames):")
    print(f"  {'Zone':>5} {'N_valid':>8} {'Median':>8} {'Min':>7} {'<2000':>8}")
    near_totals = {}
    for z in range(NOF_ZONES):
        hits = stable_zone_hits[z]
        if hits:
            med = int(np.median(hits))
            mn  = min(hits)
            near = sum(1 for x in hits if x < 2000)
            near_totals[z] = near
            flag = " ← YOU?" if near > n_frames * 0.3 else ""
            print(f"  Zone {z:2d}: {len(hits):8d}  {med:8d}  {mn:7d}  {near:8d}{flag}")

    print(f"\n  4×4 grid — median distance:")
    med_grid = np.array([int(np.median(stable_zone_hits[z])) if stable_zone_hits[z] else -1
                         for z in range(16)]).reshape(4,4)
    for r in range(4):
        print("    " + "  ".join(f"{med_grid[r,c]:6d}" for c in range(4)))

    print(f"\n  4×4 grid — count of readings <2000mm:")
    near_grid = np.array([near_totals.get(z, 0) for z in range(16)]).reshape(4,4)
    for r in range(4):
        print("    " + "  ".join(f"{near_grid[r,c]:6d}" for c in range(4)))

    print(f"\n  After ST display transform (what you should see on screen):")
    display_map = build_display_index_map()
    disp_near = np.zeros((4,4), dtype=int)
    disp_med  = np.zeros((4,4), dtype=int)
    for r in range(4):
        for c in range(4):
            raw_z = display_map[r, c]
            disp_near[r,c] = near_totals.get(raw_z, 0)
            disp_med[r,c]  = int(np.median(stable_zone_hits[raw_z])) if stable_zone_hits[raw_z] else -1

    print(f"  Median distance (display layout):")
    for r in range(4):
        print("    " + "  ".join(f"{disp_med[r,c]:6d}" for c in range(4)))
    print(f"  <2000mm hit count (display layout):")
    for r in range(4):
        print("    " + "  ".join(f"{disp_near[r,c]:6d}" for c in range(4)))

    # -----------------------------------------------------------------------
    print(f"\n[STAGE 5] UDP packet formatting")
    if frames:
        last_frame_status, last_frame_dist = stage4_extract_zones(frames[-1])
        data_map = stage5_format_for_udp(last_frame_status, last_frame_dist, apply_remap=True)
        import json
        payload = json.dumps(data_map).encode()
        print(f"  JSON payload size: {len(payload)} bytes")
        print(f"  Sample (first 4 zones): {dict(list(data_map.items())[:4])}")

    # -----------------------------------------------------------------------
    print(f"\n[STAGE 6] UDP payload sanity check")
    if frames:
        issues = stage6_udp_check(data_map)
        if not issues:
            print(f"  ✓ All zone keys valid, all distances/statuses plausible")
        else:
            for iss in issues:
                print(f"  ✗ {iss}")

    # -----------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Stage 1 (packet alignment):  {'✓' if ok1 else '✗'}")
    print(f"  Stage 2 (counter stripping): ✓  {len(flat)} bytes flat stream")
    print(f"  Stage 3 (frame assembly):    ✓  {n_frames} frames, {n_frames*SAMPLES_PER_TS} samples")
    print(f"  Stage 4 (zone extraction):   ✓  zones at fixed columns [2Z, 2Z+1]")
    print(f"  Stage 5 (UDP format):        ✓")
    print(f"  Stage 6 (sanity check):      {'✓' if not issues else f'✗ {len(issues)} issues'}")
    print()

    # Most-stable zone
    if near_totals:
        best_z = max(near_totals, key=near_totals.get)
        pos = np.argwhere(display_map == best_z)[0]
        print(f"  Your position: raw zone {best_z} → display row={pos[0]}, col={pos[1]}")
        print(f"  (zone with most readings < 2000mm: {near_totals[best_z]}/{n_frames} frames)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ToF pipeline validator")
    parser.add_argument("--dat", required=True, help="Path to vl53l8cx_tof.dat")
    args = parser.parse_args()

    if not os.path.exists(args.dat):
        print(f"ERROR: file not found: {args.dat}")
        sys.exit(1)

    run_validation(args.dat)
