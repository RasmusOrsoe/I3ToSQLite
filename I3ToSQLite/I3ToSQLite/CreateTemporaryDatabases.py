'''

'''
import os, glob
from icecube import dataclasses, icetray, dataio
from icecube import genie_icetray
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
import sqlalchemy
import time
from multiprocessing import Pool
import pickle
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument("-config", "--config", type=str, required=True)
args = parser.parse_args()



def Contains_RetroReco(frame):
    try:
        frame['L7_reconstructed_zenith']
        return True
    except:
        return False
def If_Available(expression,frame):
    try:
        eval(expression)
        out = expression
    except:
        out = str(-1)
    return out

def Contains_Classifiers(frame):
    try:
        frame["L4_MuonClassifier_Data_ProbNu"].value
        return True
    except:
        return False


def Build_Standard_Extraction():
    standard_truths = {'energy': 'MCInIcePrimary.energy',
            'position_x': 'MCInIcePrimary.pos.x', 
            'position_y': 'MCInIcePrimary.pos.y', 
            'position_z': 'MCInIcePrimary.pos.z',
            'azimuth': 'MCInIcePrimary.dir.azimuth',
            'zenith': 'MCInIcePrimary.dir.zenith',
            'pid': 'MCInIcePrimary.pdg_encoding',
            'event_time': 'event_time',
            'sim_type': 'sim_type',
            'interaction_type': 'interaction_type',
            'elasticity': 'elasticity',
            'RunID': 'RunID',
            'SubrunID': 'SubrunID',
            'EventID': 'EventID',
            'SubEventID': 'SubEventID'}
    return standard_truths

def Case_Handle_This(frame, sim_type):
    if sim_type != 'noise':
        try:
            MCInIcePrimary = frame['MCInIcePrimary']
        except:
            MCInIcePrimary = frame['I3MCTree'][0]
    else:
        MCInIcePrimary = None
    try:
        interaction_type =  frame["I3MCWeightDict"]["InteractionType"]
    except:
        interaction_type = -1
    try:
        elasticity = frame['I3GENIEResultDict']['y']
    except:
        elasticity = -1 
    return MCInIcePrimary, interaction_type, elasticity

def is_montecarlo(frame):
    mc = True
    try:
        frame['MCInIcePrimary']
    except:
        try:
            frame['I3MCTree']
        except:
            mc = False
    return mc

def Build_Blank_Extraction():
    ## Please note that if the simulation type is pure noise or real that these values will be appended to the truth table
    blank_extraction = {'energy': '-1',
            'position_x': '-1', 
            'position_y': '-1', 
            'position_z': '-1',
            'azimuth': '-1',
            'zenith': '-1',
            'pid': '-1',
            'event_time': 'event_time',
            'sim_type': 'sim_type',
            'interaction_type': '-1',
            'elasticity': '-1',
            'RunID': 'RunID',
            'SubrunID': 'SubrunID',
            'EventID': 'EventID',
            'SubEventID': 'SubEventID'}
    return blank_extraction

