import os
import sys
import numpy as np

# --- MONKEY PATCH : Correction du bug SDK ST (Numpy compatibility) ---
if not hasattr(np, 'fromstring_original'):
    np.fromstring_original = np.fromstring
    np.fromstring = lambda *args, **kwargs: np.frombuffer(*args, **kwargs)

# Ajout du SDK au path
sdk_path = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK\stdatalog_core"
if sdk_path not in sys.path:
    sys.path.append(sdk_path)

from stdatalog_core.HSD.HSDatalog_v2 import HSDatalog_v2

def main():
    acq_folder = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\mySTDATALOG-APP"
    
    print(f"--- Extraction VL53L8CX via HSDatalog V2 ---")
    
    try:
        hsd = HSDatalog_v2(acq_folder)
        comp_name = "vl53l8cx_tof"
        
        # --- DEBUG : On regarde ce qu'il y a vraiment dans les capteurs ---
        sensors = hsd.get_sensor_list()
        if sensors and len(sensors) > 0:
            print(f"DEBUG: Premier capteur trouvé (clés disponibles) : {sensors[0].keys()}")
            # On cherche manuellement le capteur ToF dans la liste
            found = False
            for s in sensors:
                # On teste les clés communes en V2 : 'name', 'alias', 'c_name'
                current_name = s.get('name') or s.get('alias') or s.get('comp_name')
                if current_name == comp_name:
                    found = True
                    break
            
            if found or hsd.get_component(comp_name) is not None:
                print(f"✅ Capteur {comp_name} identifié. Lancement de get_dataframe...")
                
                # LA FONCTION QUE TU VEUX CREUSER
                df = hsd.get_dataframe(comp_name)
                
                if df is not None and not df.empty:
                    print("\n" + "="*30)
                    print("   SUCCÈS : DONNÉES EXTRAITES")
                    print("="*30)
                    print(df.head(10))
                    
                    output_csv = "extraction_vl53_finale.csv"
                    df.to_csv(output_csv, index=False)
                    print(f"\n💾 Fichier sauvegardé : {output_csv}")
                else:
                    print("❌ Le DataFrame est revenu vide.")
            else:
                print(f"❌ '{comp_name}' non trouvé. Liste des noms détectés :")
                for s in sensors:
                    print(f" - {s.get('name') or s.get('alias') or 'Nom inconnu'}")
        else:
            print("❌ Aucun capteur détecté dans l'acquisition.")

    except Exception as e:
        print(f"💥 Erreur : {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()