import numpy as np
import pandas as pd

def analyze_dat_file(file_path):
    packet_size = 140
    data_list = []
    
    print(f"Analysiere Datei: {file_path}...")
    
    with open(file_path, "rb") as f:
        content = f.read()
    
    offset = 0
    while offset + packet_size <= len(content):
        packet = content[offset : offset + packet_size]
        # Wir extrahieren Status (0,2,4...) und Distanz (1,3,5...)
        payload = np.frombuffer(packet[4:132], dtype=np.uint32)
        
        if len(payload) == 32:
            stat = payload[0::2][:16]
            dist = payload[1::2][:16]
            
            # Wir nehmen einen Frame aus der Mitte der Datei für die Anzeige
            data_list.append(dist)
        offset += packet_size

    # Wir schauen uns einen stabilen Frame an (z.B. den 50. Frame)
    if len(data_list) > 50:
        sample_frame = np.array(data_list[50]).reshape(4, 4)
        print("\nDein 4x4 Grid (Durchschnittswert aus der Aufnahme):")
        print("-" * 35)
        for row in sample_frame:
            print(" | ".join([f"{val:4d}mm" for val in row]))
        print("-" * 35)
        
        # Einfache Analyse
        center_val = sample_frame[1:3, 1:3].mean()
        if center_val < 1500:
            print(f"\nERGEBNIS: Du bist im Zentrum sichtbar ({center_val:.0f}mm)!")
        else:
            print("\nERGEBNIS: Im Zentrum ist nur Hintergrund. Du sitzt vermutlich am Rand.")
    else:
        print("Datei zu kurz für eine stabile Analyse.")

if __name__ == "__main__":
    # Hier den Namen deiner Datei eintragen
    analyze_dat_file("vl53l8cx_tof.dat")