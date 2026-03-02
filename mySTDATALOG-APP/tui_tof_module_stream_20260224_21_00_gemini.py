import sys
import os
import time
import struct

# --- PFAD-FIX ---
TUI_DIR = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK\stdatalog_examples\gui_applications\stdatalog\TUI"
if TUI_DIR not in sys.path: sys.path.append(TUI_DIR)

from stdatalog_TUI import HSDInfo

def run_surgical_alignment_logger(duration_sec=10):
    flags = HSDInfo.TUIFlags(output_folder="Validation_Log", sub_datetime_folder=True, 
                             acq_name="ToF_Final_Fix", acq_desc="4Byte_Shift_Correction",
                             file_config='', ucf_file='', ispu_out_fmt='', 
                             time_sec=duration_sec, interactive_mode=False)
    
    hsd = HSDInfo(flags)
    hsd.selected_device_id = 0
    hsd.update_sensor_list()
    hsd.check_output_folder()
    
    comp_name = "vl53l8cx_tof"
    output_file = os.path.join(hsd.output_acquisition_path, "vl53l8cx_tof.dat")

    print("[*] Starte ST-Engine...")
    hsd.start_log()
    
    # Wir erfassen die Daten in einem Buffer, um das Alignment zu korrigieren
    capture_buffer = b""
    start_t = time.time()
    
    print("[*] Erfasse Daten und korrigiere 4-Byte Shift...")
    
    while time.time() - start_t < duration_sec:
        res = hsd.hsd_link.get_sensor_data(0, comp_name)
        if res and res[1]:
            capture_buffer += res[1]
        time.sleep(0.005)

    hsd.stop_log()

    # --- DER CHIRURGISCHE EINGRIFF ---
    # Wir suchen im gesamten Buffer den ERSTEN Punkt, an dem 
    # ein valider Status (5 oder 9) an Position 8 steht.
    # Das repariert den Fehler aus Stage 5 (Distanz=5, Status=2285)
    
    final_offset = -1
    for i in range(len(capture_buffer) - 140):
        # Ein valides ST-ToF Paket: [4B Counter][4B Dist][4B Status]...
        # Also muss an Offset i+8 der Status (5 oder 9) stehen.
        status_candidate = struct.unpack('<I', capture_buffer[i+8 : i+12])[0]
        if status_candidate in [5, 9]:
            # Zusätzlicher Check: 140 Bytes weiter muss wieder ein Status sein
            next_status = struct.unpack('<I', capture_buffer[i+140+8 : i+140+12])[0]
            if next_status in [5, 9]:
                final_offset = i
                break

    if final_offset != -1:
        # Wir schneiden den Puffer so zu, dass er ein Vielfaches von 140 ist
        aligned_data = capture_buffer[final_offset:]
        excess = len(aligned_data) % 140
        if excess > 0:
            aligned_data = aligned_data[:-excess]
            
        with open(output_file, "wb") as f:
            f.write(aligned_data)
        
        print(f"[V] ERFOLG: Datei mit Offset {final_offset} synchronisiert.")
        print(f"[*] Größe: {len(aligned_data)} Bytes ({len(aligned_data)//140} Pakete).")
    else:
        print("[!] Fehler: Konnte kein stabiles Paket-Muster finden.")

if __name__ == "__main__":
    run_surgical_alignment_logger(10)