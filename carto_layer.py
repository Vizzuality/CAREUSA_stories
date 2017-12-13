import contentful
from iso3166 import countries
from collections import Counter
import iso3166
import pandas as pd


def extract_entry(entry):
    """Given a single entry object (of story type), return a list"""
    iso = entry.country_list[0]
    sector_list = entry.sector_list
    sector_count = len(entry.sector_list)
    name = iso3166.countries_by_alpha3[iso].name
    return [iso, name, sector_list, sector_count]


def flatten_list(array_list):
    """
       Takes array of lists ([.,.,.],[.,.,.],...) and returns
        a flattened array [...]
    """
    tmp_flattened_list = []
    for item in array_list:
        for i in item:
            tmp_flattened_list.append(i)
    return tmp_flattened_list


def gen_row_of_table(iso, sector_count, all_sectors):
    """Given an iso, and a counted dictionary of stories for a given is,
        return a row for generating a final output table for Carto,
        and the name of the column also.
    """
    col_names = ['iso', 'name']
    iso = iso
    name = name = iso3166.countries_by_alpha3[iso].name
    #print(iso, name, '\n')
    data_row = [iso, name]
    for sector in sorted(all_sectors):
        #print(sector)
        col_name = sector.replace(" ", "_").lower()
        col_names.append(col_name)
        data_row.append(sector_count.get(sector, 0))
    col_names.append('total')
    data_row.append(sum(sector_count.values()))
    return data_row, col_names


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

    assert ACCESS_TOKEN, 'failed to find ACCESS_TOKEN'
    assert SPACE_ID, 'failed to find SPACE_ID'

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
    df = pd.DataFrame(tmp_array, columns=['iso','name','sector_list',
                                          'sector_count'])
    # Iterate through the list of sectors, flatten it, then find the unique set
    all_sectors = []
    for sublist in df.sector_list:
        for item in sublist:
            all_sectors.append(item)
    unique_sectors = set(all_sectors)
    # Extract a set of the unique iso codes
    unique_isos = sorted(df.iso.unique())
    tmp_array = []
    for iso in unique_isos:
        print("Extracting ", iso, end="")
        tmp_df = df[df.iso == iso]
        print(" found ", len(tmp_df)," stories. ", end="")
        tmp_sector_list = flatten_list(tmp_df.sector_list.values)
        sector_count = Counter(tmp_sector_list)
        print(sector_count)
        tmp_row, col_names = gen_row_of_table(iso, sector_count, unique_sectors)
        tmp_array.append(tmp_row)
    export_df = pd.DataFrame(tmp_array, columns=col_names)
    export_df.to_csv('output_stories.csv')
    print('Normal end of program reached.')


if __name__ == '__main__':
    main()
