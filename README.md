![title](https://raw.githubusercontent.com/ESA-PhiLab/OST_Notebooks/master/auxiliary/header_image.PNG)

# damage proxy map
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Automatically produce Damage Proxy Maps based on Coherence Change Detection.

## Short description

This notebook provides a template for the creation of Damage Proxy Maps as proposed by [Tay et al. 2020](https://www.nature.com/articles/s41597-020-0443-5).

Module using the `sepal_ui` framework and an interactive **Voila** dashboard for the automated creation of Damage Proxy Maps as proposed by Tay et al. 2020. Underlying processing is done using the Open SAR Toolkit, which provides wrappers of ESA's Sentinel-1 toolbox. 


## Requirements

- a Copernicus Open Data Hub user account, valid for at least 7 days (https://scihub.copernicus.eu)

## Inputs

- AOI vector file

- Diaster event date


## Outputs

- GeoTiff of original CCD values
- Pseudocoloured GeoTiff DPM map file
- Pseudocoloured KMZ DPM map file
- GeoJSON DPM point layer with CCD values