def Build_RetroReco_Extraction(is_mc):
    retro_extraction = {'azimuth_retro': 'frame["L7_reconstructed_azimuth"].value',
                        'time_retro': 'frame["L7_reconstructed_time"].value',
                        'energy_retro': 'frame["L7_reconstructed_total_energy"].value', 
                        'position_x_retro': 'frame["L7_reconstructed_vertex_x"].value', 
                        'position_y_retro': 'frame["L7_reconstructed_vertex_y"].value',
                        'position_z_retro': 'frame["L7_reconstructed_vertex_z"].value',
                        'zenith_retro': 'frame["L7_reconstructed_zenith"].value',
                        'azimuth_sigma': 'frame["L7_retro_crs_prefit__azimuth_sigma_tot"].value',
                        'position_x_sigma': 'frame["L7_retro_crs_prefit__x_sigma_tot"].value',
                        'position_y_sigma': 'frame["L7_retro_crs_prefit__y_sigma_tot"].value',
                        'position_z_sigma': 'frame["L7_retro_crs_prefit__z_sigma_tot"].value',
                        'time_sigma': 'frame["L7_retro_crs_prefit__time_sigma_tot"].value',
                        'zenith_sigma': 'frame["L7_retro_crs_prefit__zenith_sigma_tot"].value',
                        'energy_sigma': 'frame["L7_retro_crs_prefit__energy_sigma_tot"].value',
                        'cascade_energy_retro': 'frame["L7_reconstructed_cascade_energy"].value',
                        'track_energy_retro': 'frame["L7_reconstructed_track_energy"].value',
                        'track_length_retro': 'frame["L7_reconstructed_track_length"].value',
                        'L7_MuonClassifier_FullSky_ProbNu': 'frame["L7_MuonClassifier_FullSky_ProbNu"].value',
                        'L4_MuonClassifier_Data_ProbNu': 'frame["L4_MuonClassifier_Data_ProbNu"].value',
                        'L4_NoiseClassifier_ProbNu': 'frame["L4_NoiseClassifier_ProbNu"].value',
                        'L7_PIDClassifier_FullSky_ProbTrack': 'frame["L7_PIDClassifier_FullSky_ProbTrack"].value'}

    if is_mc:
        retro_extraction['osc_weight'] = 'frame["I3MCWeightDict"]["weight"]'    
    return retro_extraction
def Extract_Retro(frame):
    contains_retro = Contains_RetroReco(frame)
    contains_classifier = Contains_Classifiers(frame)
    is_mc = is_montecarlo(frame)
    retro = {}
    if contains_retro or contains_classifier:
        retro_extraction = Build_RetroReco_Extraction(is_mc)
        for retro_variable in retro_extraction.keys():
            retro[retro_variable] = eval(If_Available(retro_extraction[retro_variable],frame)) 
    return retro

def Extract_Truth(frame, input_file, extract_these_truths = None):
    if extract_these_truths == None:
        extract_these_truths = Build_Standard_Extraction()
    mc = is_montecarlo(frame)
    sim_type = Find_Simulation_Type(mc,input_file)
    event_time =  frame['I3EventHeader'].start_time.utc_daq_time
    RunID, SubrunID, EventID, SubEventID = Extract_Event_IDs(frame)
    if mc:
        MCInIcePrimary, interaction_type, elasticity = Case_Handle_This(frame, sim_type)
        if MCInIcePrimary != None:
            ## is not noise
            truth = {}
            for truth_variable in extract_these_truths.keys():
                truth[truth_variable] = eval(extract_these_truths[truth_variable])
        else:
            print('Could Not Find Primary Particle')
    else:
        ## is real data or noise   
        blank_extraction = Build_Blank_Extraction()
        truth = {}
        for truth_variable in blank_extraction.keys():
            truth[truth_variable] = eval(blank_extraction[truth_variable])
    return truth

def Extract_Features(frame, key, gcd_dict,calibration):
    charge = []
    time   = []
    width  = []
    area   = []
    rqe    = []
    x       = []
    y       = []
    z       = []
    if key in frame.keys():
        data    = frame[key]
        try:
            om_keys = data.keys()
        except:
            try:
                if "I3Calibration" in frame.keys():
                    data = frame[key].apply(frame)
                    om_keys = data.keys()
                else:
                    frame["I3Calibration"] = calibration 
                    data = frame[key].apply(frame)
                    om_keys = data.keys()
            except:
                data = dataclasses.I3RecoPulseSeriesMap.from_frame(frame,key)
                om_keys = data.keys()
        for om_key in om_keys:
            pulses = data[om_key]
            for pulse in pulses:
                charge.append(pulse.charge)
                time.append(pulse.time) 
                width.append(pulse.width)
                area.append(gcd_dict[om_key].area)  
                rqe.append(frame["I3Calibration"].dom_cal[om_key].relative_dom_eff)
                x.append(gcd_dict[om_key].position.x)
                y.append(gcd_dict[om_key].position.y)
                z.append(gcd_dict[om_key].position.z)
        
    features = {'charge': charge, 
                'dom_time': time, 
                'dom_x': x, 
                'dom_y': y, 
                'dom_z': z,
                'width' : width,
                'pmt_area': area, 
                'rde': rqe}
    return features
    

