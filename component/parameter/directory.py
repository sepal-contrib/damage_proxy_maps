from pathlib import Path

project_dir = Path('~','test_dpm').expanduser()
tmp_dir = Path('/ram')

result_dir = Path('~', 'Damage_Proxy_Maps').expanduser()
result_dir.mkdir(parents=True, exist_ok=True)


process = """  
## Processing

 

"""