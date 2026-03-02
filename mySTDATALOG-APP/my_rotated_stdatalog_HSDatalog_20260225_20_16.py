import os
import sys
import numpy as np
import pandas as pd

# --- CONFIGURATION ---
SDK_PATH = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK\stdatalog_core"
ACQ_FOLDER = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\mySTDATALOG-APP"

if SDK_PATH not in sys.path:
    sys.path.append(SDK_PATH)

# --- MONKEY PATCH ---
if not hasattr(np, 'fromstring_original'):
    np.fromstring_original = np.fromstring
    np.fromstring = lambda *args, **kwargs: np.frombuffer(*args, **kwargs)

from stdatalog_core.HSD.HSDatalog_v2 import HSDatalog_v2

def reshape_to_gui_view(row):
    """
    Applique la rotation pour correspondre à la GUI (270° + Flip).
    Dans tes logs, le 1162mm est à droite mais au milieu.
    On pivote la matrice pour le remonter en haut à droite.
    """
    # 1. Extraction brute (Z0 à Z15)
    zones = [row[f'Distance Z{i}'] for i in range(16)]
    
    # 2. Mise en matrice 4x4 de base
    matrix = np.array(zones).reshape(4, 4)
    
    # 3. ROTATION DE 90° ANTI-HORAIRE (Equivaut à ton décalage constaté)
    # Cela va déplacer les valeurs de la droite vers le haut
    matrix = np.rot90(matrix, k=1) 
    
    return matrix

def main():
    print(f"--- Analyse ToF : Calibrage final Miroir GUI ---")
    
    try:
        hsd = HSDatalog_v2(ACQ_FOLDER)
        comp_name = "vl53l8cx_tof"
        
        df = hsd.get_dataframe(comp_name)
        
        if df is not None and not df.empty:
            last_frame = df.iloc[-1]
            matrix = reshape_to_gui_view(last_frame)
            
            print("\n" + "="*45)
            print("   GRILLE 4x4 (Vue MIROIR GUI)")
            print("="*45)
            print("         [C0]    [C1]    [C2]    [C3]")
            for i, row in enumerate(matrix):
                label = "HAUT" if i == 0 else "BAS " if i == 3 else "    "
                print(f"{label} | " + " | ".join(f"{val:6.0f}" for val in row))
            print("="*45)
            
            # Identification de la case Haut-Droite (C3 de la ligne HAUT)
            val_haut_droite = matrix[0, 3]
            print(f"\n🔍 Valeur en Haut à Droite : {val_haut_droite} mm")
            
            if val_haut_droite < 1500:
                print("✨ VICTOIRE ! La présence est bien affichée en Haut à Droite.")
            else:
                print("ℹ️ Si la présence est encore décalée, ajustez 'k' dans np.rot90")

            df.to_csv("extraction_miroir_finale.csv", index=False)
            
    except Exception as e:
        print(f"💥 Erreur : {e}")

if __name__ == "__main__":
    main()