def Find_Simulation_Type(mc, input_file):
    if mc == False:
        sim_type = 'data'
    else:
        sim_type = 'NuGen'
    if 'muon' in input_file:
        sim_type = 'muongun'
    if 'corsika' in input_file:
        sim_type = 'corsika'
    if 'genie' in input_file:
        sim_type = 'genie'
    if 'noise' in input_file:
        sim_type = 'noise'
    if sim_type == 'lol':
        print('SIM TYPE NOT FOUND!')
    return sim_type

def Load_GeoSpatial_Data(gcd_path):
    gcd_file = dataio.I3File(gcd_path)
    g_frame = gcd_file.pop_frame(icetray.I3Frame.Geometry)
    om_geom_dict = g_frame["I3Geometry"].omgeo
    calibration = gcd_file.pop_frame(icetray.I3Frame.Calibration)["I3Calibration"]
    return om_geom_dict, calibration  

def IsEmpty(features):
    if features['dom_x'] != None:
        return False
    else:
        return True

def Extract_Event_IDs(frame):
    RunID       = frame['I3EventHeader'].run_id
    SubrunID    = frame['I3EventHeader'].sub_run_id
    EventID     = frame['I3EventHeader'].event_id
    SubEventID  = frame['I3EventHeader'].sub_event_id
    return RunID, SubrunID, EventID, SubEventID

def Apply_Event_No(extraction, event_no_list, event_counter):
    out = pd.DataFrame(extraction.values()).T
    out.columns = extraction.keys()
    out['event_no'] = event_no_list[event_counter]
    return out

def Check_For_New_Columns(columns, biggest_columns):
    if len(columns) > len(biggest_columns):
        return columns
    else:
        return biggest_columns

def WriteDicts(settings):
    input_files,id,gcd_files,outdir , max_dict_size,event_no_list, pulse_map_keys,custom_truth, db_name,verbose = settings
    # Useful bits
    event_counter = 0
    feature_big = {}
    truth_big   = pd.DataFrame()
    retro_big   = pd.DataFrame()
    file_counter = 0
    output_count = 0
    gcd_count = 0
    for u in range(len(input_files)):
        input_file = input_files[u]
        gcd_dict, calibration = Load_GeoSpatial_Data(gcd_files[u])
        i3_file = dataio.I3File(input_file, "r")
        if verbose > 0:
            print('Worker %s Reading %s'%(id,input_file.split('/')[-1]))
            print(input_file)
            sys.stdout.flush()
        gcd_count  +=1
    
        while i3_file.more() :
            try:
                frame = i3_file.pop_physics()
            except:
                frame = False
            if frame :
                pulse_maps = {}
                for pulse_map_key in pulse_map_keys:
                    pulse_maps[pulse_map_key] = Extract_Features(frame,pulse_map_key, gcd_dict,calibration)
                   
                truths   = Extract_Truth(frame, input_file, custom_truth)
                truth    = Apply_Event_No(truths, event_no_list, event_counter)
                retros   = Extract_Retro(frame)
                if len(retros)>0:
                    retro   = Apply_Event_No(retros, event_no_list, event_counter)

                for pulse_map_key in pulse_map_keys:
                    is_empty = IsEmpty(pulse_maps[pulse_map_key]) 
                    if is_empty == False:
                        pulse_maps[pulse_map_key] = Apply_Event_No(pulse_maps[pulse_map_key], event_no_list, event_counter)
                event_counter += 1
                if len(feature_big) == 0:
                    feature_big = pulse_maps
                else:
                    for pulse_map_key in pulse_map_keys:
                        feature_big[pulse_map_key] = feature_big[pulse_map_key].append(pulse_maps[pulse_map_key],ignore_index = True, sort = True)
                truth_big   = truth_big.append(truth, ignore_index = True, sort = True)
                
                if len(retros)>0 :
                    retro_big   = retro_big.append(retro, ignore_index = True, sort = True)
                if len(truth_big) >= max_dict_size:
                    print('saving')
                    engine = sqlalchemy.create_engine('sqlite:///'+outdir + '/%s/tmp/worker-%s-%s.db'%(db_name,id,output_count))
                    truth_big.to_sql('truth',engine,index= False, if_exists = 'append')
                    if len(retro_big)> 0:
                        retro_big.to_sql('RetroReco',engine,index= False, if_exists = 'append')
                    for pulse_map_key in pulse_map_keys:
                        feature_big[pulse_map_key].to_sql(pulse_map_key,engine,index= False, if_exists = 'append')
                    engine.dispose()
                    feature_big = {} #pd.DataFrame()
                    truth_big   = pd.DataFrame()
                    retro_big   = pd.DataFrame()
                    output_count +=1
        file_counter +=1
        if verbose > 0:
            print('Worker %s has finished %s/%s I3 files.'%(id, file_counter, len(input_files)))
            sys.stdout.flush()
    if (len(feature_big) > 0):
        print('saving eof')
        engine = sqlalchemy.create_engine('sqlite:///'+outdir +  '/%s/tmp/worker-%s-%s.db'%(db_name,id,output_count))
        truth_big.to_sql('truth',engine,index= False, if_exists = 'append')
        if len(retro_big)> 0:
            retro_big.to_sql('RetroReco',engine,index= False, if_exists = 'append')
        for pulse_map_key in pulse_map_keys:
            feature_big[pulse_map_key].to_sql(pulse_map_key,engine,index= False, if_exists = 'append')
        engine.dispose()
        feature_big = {} 
        truth_big   = pd.DataFrame()
        retro_big   = pd.DataFrame()
    

