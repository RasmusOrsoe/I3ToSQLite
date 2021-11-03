import os
from sqlalchemy import create_engine
import sqlalchemy
import pandas as pd
import sqlite3
import time
import pickle
from tqdm import tqdm
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-config", "--config", type=str, required=True)
args = parser.parse_args()


def fetch_temps(path):
    out = []
    files = os.listdir(path)
    for file in files:
        if '.db' in file:
            out.append(file)
    return out

def Extract_Everything(db, keys):
    pulse_maps = {}
    with sqlite3.connect(db) as con:
        truth_query = 'select * from truth'
        truth = pd.read_sql(truth_query,con)
    for key in keys:
        with sqlite3.connect(db) as con:
            pulse_map_query = 'select * from %s'%key
            pulse_map = pd.read_sql(pulse_map_query,con)
        pulse_maps[key] = pulse_map
    try:
        with sqlite3.connect(db) as con:
            retro_query = 'select * from RetroReco'
            retro = pd.read_sql(retro_query,con)
    except:
        retro = []
    return truth, pulse_maps, retro

def Extract_Column_Names(tmp_path, db_files, keys):
    pulse_map_columns = {}
    db = tmp_path + '/' + db_files[0]
    with sqlite3.connect(db) as con:
        truth_query = 'select * from truth limit 1'
        truth_columns = pd.read_sql(truth_query,con).columns
    for key in keys:
        with sqlite3.connect(db) as con:
            pulse_map_query = 'select * from %s limit 1'%key
            pulse_map = pd.read_sql(pulse_map_query,con)
        pulse_map_columns[key] = pulse_map.columns
    
    for db_file in db_files:
        db = tmp_path + '/' + db_file
        try:
            with sqlite3.connect(db) as con:
                retro_query = 'select * from RetroReco limit 1'
                retro_columns = pd.read_sql(retro_query,con).columns
            if len(retro_columns)>0:
                break
        except:
            retro_columns = []
        


    return truth_columns, pulse_map_columns, retro_columns

def Run_SQL_Code(database, CODE):
    conn = sqlite3.connect(database + '.db')
    c = conn.cursor()
    c.executescript(CODE)
    c.close()  
    return

def Attach_Index(database, table_name):
    CODE = "PRAGMA foreign_keys=off;\nBEGIN TRANSACTION;\nCREATE INDEX event_no_{} ON {} (event_no);\nCOMMIT TRANSACTION;\nPRAGMA foreign_keys=on;".format(table_name,table_name)
    Run_SQL_Code(database,CODE)
    return

def CreateTable(database,table_name, columns, is_pulse_map = False):
    count = 0
    for column in columns:
        if count == 0:
            if column == 'event_no':
                if is_pulse_map == False:
                    query_columns =  column + ' INTEGER PRIMARY KEY NOT NULL'
                else:
                     query_columns =  column + ' NOT NULL'
            else: 
                query_columns =  column + ' FLOAT'
        else:
            if column == "event_no":
                if is_pulse_map == False:
                    query_columns =  query_columns + ', ' + column + ' INTEGER PRIMARY KEY NOT NULL'
                else:
                     query_columns = query_columns + ', '+ column + ' NOT NULL' 
            else:
                query_columns = query_columns + ', ' + column + ' FLOAT'

        count +=1
    CODE = "PRAGMA foreign_keys=off;\nCREATE TABLE {} ({});\nPRAGMA foreign_keys=on;".format(table_name,query_columns) 
    Run_SQL_Code(database, CODE)
    if is_pulse_map:
        #try:
        print(table_name)
        print('attaching indexs')
        Attach_Index(database,table_name)
        #except:
        #    notimportant = 0
    return

def Create_Empty_Tables(database,pulse_map_keys,truth_columns, pulse_map_columns, retro_columns):
    
    print('Creating Empty Truth Table')
    CreateTable(database, 'truth', truth_columns, is_pulse_map = False) # Creates the truth table containing primary particle attributes and RetroReco reconstructions
    print('Creating Empty RetroReco Table')
    if len(retro_columns) > 1:
        CreateTable(database, 'RetroReco',retro_columns, is_pulse_map = False) # Creates the RetroReco Table with reconstuctions and associated values.
    for pulse_map_key in pulse_map_keys:
        # Creates the pulse map tables
        print('Creating Empty %s Table'%pulse_map_key)
        CreateTable(database, pulse_map_key,pulse_map_columns[pulse_map_key], is_pulse_map = True)
    return

def Submit_Truth(database, truth):
    engine_main = sqlalchemy.create_engine('sqlite:///' + database + '.db')
    truth.to_sql('truth',engine_main,index= False, if_exists = 'append')
    engine_main.dispose()
    return  

def Submit_Pulse_Maps(database, pulse_maps):
    engine_main = sqlalchemy.create_engine('sqlite:///' + database + '.db')
    for pulse_map in pulse_maps.keys():
        pulse_maps[pulse_map].to_sql(pulse_map, engine_main,index= False, if_exists = 'append')
    engine_main.dispose()
    return

def Submit_Retro(database, retro):
    if len(retro)>0:
        engine_main = sqlalchemy.create_engine('sqlite:///' + database + '.db')
        retro.to_sql('RetroReco',engine_main,index= False, if_exists = 'append')
        engine_main.dispose()
    return  

def Merge_Temporary_Databases(database, db_files, path_to_tmp,pulse_map_keys):
    file_counter = 1
    Print_Message()
    for i in tqdm(range(len(db_files)), colour = 'green'):
        file = db_files[i]
        truth, pulse_maps, retro = Extract_Everything(path_to_tmp + '/'  + file,pulse_map_keys)
        Submit_Truth(database,truth)
        Submit_Pulse_Maps(database, pulse_maps)
        Submit_Retro(database, retro)
        file_counter += 1
    return

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

    start_time = float(config['start_time'])
    try:
        max_dictionary_size = int(config['max_dictionary_size'])
    except:
        max_dictionary_size = 10000
    try:
        custom_truth    =   PickleCleaner(config['custom_truth'])
        
    except:
        custom_truth    = None
    
    return paths, outdir, workers, pulse_keys, db_name, max_dictionary_size, custom_truth, start_time

def CreateDirectory(dir):
    try:
        os.makedirs(dir)
        return False
    except:
        return True
def Print_Message():
    print('-----------------')
    print('MERGING DATABASES')
    print('-----------------')
def CreateDatabase(database_name,outdir, pulse_map_keys):
    path_tmp = outdir + '/' + database_name + '/tmp'
    database_path = outdir + '/' + database_name + '/' + database_name
    directory_exists = CreateDirectory(outdir)
    db_files = fetch_temps(path_tmp)
    print('Found %s .db-files in %s'%(len(db_files),path_tmp))
    truth_columns, pulse_map_columns, retro_columns = Extract_Column_Names(path_tmp, db_files, pulse_map_keys)
    Create_Empty_Tables(database_path,pulse_map_keys, truth_columns, pulse_map_columns, retro_columns)
    Merge_Temporary_Databases(database_path, db_files, path_tmp, pulse_map_keys)
    os.system('rm -r %s'%path_tmp)
    return


paths, outdir, workers, pulse_keys, db_name, max_dictionary_size, custom_truth, start_time = Extract_Config(args.config)
CreateDatabase(db_name, outdir, pulse_keys)

print('Database Creation Successful!')
print('Time Elapsed: %s minutes'%((time.time() - start_time)/60))

