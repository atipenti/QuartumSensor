import time
from stdatalog_core.HSD_link.HSDLink import HSDLink
from stdatalog_core.HSD_utils.DataReader import DataReader
from stdatalog_core.HSD.utils.type_conversion import TypeConversion

# Simple callback to handle the decoded data
def my_output_function(data_packet):
    comp_name = data_packet.comp_name
    data_dict = data_packet.data
    
    if "tof" in comp_name:
        valid_distances = []
        # Create an 8x8 grid for visualization
        grid = ""
        
        for i in range(64):
            dist = data_dict[i][0]
            # Filter out noise, the '255' glitch, and impossible high values
            if 40 < dist < 4000 and dist != 255 and dist != 850:
                valid_distances.append(dist)
                # Visual: '#' for close, '.' for far
                grid += "# " if dist < 200 else "+ " if dist < 600 else ". "
            else:
                grid += "  "
            
            if (i + 1) % 8 == 0: grid += "\n" # New line every 8 zones
        
        if valid_distances:
            avg = sum(valid_distances) / len(valid_distances)
            print(f"\n--- ToF 8x8 Visual Map ---")
            print(grid)
            print(f"Stats -> Avg: {avg:4.0f}mm | Valid Zones: {len(valid_distances)}/64")
        
    elif "tmos" in comp_name:
        presence = "DETECTED" if data_dict.get(1, [0])[0] > 0 else "empty   "
        motion   = "MOVING"   if data_dict.get(2, [0])[0] > 0 else "STILL "
        print(f">> [TMOS ALERT] Presence: {presence} | Activity: {motion}")

def main():
    hsd_factory = HSDLink()
    hsd_link = hsd_factory.create_hsd_link(dev_com_type='st_hsd')

    if hsd_link is None:
        print("Device not found.")
        return

    dev_id = 0
    enabled_sensors = ["vl53l8cx_tof", "sths34pf80_tmos", "vd6283tx_als"]
    
    status = hsd_link.get_device_status(dev_id)
    readers = {}

    print("\n--- Initializing Readers ---")
    for comp_dict in status["devices"][0]["components"]:
        name = list(comp_dict.keys())[0]
        if name in enabled_sensors:
            details = comp_dict[name]
            
            # Metadata extraction
            d_type = details.get("data_type", "int16_t")
            s_per_ts = details.get("samples_per_ts", 1)
            dim = details.get("dim", 1)
            sensitivity = details.get("sensitivity", 1.0)
            
            # Use SDK conversion tools
            s_size = TypeConversion.check_type_length(d_type)
            f_char = TypeConversion.get_format_char(d_type)

            # DataReader Argument Mapping:
            # 1. output_function: my_output_function
            # 2. comp_name: name
            # 3. samples_per_ts: s_per_ts
            # 4. dimensions: dim
            # 5. sample_size: s_size
            # 6. data_format: f_char
            # 7. sensitivity: sensitivity
            # 8. interleaved_data: True
            # 9. flat_raw_data: False
            readers[name] = DataReader(
                my_output_function, 
                name,               
                s_per_ts,           
                dim,                
                s_size,             
                f_char,             
                sensitivity,        
                True,               
                False               
            )
            print(f"Initialized reader for: {name}")

    print("\n--- Starting Stream ---")
    hsd_link.start_log(dev_id)

    try:
        # Stream for 10 seconds
        stop_time = time.time() + 10
        while time.time() < stop_time:
            for name in enabled_sensors:
                res = hsd_link.get_sensor_data(dev_id, name)
                if res:
                    _, raw_bytes = res
                    if raw_bytes:
                        # Feed raw bytes to DataReader
                        # Note: DataReader.feed_data expects an object with a .data attribute
                        # We use a simple lambda or class to wrap the bytes
                        class DataWrapper:
                            def __init__(self, b): self.data = b
                        
                        readers[name].feed_data(DataWrapper(raw_bytes))
            time.sleep(0.01)
    finally:
        hsd_link.stop_log(dev_id)
        print("\nStream stopped.")

if __name__ == "__main__":
    main()