def IsI3(file):
    if 'gcd' in file.lower():
        return False
    elif 'geo' in file.lower():
        return False
    else:
        return True
def HasExtension(file, extensions):
    check = 0
    for extension in extensions:
        if extension in file:
            check +=1
    if check >0:
        return True
    else:
        return False

def WalkDirectory(dir, extensions, gcd_rescue):
    files_list = []
    GCD_list   = []
    root,folders,root_files = next(os.walk(dir))
    gcds_root = []
    gcd_root = None
    i3files_root = []
    for file in root_files:
        if HasExtension(file, extensions):
            if IsI3(file):
                i3files_root.append(os.path.join(root,file))
            else:
                gcd_root = os.path.join(root,file)
                gcds_root.append(os.path.join(root,file))
    if gcd_root == None:
        gcd_root = gcd_rescue
    for k in range(len(i3files_root) - len(gcds_root)):
        gcds_root.append(gcd_root)
    files_list.extend(i3files_root)
    GCD_list.extend(gcds_root)
    for folder in folders:
        sub_root, sub_folders, sub_folder_files = next(os.walk(os.path.join(root,folder)))
        gcds_folder = []
        gcd_folder = None
        i3files_folder = []
        for sub_folder_file in sub_folder_files:
            if HasExtension(sub_folder_file, extensions):
                if IsI3(sub_folder_file):
                    i3files_folder.append(os.path.join(sub_root,sub_folder_file))
                else:
                    gcd_folder = os.path.join(sub_root,sub_folder_file)
                    gcds_folder.append(os.path.join(sub_root,sub_folder_file))
        if gcd_folder == None:
            gcd_folder = gcd_rescue
        for k in range(len(i3files_folder) - len(gcds_folder)):
            gcds_folder.append(gcd_folder)
        files_list.extend(i3files_folder)
        GCD_list.extend(gcds_folder)
    
    files_list, GCD_list = PairWiseShuffle(files_list, GCD_list)
    return files_list, GCD_list

def PairWiseShuffle(files_list, gcd_list):
    df = pd.DataFrame({'i3': files_list, 'gcd': gcd_list})
    df_shuffled = df.sample(frac = 1)
    i3_shuffled = df_shuffled['i3'].tolist()
    gcd_shuffled = df_shuffled['gcd'].tolist()
    return i3_shuffled, gcd_shuffled


def FindFiles(paths,outdir,db_name,gcd_rescue, extensions = None):
    print('Counting files in: \n%s\n This might take a few minutes...'%paths)
    if extensions == None:
        extensions = ("i3.bz2",".zst",".gz")
    input_files_mid = []
    input_files = []
    files = []
    gcd_files_mid = []
    gcd_files = []
    for path in paths:
        input_files_mid, gcd_files_mid = WalkDirectory(path, extensions, gcd_rescue)
        input_files.extend(input_files_mid)
        gcd_files.extend(gcd_files_mid)

    if len(input_files) > 0:
        input_files, gcd_files = PairWiseShuffle(input_files, gcd_files)
        Save_Filenames(input_files, outdir, db_name)
    return input_files, gcd_files
    
