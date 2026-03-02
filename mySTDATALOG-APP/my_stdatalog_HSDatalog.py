import struct
import os

FILE_PATH = "vl53l8cx_tof.dat"

def stream_tof_fixed():
    if not os.path.exists(FILE_PATH):
        print("Fichier introuvable.")
        return

    print("🔍 Scan du flux VL53L8CX (Format: Status[16] -> TS[8] -> Dist[16])...")
    
    with open(FILE_PATH, "rb") as f:
        # On lit tout le contenu pour cette analyse
        data = f.read()

    # On cherche les index des timestamps
    # Un timestamp dans tes logs est un uint32 qui augmente de 272
    # On va chercher les séquences où l'on a 16 uint32 suivis de 16 uint32
    
    i = 0
    count = 0
    while i < len(data) - 136:
        # On tente de lire un bloc potentiel
        # Structure supposée d'après tes logs: 
        # [64 octets Status] [8 octets TS] [64 octets Distances]
        
        # Le TS est à l'offset i + 64
        ts_low = struct.unpack("<I", data[i+64 : i+68])[0]
        
        # Filtre pour trouver le TS (il doit être assez grand et cohérent)
        if 100 < ts_low < 1000000:
            # On a trouvé un Timestamp !
            # Les 16 distances sont juste après (offset i + 72)
            dist_data = data[i+72 : i+136]
            if len(dist_data) == 64:
                distances = struct.unpack("<16I", dist_data)
                
                # Optionnel : récupérer les statuts qui étaient juste avant (offset i)
                status_data = data[i:i+64]
                statuses = struct.unpack("<16I", status_data)
                
                # Affichage
                dist_str = " | ".join(f"{d:4}" for d in distances)
                print(f"TS:{ts_low:06d} | DIST | {dist_str}")
                
                # On avance de 136 octets (la taille d'un paquet complet)
                i += 136
                count += 1
                continue
        
        # Si on n'a pas trouvé, on avance de 4 octets pour chercher plus loin
        i += 4

    print(f"\n✅ Analyse terminée. {count} paquets extraits.")

if __name__ == "__main__":
    stream_tof_fixed()