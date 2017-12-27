import contentful
from iso3166 import countries
from collections import Counter
import iso3166
import pandas as pd
import requests
import os
import time
from pprint import pprint

output_file = 'output_stories.csv'


def extract_entry(entry):
    """Given a single entry object (of story type), return a list"""
    try:
        identifier = entry.id
    except:
        identifier = None
    try:
        iso = entry.country_list[0]
        name = iso3166.countries_by_alpha3[iso].name
    except:
        iso = None
        name = None
    try:
        sector_list = entry.sector_list
        sector_count = len(entry.sector_list)
    except:
        sector_list = None
        sector_count = None
    try:
        dt = entry.story_date
        date = str(dt.date())
        year = dt.year
    except:
        date = None
        year = None
    return [identifier, iso, name, sector_list, sector_count, date, year]


def sector_row_entries(sector_entry, all_sectors):
    """Given an entry and a list of sectors
        return a row for generating a final output table for Carto,
        and the name of the column also.
    """
    #print(sector_entry)
    tmp = []
    col_names = []
    for sector in sorted(all_sectors):
        col_name = sector.replace(" ", "_").lower()
        if col_name == 'emergency_&_disaster_aid':
            col_name = 'emergency__disaster_aid'
        #print(sector, col_name)
        col_names.append(col_name)
        found = 0
        for tag in sector_entry:
            if tag == sector:
                #print(f'     found {tag} entry')
                found = 1
                tmp.append(True)
        if found == 0:
            tmp.append(False)
    return tmp, col_names


# Carto management functions

def drop_existing_carto_table(APIKEY, target_table='output_stories'):
    print(f'Attempting to erase {target_table}')
    url = 'https://careusa.carto.com/api/v2/sql'
    params = {'q':f"DROP TABLE {target_table}",
              'api_key': APIKEY,}
    r = requests.get(url=url, params=params)
    #print(r.url)
    if r.status_code == 200:
        print(f'Sucsessfully droped the existing carto table {target_table}')
        return None
    else:
        print(f"Unable to drop {target_table} table. Status: {r.status_code}")
        return "DROP TABLE failed"


def upload_to_carto(APIKEY):
    """Use the Carto API to upload a local csv file to the careusa account"""
    url = "https://careusa.carto.com/api/v1/imports"
    params = {'api_key': APIKEY,
              'privacy':'public',
              'collision_strategy':'overwrite'}
    files = {'file': open(output_file,'rb')}
    r = requests.post(url=url,files=files, params=params)

    if r.status_code == 200:
        print(f"Carto respose {r.status_code}: Table upload successful")
        pprint(r.json())
        return r.json().get('item_queue_id')
    else:
        print(f"Table upload failed - Carto response {r.status_code}")


def upload_report(queue_id, APIKEY):
    """Uses the carto queue id to report on status of file upload"""
    if queue_id:
        params = {'api_key': APIKEY}
        print('Report on status of uploaded file ingestion:')
        url = f"https://careusa.carto.com/api/v1/imports/{queue_id}"
        r2 = requests.get(url=url, params=params)
        print(r2.status_code)
        pprint(r2.json())
        return None
    else:
        return None


def main():
    env_file = []
    try:
        with open('.env') as env:
            for line in env:
                env_file.append(line)
    except:
        print('Failed to find .env file - see README')
        return
    ACCESS_TOKEN = None
    SPACE_ID = None
    for item in env_file:
        if item.split()[0] == 'ACCESS_TOKEN':
            ACCESS_TOKEN = item.split()[-1]
        if item.split()[0] == 'SPACE_ID':
            SPACE_ID = item.split()[-1]
        if item.split()[0] == 'CARTO_API_KEY':
            CARTO_API_KEY = item.split()[-1]

    assert ACCESS_TOKEN, 'failed to find ACCESS_TOKEN'
    assert SPACE_ID, 'failed to find SPACE_ID'
    assert CARTO_API_KEY, 'failed to find CARTO_API_KEY'

    # Create your Contentful Delivery API Client
    client = contentful.Client(SPACE_ID, ACCESS_TOKEN)
    # Gather the stories
    stories = client.entries({'content_type': 'story'})
    print("Found ", len(stories), "stories. \n")
    assert len(stories) > 0, "Didn't find any stories."
    tmp_array = []
    for entry in stories:
        #print(entry)
        tmp_array.append(extract_entry(entry))
    # each row in the below df is a single story
    df = pd.DataFrame(tmp_array, columns=['id','iso','country','sector_list',
                                          'sector_count','date','year'])
    # Iterate through the list of sectors, flatten it, then find the unique set
    all_sectors = []
    for sublist in df.sector_list:
        for item in sublist:
            all_sectors.append(item)
    unique_sectors = set(all_sectors)

    # Generate a table with one row per story, but seperated tags
    tmp_row = []
    for index in df.index:
        #print(index, df['sector_list'][index], unique_sectors)
        sector_entries = []
        sector_entries, sector_names = sector_row_entries(sector_entry = df['sector_list'][index],
                                                          all_sectors=unique_sectors)
        sector_entries.append(df['id'][index])
        sector_entries.append(df['iso'][index])
        sector_entries.append(df['country'][index])
        sector_entries.append(df['date'][index])
        sector_entries.append(df['year'][index])
        tmp_row.append(sector_entries)

    sector_names.append('id')
    sector_names.append('iso')
    sector_names.append('country')
    sector_names.append('date')
    sector_names.append('year')

    export_df = pd.DataFrame(tmp_row, columns=sector_names)
    export_df.to_csv(output_file, index=False)
    print('Created temporary file. Starting Carto update process.')
    report = drop_existing_carto_table(APIKEY=CARTO_API_KEY) # First, remove the existing table
    if report:
        print('Table drop failed. Will try and continue with the run, but there may be a problem.')
    print('Please wait...')
    time.sleep(10)            # wait a few seconds
    print('Uploading new table.')
    queue_id = upload_to_carto(APIKEY=CARTO_API_KEY)
    print('Waiting several seconds for file to process, then I will retrieve a report on the status:\n')
    time.sleep(10)
    upload_report(queue_id, APIKEY=CARTO_API_KEY)
    if os.path.exists(output_file):
        print(f'Cleanup - removed temporary {output_file} file.')
        os.remove(output_file)

if __name__ == '__main__':
    main()