def Save_Filenames(input_files,outdir, db_name):
    input_files = pd.DataFrame(input_files)
    input_files.columns = ['filename']
    input_files.to_csv(outdir + '/%s/config/i3files.csv'%db_name)
    return

def CreateOutDirectory(outdir):
    try:
        os.makedirs(outdir)
        return False
    except:
        print(' !!WARNING!! \n \
            %s already exists. \n \
            ABORTING! '%outdir)
        return True

def PickleCleaner(List):
    clean_list = []
    for element in List:
        clean_list.append(str(element))
    return clean_list

def Extract_Config(config_path):
    with open('%s/config.pkl'%config_path, 'rb') as handle:
        config = pickle.load(handle)  
    paths = PickleCleaner(config['paths'])
    
    outdir = str(config['outdir'])
    workers = int(config['workers'])

    pulse_keys = PickleCleaner(config['pulse_keys'])
   
    db_name = str(config['db_name'])
    gcd_rescue = str(config['gcd_rescue'])
    verbose = int(config['verbose'])
    try:
        max_dictionary_size = int(config['max_dictionary_size'])
    except:
        max_dictionary_size = 10000
    try:
        custom_truth    =   PickleCleaner(config['custom_truth'])
        
    except:
        custom_truth    = None
    return paths, outdir, workers, pulse_keys, db_name, max_dictionary_size, custom_truth, gcd_rescue, verbose
def Transmit_Start_Time(start_time,config_path):
    with open('%s/config.pkl'%config_path, 'rb') as handle:
        config = pickle.load(handle)
    config['start_time'] = start_time
    with open('%s/config.pkl'%config_path, 'wb') as handle:
        pickle.dump(config, handle, protocol=2)  
    return

def PrintMessage(workers, input_files):
    print('Found %s I3 files!'%len(input_files))
    print('----------------------')
    print('READING FILES IN %s PARALLEL SESSIONS'%workers)
    print('----------------------')
def CreateTemporaryDatabases(paths, outdir, workers, pulse_keys,config_path, start_time,db_name,gcd_rescue,verbose,max_dictionary_size = 10000, custom_truth = None):
    if __name__ == "__main__" :
        start_time = time.time()
        if verbose == 0:
            icetray.I3Logger.global_logger = icetray.I3NullLogger()    
        directory_exists = CreateOutDirectory(outdir + '/%s/tmp'%db_name)
        input_files, gcd_files = FindFiles(paths, outdir,db_name,gcd_rescue)
        
        if len(input_files) > 0:
            if workers > len(input_files):
                workers = len(input_files)
            
            # SETTINGS
            settings = []
            event_nos = np.array_split(np.arange(0,99999999,1),workers) #Notice that this choice means event_no is NOT unique between different databases.
            file_list = np.array_split(np.array(input_files),workers)
            gcd_file_list = np.array_split(np.array(gcd_files),workers)

            for i in range(0,workers):
                settings.append([file_list[i],str(i),gcd_file_list[i],outdir,max_dictionary_size,event_nos[i], pulse_keys, custom_truth, db_name, verbose])
            #WriteDicts(settings[0])
            PrintMessage(workers, input_files)       
            p = Pool(processes = workers)
            p.map_async(WriteDicts, settings)
            p.close()
            p.join()
            print('transmitting..')
            Transmit_Start_Time(start_time, config_path)
        else:
            print('ERROR: No files found in: %s \n Please make sure your folder structure adheres to IceCube convention'%paths)


start_time = time.time()

paths, outdir, workers, pulse_keys, db_name, max_dictionary_size, custom_truth, gcd_rescue, verbose = Extract_Config(args.config)
print(args.config)
CreateTemporaryDatabases(paths, outdir, workers, pulse_keys,args.config, start_time,db_name,gcd_rescue,verbose, max_dictionary_size, custom_truth)




             






