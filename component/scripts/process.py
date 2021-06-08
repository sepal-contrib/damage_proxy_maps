import os, shutil
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
import gdal
import rasterio as rio
from rasterio.merge import merge
from rasterio.features import shapes
import geemap

from ost import Sentinel1Batch

from component import parameter as pm

def check_computer_size(output):
    """check if the computer size will match the reuirements of the app"""
    
    # we get available ram
    with open('/proc/meminfo') as f:
        meminfo = f.read()
        matched = re.search(r'^MemTotal:\s+(\d+)', meminfo)

    if matched: 
        mem_total_kB = int(matched.groups()[0])

    # we check if available ram and cpus are enough
    if mem_total_kB/1024/1024 < 30 or os.cpu_count() < 4:
        raise Exception('WARNING: You should run this notebook with an instance of at least 32Gb of Ram and 4 CPUs.')
        
    return


def remove_folder_content(folder):
    """A helper function that cleans the content of a folder

    :param folder:
    """

    for root, dirs, files in os.walk(folder):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            shutil.rmtree(os.path.join(root, d))
            
            
def create_dmp(io, output):
    
    # create start date from 60 days before
    event_date = dt.strptime(io.event, '%Y-%m-%d')
    
    start = dt.strftime(event_date + timedelta(days=-60), '%Y-%m-%d')
    end = dt.strftime((event_date + timedelta(days=+30)), '%Y-%m-%d') 
    
    # define project dir 
    aoi_name = Path(io.file).stem
    project_dir = Path().home().joinpath(f'module_results/Damage_Proxy_Maps/{io.event}_{aoi_name}')
    output.add_live_msg(' Setting up project')
    
    s1_slc = Sentinel1Batch(
        project_dir=project_dir,
        aoi = io.file,
        start = start,
        end = end,
        product_type='SLC',
        ard_type='OST-RTC'
    )

    # get username and password
    if io.username and io.password:
        s1_slc.scihub_uname = io.username
        s1_slc.scihub_pword = io.password 
    else:
        from ost.helpers.settings import HERBERT_USER
        s1_slc.scihub_uname = HERBERT_USER['uname']
        s1_slc.scihub_pword = HERBERT_USER['pword']

    output.add_live_msg(' Searching for data')
    s1_slc.search(base_url='https://scihub.copernicus.eu/dhus/')
    #s1_slc.inventory_file = s1_slc.inventory_dir.joinpath('full.inventory.gpkg')
    #s1_slc.read_inventory() 

    for i, track in enumerate(s1_slc.inventory.relativeorbit.unique()):
        # filter by track
        df = s1_slc.inventory[s1_slc.inventory.relativeorbit == track].copy()

        # get all acquisitions dates for that track
        datelist = sorted([dt.strptime(date, '%Y%m%d') for date in df.acquisitiondate.unique()])

        # get difference in dates
        date_diff = [int(str(date - event_date).split(' ')[0].split(':')[0]) for date in datelist]
        
        # get only the negative ones (i.e. before event)
        image_days = sorted([int(d) for d in date_diff if int(d) < 0])[-2:]
        
        # continue if not
        if len(image_days) != 2:
            output.add_live_msg(f' Not enough pre-event images available for track {track}', 'warning')
            time.sleep(2)
            continue

        output.add_live_msg(f' Including track {track} for processing')
        # get only positives one (ie. after evtn)
        
        #### we ignore images at the same day? #### or do we include, i.e. >= 0
        image_days.append(sorted([int(d) for d in date_diff if int(d) > 0])[0])
        print(image_days)

        if len(image_days) != 3:
            output.add_live_msg("""
                Not all imagery is yet available. </br>
                Processing the pre-event images for now </br>
                Continue processing after new imagery is available
            """)
            
        ####################################################
        ##     Add an info when this will be the case     ##
        ####################################################

        idx = [True if date in image_days else False for date in date_diff]

        final_dates = [dt.strftime(date, '%Y%m%d') for date in np.array(datelist)[np.array(idx) == True]]

        #if i == 0:
        final_df = s1_slc.inventory[
            (s1_slc.inventory.acquisitiondate.isin(final_dates)) &
            (s1_slc.inventory.relativeorbit == track)
        ]
        #else:
        #    final_df = final_df.append(
        #        s1_slc.inventory[
        #            (s1_slc.inventory.acquisitiondate.isin(final_dates)) &
        #            (s1_slc.inventory.relativeorbit == track)
        #       ]
        #    )

        output.add_live_msg(' Downloading relevant Sentinel-1 SLC scenes ... (this may take a while)')
        s1_slc.download(final_df, mirror=1, concurrent=2, uname=s1_slc.scihub_uname, pword=s1_slc.scihub_pword)
        output.add_live_msg(' Create burst inventory')
        s1_slc.create_burst_inventory(final_df)

        # setting ARD parameters
        output.add_live_msg(' Setting processing parameters')
        s1_slc.ard_parameters['single_ARD']['resolution'] = 30 # in metres
        s1_slc.ard_parameters['single_ARD']['create_ls_mask'] = False
        s1_slc.ard_parameters['single_ARD']['backscatter'] = False
        s1_slc.ard_parameters['single_ARD']['coherence'] = True
        s1_slc.ard_parameters['single_ARD']['coherence_bands'] = 'VV'  # 'VV, VH'

        # production of polarimetric layers
        s1_slc.ard_parameters['single_ARD']['H-A-Alpha'] = False # does not give a lot of additional information

        # resampling of image (not so important)
        s1_slc.ard_parameters['single_ARD']['dem']['image_resampling'] = 'BICUBIC_INTERPOLATION'  # 'BILINEAR_INTERPOLATION'

        # multi-temporal speckle filtering is quite effective
        s1_slc.ard_parameters['time-series_ARD']['mt_speckle_filter']['filter'] = 'Boxcar'
        s1_slc.ard_parameters['time-series_ARD']['remove_mt_speckle'] = True
        s1_slc.ard_parameters['mosaic']['cut_to_aoi'] = True

        # set tmp_dir
        s1_slc.config_dict['temp_dir'] = str(pm.tmp_dir)

        #
        workers = int(4) if os.cpu_count()/4 > 4 else int(os.cpu_count()/4)
        output.add_live_msg(f' We process {workers} bursts in parallel.')
        s1_slc.config_dict['max_workers'] = workers
        s1_slc.config_dict['executor_type'] = 'concurrent_processes'

        # process
        output.add_live_msg("Processing... (this may take a while)")
        s1_slc.bursts_to_ards(
            timeseries=True, 
            timescan=False, 
            mosaic=False,
            overwrite=False
        )

        if len(image_days) != 3:
            raise Exception("Something went wrong")
        else:
            output.add_live_msg("calculate change and merge results")
            bursts = list(s1_slc.processing_dir.glob(f'[A,D]*{track}*'))

            # we create the CCD for each burst 
            for burst in bursts:
                track_name = burst.name[:4]

                coh_1 = list(burst.glob('Timeseries/01.*coh.VV.tif'))[0]
                coh_2 = list(burst.glob('Timeseries/02.*coh.VV.tif'))[0]
                dates = sorted(
                    [coh_1.name.split('.')[1], 
                     coh_1.name.split('.')[2], 
                     coh_2.name.split('.')[2]]
                )
                dst_file = burst.joinpath(f"Timeseries/ccd_{burst.name}_{'_'.join(dates)}.tif")

                with rio.open(coh_1) as pre_coh:
                    pre_arr = pre_coh.read()

                with rio.open(coh_2) as post_coh:

                    post_arr = post_coh.read()
                    coh_diff = np.subtract(pre_arr, post_arr)
                    coh_diff[coh_diff < 0.27] = 0
                    coh_diff = coh_diff * 100


                    meta = pre_coh.meta
                    meta.update(dtype='uint8', nodata=0)

                with rio.open(dst_file, 'w', **meta) as dst:
                    dst.write(coh_diff.astype('uint8'))

            # -----------------------------------------
            # and merge the result
            src_files_to_mosaic = []
            for file in s1_slc.processing_dir.glob(f"*[A,D]*{track}_*/Timeseries/ccd*tif"):
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
            tmp_mrg = tmp_dir.joinpath(f"ccd_{track_name}_{'_'.join(dates)}.tif")
            with rio.open(tmp_mrg, "w", **out_meta) as dest:
                dest.write(mosaic)

            # crop to aoi (some ost routine)
            with fiona.open(io.file, "r") as shapefile:
                shapes_ = [feature["geometry"] for feature in shapefile]

            with rio.open(tmp_mrg) as src:
                out_image, out_transform = rio.mask.mask(src, shapes_, crop=True)
                out_meta = src.profile

            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })

            # create final output directory
            outdir = s1_slc.project_dir.joinpath('Damage_Proxy_Map')
            outdir.mkdir(parents=True, exist_ok=True)
            out_ds_tif = outdir.joinpath(f"ccd_{track_name}_{'_'.join(dates)}.tif")
            with rio.open(out_ds_tif, "w", **out_meta) as dest:
                dest.write(out_image)

            # delete tmpmerge 
            tmp_mrg.unlink()
            # -----------------------------------------


            # -----------------------------------------
            # kmz and dmp output
            # write a color file to tmp
            ctfile = tmp_dir.joinpath('colourtable.txt')
            f = open(ctfile, "w")
            ct = ["0 0 0 0 0\n"
                "27 253 246 50 255\n"
                "35 253 169 50 255\n"
                "43 253 100 50 255\n"
                "51 253 50 50 255\n"
                "59 255 10 10 255\n"
                "255 253 0 0 255"
                ]
            f.writelines(ct)
            f.close()

            out_dmp_tif = outdir.joinpath(f"dmp_{track_name}_{'_'.join(dates)}.tif")
            demopts = gdal.DEMProcessingOptions(colorFilename=str(ctfile), addAlpha=True)
            gdal.DEMProcessing(str(out_dmp_tif), str(out_ds_tif), 'color-relief', options=demopts)         

            opts = gdal.TranslateOptions(format='KMLSUPEROVERLAY', creationOptions=["format=png"])
            gdal.Translate(str(out_dmp_tif.with_suffix('.kmz')), str(out_dmp_tif), options=opts)

            ### adding legend like this to KMZ
            #added = [
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
            #]
            #tmpzip = tmp_dir.joinpath('zipped')
            #tmpzip.mkdir(parents=True, exist_ok=True)
#
            #with ZipFile(out_dmp_tif.with_suffix('.kmz')) as zip_ref:
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
            #with ZipFile(out_dmp_tif.with_suffix('.kmz'), 'w') as zip_ref:
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

                results = (
                        {
                            'properties': {'raster_val': v},
                            'geometry': s
                        }
                        for i, (s, v)
                        in enumerate(
                            shapes(image, mask=mask, transform=src.transform)
                        )
                )

            geoms = list(results)  
            gpd_polygonized_raster  = gpd.GeoDataFrame.from_features(geoms)
            gpd_polygonized_raster['geometry'] = gpd_polygonized_raster['geometry'].centroid
            gpd_polygonized_raster.to_file(out_dmp_tif.with_suffix('.geojson'), driver='GeoJSON')
            
            # delete downloads
            try:
                remove_folder_content(s1_slc.download_dir)
                remove_folder_content(s1_slc.processing_dir)
            except:
                pass
            
        # -----------------------------------------
    try:
        shutil.rmtree(s1_slc.download_dir)
        shutil.rmtree(s1_slc.processing_dir)  
    except:
        pass
    
    return