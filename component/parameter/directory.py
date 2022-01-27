from pathlib import Path

project_dir = Path("~", "test_dpm").expanduser()
tmp_dir = "/ram/process_tmp"
Path(tmp_dir).mkdir(parents=True, exist_ok=True)


result_dir = Path.home() / f"module_results/Damage_Proxy_Maps"
result_dir.mkdir(parents=True, exist_ok=True)


process = """  
## Processing

 

"""
