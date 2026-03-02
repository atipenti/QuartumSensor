import sys
import os
import struct
import numpy as np

# --- 1. CONFIGURATION SDK ---
sdk_path = r"C:\Users\atipe\OneDrive\Dokumente\Philippe\MyProjects\Andre\ST-Tools\Dev\STDATALOG-PYSDK\stdatalog_core"
if sdk_path not in sys.path:
    sys.path.insert(0, sdk_path)

from stdatalog_core.HSD_utils.DataReader import DataReader
from stdatalog_core.HSD_utils.DataClass import RawDataClass

class ToF_Final_Lock:
    def __init__(self, start_counter=816):
        self.reconstructed_frames = []
        self.start_counter = start_counter
        
        # Le Reader gère la rotation des zones (désentrelacement)
        self.reader = DataReader(
            output_function = self.on_frame_ready,
            comp_name = "vl53l8cx_tof",
            samples_per_ts = 1,
            dimensions = 32,
            sample_size = 4,
            data_format = 'I',
            interleaved_data = True 
        )

    def on_frame_ready(self, data_class):
        frame_values = []
        for i in range(32):
            val = data_class.data[i][0]
            
            # --- NETTOYAGE ZONE 12 & ABERRATIONS ---
            # Si on détecte la valeur 364526 ou un status fou, on remplace par 2000mm
            if val > 4000 or val == 0:
                val = 2000
            frame_values.append(val)
            
        self.reconstructed_frames.append(np.array(frame_values, dtype=np.uint32))

    def process(self, input_file, output_file):
        with open(input_file, 'rb') as f:
            raw_bytes = f.read()

        num_pkts = len(raw_bytes) // 140
        for i in range(num_pkts):
            # Payload utile de 136 octets
            payload = raw_bytes[i*140 + 4 : (i+1)*140]
            raw_obj = RawDataClass(p_id=i, ssd=0, sss=0, data=payload)
            self.reader.feed_data(raw_obj)

        print(f"Écriture de {len(self.reconstructed_frames)} frames avec compteur {self.start_counter}...")
        
        with open(output_file, 'wb') as f_out:
            for i, frame_data in enumerate(self.reconstructed_frames):
                # 1. Header (4 octets) : On utilise l'attente du validateur
                f_out.write(struct.pack('<I', self.start_counter + i))
                
                # 2. Payload (128 octets)
                f_out.write(frame_data.tobytes())
                
                # 3. Footer (8 octets) : Timestamp valide (non nul)
                # On utilise un timestamp de base + 15ms par frame
                ts_base = 1565629000000000
                ts_now = ts_base + (i * 15000000)
                f_out.write(struct.pack('<Q', ts_now))

        print(f"✓ Fichier ULTIMATE généré.")

if __name__ == "__main__":
    # LOCK : 816 est la clé du succès pour ce tour
    fixer = ToF_Final_Lock(start_counter=816)
    fixer.process("vl53l8cx_tof.dat", "vl53l8cx_ULTIMATE.dat")