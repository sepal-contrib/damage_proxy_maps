from pathlib import Path

project_dir = Path('~','test_dpm').expanduser()
tmp_dir = Path('/ram')

aoi = """  
###Area of Interest

Select a geo-refrenced vector file of your Area Of Interest (AOI) in an ogr-compatible format (e.g. shp, gpkg, geojson).

"""

date = """  
###Date selection

Pick the date where the disaster event happened.
"""

scihub = """  
### Scihub credentials

Provide your scihub credentials for search and download of the relevant Sentinel-1 scenes. If you do not have an account, go to [Copernicus Scihub](https://scihub.copernicus.eu/) and register.
"""

process = """  
## Processing

Clicking this button will trigger the full workflow. Some of the steps may take a while (e.g. download, processing), so be patient. If you suffer from an instable internet connection, make sure to set the minimum runtime of your instance to 2 hours. Otherwise make sure to keep the connection to the SEPAL website (i.e. do not close browser or browser tab).

**NOTE:** If the processing did not finish, you can re-run the module with the same parameters, and the processing will continue from where it stopped. 

"""