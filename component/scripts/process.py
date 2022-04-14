import os
import shutil
import re
import time

from datetime import datetime as dt
from datetime import timedelta
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pyproj
import geopandas as gpd
import fiona
from osgeo import gdal
import rasterio as rio
from rasterio.merge import merge
from rasterio.features import shapes
import geemap

from ost import Sentinel1Batch
from ost.helpers import scihub, srtm

from component import parameter as pm


def check_product_on_asf(identifier, uname, pword):
    
    url = f"https://datapool.asf.alaska.edu/SLC/SA/{identifier}.zip"
    with requests.Session() as session:
        session.auth = (uname, pword)
        request = session.request("get", url)
        response = session.get(request.url, auth=(uname, pword), stream=True)
        return response.status_code
    
    
def check_computer_size():
    """check if the computer size will match the reuirements of the app"""

    # we get available ram
    with open("/proc/meminfo") as f:
        meminfo = f.read()
        matched = re.search(r"^MemTotal:\s+(\d+)", meminfo)

    if matched:
        mem_total_kB = int(matched.groups()[0])

    # we check if available ram and cpus are enough
    if mem_total_kB / 1024 / 1024 < 30 or os.cpu_count() < 4:
        raise Exception(
            "WARNING: You should run this notebook with an instance of at least 32Gb of Ram and 4 CPUs."
        )

    return


