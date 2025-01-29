import sys
import os
import yaml
import pprint
asset_data_path = "../asset_data"

#Couldn't figure out how to import yaml_io so I'm just manually reading the yamls

#replaces invalid characters in the yaml files with valid ones
def preprocess_yaml_content(content: str) -> str:
    # Replace tabs with 4 spaces
    content = content.replace('\t', '    ')
    # Handle improperly escaped single quotes in double-quoted scalars
    content = content.replace("\\'", "'")
    return content


def inventory_to_dict(inventory_repository_path:str = "../asset_data") -> dict:
    db = {}

    current_assets_dir = os.path.join(asset_data_path, "current_assets")
    if not os.path.exists(current_assets_dir):
        print(f'No current_assets directory found in asset_data')
        sys.exit(1)
    #put all the nodes in the db
    nodes = os.listdir(current_assets_dir)

    #get the node's data
    for filename in nodes:
        
        #only parse config files
        if filename.endswith(".yaml"):
            filepath = os.path.join(current_assets_dir, filename)

            #open, process, and parse nodefiles
            with open(filepath, 'r') as stream:
                content = stream.read()
                content = preprocess_yaml_content(content)
                try:
                    data = yaml.safe_load(content)
                    hostname = os.path.basename(os.path.realpath(filepath)).removesuffix('.yaml')
                    db[hostname] = {}
                    db[hostname]["hostname"] = hostname #To comply with common data format
                    db[hostname]["chassis"] = data['hardware']['model']
                    db[hostname]["location"] = f"{data['location']['building']} {data['location']['room']}"

                    #db[hostname] = data #Debug line to show raw data
                except yaml.YAMLError as e:
                    print(f"Error parsing YAML file {filepath}: {e}")


    return db

#call the functions if this script is run directly
if __name__ == "__main__":
    if len(sys.argv) != 1:
        print('Usage: python3 inventory_data.py')
        print('This script loads the json files in the inventory_data repository into a dictionary')
        sys.exit(1)
    db = inventory_to_dict()
    pprint.pprint(db) #print the first 5 keys in the dictionary
    