def create_dmp(aoi_model, model, output):

    output.add_live_msg('Initializing DPM creation')
    # create start date from 60 days before
    event_start = dt.strptime(model.event_start, "%Y-%m-%d")
    event_end = dt.strptime(model.event_end, "%Y-%m-%d")

    # set a period around start and end date for data search
    search_start = dt.strftime(event_start + timedelta(days=-60), '%Y-%m-%d')
    search_end = dt.strftime(event_end + timedelta(days=30), '%Y-%m-%d')

    # define project dir
    if event_start == event_end:
        project_dir = pm.result_dir / f"{aoi_model.name}_{model.event_start}"
    else:
        project_dir = pm.result_dir / f"{aoi_model.name}_{model.event_start}_{model.event_end}"

    aoi = aoi_model.gdf.dissolve().geometry.to_wkt().values[0]
    
    output.add_live_msg(" Setting up OST project")
    s1_slc = Sentinel1Batch(
        project_dir=project_dir,
        aoi=aoi,
        start=search_start,
        end=search_end,
        product_type="SLC",
        ard_type="OST-RTC",
    )

    # set tmp_dir
    s1_slc.temp_dir = pm.tmp_dir
    s1_slc.config_dict["temp_dir"] = pm.tmp_dir

    ## we get available ram
    #with open('/proc/meminfo') as f:
    #    meminfo = f.read()
    #    matched = re.search(r'^MemTotal:\s+(\d+)', meminfo)
    #
    #if matched:
    #    mem_total_kB = int(matched.groups()[0])
    #
    ## if we have more than 100GB ram we download there,
    ## that should speed up processing
    #if mem_total_kB/1024/1024 > 100:
    #    print('Using ramdisk')
    #    s1_slc.download_dir = '/ram/download'
    #    Path(s1_slc.download_dir).mkdir(parents=True, exist_ok=True)
    #    s1_slc.config_dict['download_dir'] = s1_slc.download_dir
    
    # get username and password
    from ost.helpers.settings import HERBERT_USER

    if model.username and model.password:
        s1_slc.scihub_uname = model.username
        s1_slc.scihub_pword = model.password
    else:
        s1_slc.scihub_uname = HERBERT_USER["uname"]
        s1_slc.scihub_pword = HERBERT_USER["pword"]

    s1_slc.asf_uname = HERBERT_USER["uname"]
    s1_slc.asf_pword = HERBERT_USER["asf_pword"]

    output.add_live_msg(" Searching for data")

    s1_slc.search(base_url="https://scihub.copernicus.eu/dhus/")
    
    for i, track in enumerate(s1_slc.inventory.relativeorbit.unique()):
        
        # filter by track
        df = s1_slc.inventory[s1_slc.inventory.relativeorbit == track].copy()
        
        # make sure all products are on ASF
        for i, row in df.iterrows():
            status = check_product_on_asf(row.identifier, s1_slc.asf_uname, s1_slc.asf_pword)
            if status != 200:
                df = df[df.identifier != row.identifier]
                
        # get all acquisitions dates for that track
        datelist = sorted([dt.strptime(date, '%Y%m%d') for date in df.acquisitiondate.unique()])
        to_process_list = []
        for date in datelist:
            
            # cehck if we have an image after end date
            if datelist[-1] < event_end:
                 output.add_live_msg(f' No image available after the end date for track {track}')
                break
                
            # ignore dates before start of event
            if date < event_start:
                continue
            
            # get index of date in datelist
            idx = datelist.index(date)
            if idx < 2:
                 output.add_live_msg(f' Not enough pre-event images available for track {track}')
                break
            
            # add dates to process list, if not already there
            # we take care of the two images needed before the start date
            [to_process_list.append(date) for date in datelist[idx-2:idx+1] if date not in to_process_list]
    
            # once we added the last image after the the end of the event we can stop
            if date >= event_end:
                break
        
            if len(to_process_list) < 3:
                 output.add_live_msg(f' Not enough images available for track {track}')
                break

        # turn the dates back to strings so we can use to filter the data inventory
        final_dates = [dt.strftime(date, '%Y%m%d') for date in to_process_list]
        final_df = s1_slc.inventory[
            (s1_slc.inventory.acquisitiondate.isin(final_dates)) &
            (s1_slc.inventory.relativeorbit == track)
        ]
        output.add_live_msg(
            " Downloading relevant Sentinel-1 SLC scenes ... (this may take a while)"
        )
        s1_slc.download(
            final_df,
            mirror=2,
            concurrent=10,
            uname=s1_slc.asf_uname,
            pword=s1_slc.asf_pword,
        )
        
        output.add_live_msg(" Create burst inventory")
        s1_slc.create_burst_inventory(final_df)

        # setting ARD parameters
        output.add_live_msg(" Setting processing parameters")
        s1_slc.ard_parameters["single_ARD"]["resolution"] = 30  # in metres
        s1_slc.ard_parameters["single_ARD"]["create_ls_mask"] = False
        s1_slc.ard_parameters["single_ARD"]["backscatter"] = False
        s1_slc.ard_parameters["single_ARD"]["coherence"] = True
        s1_slc.ard_parameters["single_ARD"]["coherence_bands"] = "VV"  # 'VV, VH'

        # production of polarimetric layers
        s1_slc.ard_parameters["single_ARD"][
            "H-A-Alpha"
        ] = False  # does not give a lot of additional information

        # resampling of image (not so important)
        s1_slc.ard_parameters['single_ARD']['dem']['dem_name'] = "SRTM 1Sec HGT"
        s1_slc.ard_parameters['single_ARD']['dem']['image_resampling'] = 'BILINEAR_INTERPOLATION'  # 'BILINEAR_INTERPOLATION'

        # multi-temporal speckle filtering is quite effective
        s1_slc.ard_parameters['time-series_ARD']['mt_speckle_filter']['filter'] = 'Boxcar'
        s1_slc.ard_parameters['time-series_ARD']['remove_mt_speckle'] = True
        s1_slc.ard_parameters['time-scan_ARD']['metrics'] = ['min', 'max']
        s1_slc.ard_parameters['time-scan_ARD']['remove_outliers'] = False
        s1_slc.ard_parameters['mosaic']['cut_to_aoi'] = True

        # set number of parallel processing 
        workers = int(4) if os.cpu_count() / 4 > 4 else int(os.cpu_count() / 4)
        output.add_live_msg(f" We process {workers} bursts in parallel.")
        s1_slc.config_dict["max_workers"] = workers
        s1_slc.config_dict["executor_type"] = "concurrent_processes"
        
        # set tmp_dir
        s1_slc.config_dict['temp_dir'] = '/ram'
        
        # pre-download SRTM
        srtm.download_srtm(s1_slc.aoi)
        
        # process
        output.add_live_msg("Processing... (this may take a while)")
        s1_slc.bursts_to_ards(
            timeseries=True, 
            timescan=True, 
            mosaic=False,
            overwrite=False # TO BE CHAGNED
        )
        
        
        output.add_live_msg("calculate change and merge results")
        bursts = list(s1_slc.processing_dir.glob(f'[A,D]*{track}*'))
        
        for burst in bursts:
            
            # get track
            track_name = burst.name[:4]

            # in and out files
            coh_min = burst.joinpath('Timescan/01.coh.VV.min.tif')
            coh_max = burst.joinpath('Timescan/02.coh.VV.max.tif')
            dstnt_file = burst.joinpath(f"Timescan/ccd_{burst.name}.tif")
            
            with rio.open(coh_max) as pre_coh:
                pre_arr = pre_coh.read()
                
                # get metadata for destination file
                meta = pre_coh.meta
                meta.update(dtype='uint8', nodata=0)
            
                with rio.open(coh_min) as post_coh:
                    post_arr = post_coh.read()

                    # calulate difference
                    coh_diff = np.subtract(pre_arr, post_arr)
                    coh_diff[coh_diff < 0.27] = 0
                    coh_diff = coh_diff * 100
 
                    with rio.open(dstnt_file, 'w', **meta) as dstnt:
                        dstnt.write(coh_diff.astype('uint8'))  
            
        # -----------------------------------------
        # and merge the result
        src_files_to_mosaic = []
        for file in s1_slc.processing_dir.glob(f"*[A,D]*{track}_*/Timescan/ccd*tif"):
            src = rio.open(file)
            src_files_to_mosaic.append(src)


        mosaic, out_trans = merge(src_files_to_mosaic)
        out_meta = src.profile.copy()

        # Update the metadata
        out_meta.update(
            driver='GTiff',
            height=mosaic.shape[1],
            width= mosaic.shape[2],
            transform=out_trans,
            crs=src.crs,
            tiled=True,
            blockxsize=128,
            blockysize=128,
            compress='lzw'
        )

        tmp_dir = Path(s1_slc.config_dict['temp_dir'])
        tmp_mrg = tmp_dir.joinpath(f"ccd_{track_name}.tif")
        with rio.open(tmp_mrg, "w", **out_meta) as dest:
            dest.write(mosaic)

        # close datasets
        [src.close for src in src_files_to_mosaic]

        # crop to aoi (some ost routine)
        shapes_ = [row.geometry for _, row in aoi_model.gdf.iterrows()]

        with rio.open(tmp_mrg) as src:
            out_image, out_transform = rio.mask.mask(src, shapes_, crop=True)
            out_meta = src.profile

        out_meta.update(
            {
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
            }
        )

        # create final output directory
        dpm_out_dir = project_dir / f"Damage_Proxy_Maps"
        dpm_out_dir.mkdir(parents=True, exist_ok=True)
        out_ds_tif = dpm_out_dir / f"ccd_{track_name}.tif"
        with rio.open(out_ds_tif, "w", **out_meta) as dest:
            dest.write(out_image)

        # delete tmpmerge
        tmp_mrg.unlink()
        # -----------------------------------------

        # -----------------------------------------
        # kmz and dmp output
        # write a color file to tmp
        ctfile = tmp_dir.joinpath("colourtable.txt")
        f = open(ctfile, "w")
        ct = [
            "0 0 0 0 0\n"
            "27 253 246 50 255\n"
            "35 253 169 50 255\n"
            "43 253 100 50 255\n"
            "51 253 50 50 255\n"
            "59 255 10 10 255\n"
            "255 253 0 0 255"
        ]
        f.writelines(ct)
        f.close()

        out_dpm_tif = dpm_out_dir / f"dpm_{track_name}.tif"
        demopts = gdal.DEMProcessingOptions(
            colorFilename=str(ctfile), addAlpha=True
        )
        gdal.DEMProcessing(
            str(out_dpm_tif), str(out_ds_tif), "color-relief", options=demopts
        )

        opts = gdal.TranslateOptions(
            format="KMLSUPEROVERLAY", creationOptions=["format=png"]
        )
        gdal.Translate(
            str(out_dpm_tif.with_suffix(".kmz")), str(out_dpm_tif), options=opts
        )

        ### adding legend like this to KMZ
        # added = [
        #    "\t\t<ScreenOverlay>\n",
        #    "\t\t\t<name>\n",
        #    "Legend: Damage Proxy Map\n",
        #    "\t\t\t</name>\n",
        #    "\t\t\t<Icon>\n",
        #    "\t\t\t\t<href>https://raw.githubusercontent.com/12rambau/damage_proxy_map/refactoring/component/message/legend.png</href>\n",
        #    "\t\t\t</Icon>\n",
        #    '\t\t\t<overlayXY x="0.98" y="0.14" xunits="fraction" yunits="fraction"/>\n',
        #    '\t\t\t<screenXY x="0.98" y="0.14" xunits="fraction" yunits="fraction"/>\n',
        #    '\t\t\t<rotationXY x="0.5" y="0.5" xunits="fraction" yunits="fraction"/>\n',
        #    '\t\t\t<size x="0.1" y="0.18" xunits="fraction" yunits="fraction"/>\n',
        #    "\t\t</ScreenOverlay>\n",
        #    "\t</Document>\n",
        #    "</kml>\n"
        # ]
        # tmpzip = tmp_dir.joinpath('zipped')
        # tmpzip.mkdir(parents=True, exist_ok=True)
        #
        # with ZipFile(out_dmp_tif.with_suffix('.kmz')) as zip_ref:
        #    zip_ref.extractall(tmpzip)
        #    with open(tmpzip.joinpath('doc.kml')) as f:
        #
        #        lines = f.readlines()
        #        lines = lines[:-2]
        #        lines.extend(added)
        #
        #    with open(tmpzip.joinpath('doc.kml'), 'w') as f:
        #        for ele in lines:
        #            f.write(ele)
        #
        # with ZipFile(out_dmp_tif.with_suffix('.kmz'), 'w') as zip_ref:
        #    # Iterate over all the files in directory
        #    for folderName, subfolders, filenames in os.walk(tmpzip):
        #        for filename in filenames:
        #           #create complete filepath of file in directory
        #           filePath = os.path.join(folderName, filename)
        #           # Add file to zip
        #           zip_ref.write(filePath, os.path.join('/0/0/', os.path.basename(filePath)))
        #        # -----------------------------------------

        # -----------------------------------------
        # polygonize (to points)
        with rio.open(out_ds_tif) as src:
            image = src.read()
            mask = image != 0

            geoms = [
                {"properties": {"raster_val": v}, "geometry": s}
                for i, (s, v) in enumerate(
                    shapes(image, mask=mask, transform=src.transform)
                )
            ]

        # geoms = list(results)
        gpd_polygonized_raster = gpd.GeoDataFrame.from_features(geoms)
        gpd_polygonized_raster["geometry"] = gpd_polygonized_raster[
            "geometry"
        ].centroid
        gpd_polygonized_raster.to_file(
            out_dpm_tif.with_suffix(".geojson"), driver="GeoJSON"
        )

        # remove storage intense files
        try:
            [file.unlink() for file in Path(s1_slc.download_dir).glob("**/*zip")]
            [
                file.unlink()
                for file in Path(s1_slc.download_dir).glob("**/*downloaded")
            ]
            [file.unlink() for file in Path(s1_slc.processing_dir).glob("**/*img")]
            [file.unlink() for file in Path(s1_slc.processing_dir).glob("**/*tif")]
            [
                file.unlink()
                for file in Path(s1_slc.processing_dir).glob("**/*processed")
            ]

        except:
            pass
        # -----------------------------------------

    try:
        shutil.rmtree(s1_slc.download_dir)
        shutil.rmtree(s1_slc.processing_dir)
    except:
        pass

    return
