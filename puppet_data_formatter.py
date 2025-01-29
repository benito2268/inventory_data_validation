# https://opensciencegrid.atlassian.net/browse/INF-2154
# hostname from file
# BMC configuration or lackthereof
# including IP address
# interfaces
# ipv4/6 addrs and MAC addresses per interface, as well as type of interface
# hostname set in networking files
#   Then we can use that data structure for fun internal parity checks:
# No duplicate IP4 addresses between BMCs
# No duplicate IPv4/6 addresses between primary NICs
# Primary NICs should have mac addresses, unless they are infiniband
# Lack of IPV6 configuration
# If assigned IPv6 address is not proper EUI64 for the mac address set
# and so on. Virtual devices (which can be determined via symlink) should not have BMCs.
import os
import yaml
import sys
import pprint
from typing import Tuple
#convert the file names to the actual property name
YAML_TO_PROPERTIES = {
    "centos_7.yaml": "centos_7",
    "centos_8_stream.yaml": "centos_8",
    "centos_9_stream.yaml": "centos_9",
    "centos.yaml" : "centos - This is the base yaml, this shouldn\'t happen",
}

def preprocess_yaml_content(content: str) -> str:
    # Replace tabs with 4 spaces
    content = content.replace('\t', '    ')
    # Handle improperly escaped single quotes in double-quoted scalars
    content = content.replace("\\'", "'")
    return content

from typing import List

#this function takes the dict of a nodefile and extracts the hostname, network hostname, bmc address, and interfaces
#interfaces are returned in a dict with key = interface name (e.g. eth0) and value = dict of HWADDR, IPADDR, IPV6ADDR
def find_nodefile_info(data: dict, os_version: str) -> Tuple[str, str, str, dict]: #this function is super ugly, maybe refactor
    hostname = None
    network_hostname = None
    bmc_address = None
    interfaces = {}

    if os_version == 'centos_7':
        # print("CentOS 7 data['network']")
        # pprint.pprint(data["network"])

        return hostname, network_hostname, bmc_address, interfaces
    elif os_version == 'centos_8' or os_version == 'centos_9':
        # print("CentOS 8/9 data")
        # if 'file' in data:
        #     pprint.pprint({k:v for (k,v) in data["file"].items() if '/etc/sysconfig/network-scripts' in k})

        if 'bmc' in data and 'lan' in data['bmc'] and 'ip_address' in data['bmc']['lan']:
            bmc_address = data['bmc']['lan']['ip_address']
        
        if 'file' in data:
            if '/etc/hostname' in data['file'] and 'content' in data['file']['/etc/hostname']:
                hostname_content = data['file']['/etc/hostname']['content']
                for key, value in hostname_content.items():
                    if isinstance(value, dict):
                        for host, flag in value.items():
                            if flag:  # Check if it's set to True
                                hostname = host
            if '/etc/sysconfig/network' in data['file'] and 'content' in data['file']['/etc/sysconfig/network']:
                network_content = data['file']['/etc/sysconfig/network']['content']
                for key, value in network_content.items():
                    if isinstance(value, dict):
                        for network_config, flag in value.items():
                            if flag and network_config.startswith("HOSTNAME="):
                                network_hostname = network_config.split('=')[1]

            # Loop through all the interfaces in /etc/sysconfig/network-scripts/
            for file_key, file_value in data['file'].items():
                if file_key.startswith('/etc/sysconfig/network-scripts/ifcfg-') and 'content' in file_value:
                    interfacename = file_key.removeprefix('/etc/sysconfig/network-scripts/ifcfg-')  # Get interface name, removeprefix() behavior is kinda weird but this should work

                    interface_info = {
                        'interface': file_key.split('/')[-1], #keeping this for parity checks
                        'HWADDR': None,
                        'IPADDR': None,
                        'IPV6ADDR': None
                    }
                    eth_content = file_value['content']
                    for key, value in eth_content.items():
                        if isinstance(value, dict):
                            for network_config, flag in value.items():
                                if flag and network_config.startswith("HWADDR="):
                                    interface_info['HWADDR'] = network_config.split('=')[1]
                                if flag and network_config.startswith("IPADDR="):
                                    interface_info['IPADDR'] = network_config.split('=')[1]
                                if flag and network_config.startswith("IPV6ADDR="):
                                    interface_info['IPV6ADDR'] = network_config.split('=')[1]
                    interfaces[interfacename] = interface_info
        return hostname, network_hostname, bmc_address, interfaces
    else:
        print(f"Unknown OS version {os_version}")
        return None, None, None, None

#this gets the chassis for the node and if it is a vm 
def get_node_chassis_and_vm(node_chassis_path:str) -> Tuple[str, bool]:
    templatename = os.path.basename(os.path.realpath(node_chassis_path))
    #not using YAML_TO_PROPERTIES b/c the chassis yaml names should hopefully match (this may change)
    return (os.path.splitext(templatename)[0], templatename == 'kvm_guest.yaml')

#given the path to a node in os_tier_1, return the centos version of the node
def get_node_os(node_os_path:str) -> str:
    templatename = os.path.basename(os.path.realpath(node_os_path)) #extract the file name

    if templatename not in YAML_TO_PROPERTIES:
        print(f'Unknown OS template name {templatename} for node {node_os_path}') #don't know why this ever gets printed out
        return None
    return YAML_TO_PROPERTIES[templatename]

def get_node_location(puppet_data_path: str) -> dict:
    ret = {}
    site_path = puppet_data_path + "/site_tier_0"
    pretty_names = {
        '3370a'   : ('CS3370a', "Computer Sciences"),
        '2360'    : ('CS2360', 'Computer Sciences'),
        'b240'    : ('CSB240', "Computer Sciences"),
        'oneneck' : ('OneNeck', "OneNeck"),
        'wid'     : ('WID', 'WID'),
        'fiu'     : ('FIU', 'FIU'),
        'syra'    : ('Syracuse', 'Syracuse'),
        'syrb'    : ('CS2360', 'Computer Sciences'),
        'wisc'    : ('CS2360', 'Computer Sciences'),
        'unl'     : ('UNL', 'UNL'),
    }

    for ent in os.listdir(site_path):
        for k, v in pretty_names.items():
            if k in os.readlink(site_path + '/' +  ent):
                ret.update({ent.removesuffix(".yaml") : f"{v[1]} {v[0]}"})

    return ret

def load_yaml_files(puppet_data_path: str) -> dict:
    nodes_data = {}
    sites_data = get_node_location(puppet_data_path)
    for filename in os.listdir(os.path.join(puppet_data_path, 'node')):
        
        #only parse config files
        if filename.endswith(".yaml"):
            filepath = os.path.join(puppet_data_path, 'node', filename)

            #open, process, and parse nodefiles
            with open(filepath, 'r') as stream:
                content = stream.read()
                content = preprocess_yaml_content(content)
                try:
                    hostname = os.path.basename(os.path.realpath(filepath)).removesuffix('.yaml') #we need the fqdn for hostname
                    
                    data = yaml.safe_load(content)

                    nodes_data[hostname] = {}

                    nodes_data[hostname]['chassis'], nodes_data[hostname]['isVM'] = get_node_chassis_and_vm(os.path.join(puppet_data_path, 'chassis', filename)) #this should be in the outside loop, but sometimes the entry for the host is not created
                    nodes_data[hostname]['os_version'] = get_node_os(os.path.join(puppet_data_path, 'os_tier_1', filename))

                    name, network_hostname, bmc_address, interfaces = find_nodefile_info(data, nodes_data[hostname]['os_version'])
                    if (name is not None and not (name == hostname.split('.')[0] or name == hostname)): # make sure name isn't none, and that name isn't just the hostname or the fqdn
                        print(f"Hostname mismatch: {name} != {hostname}")
                    
                    nodes_data[hostname]['hostname'] = hostname
                    nodes_data[hostname]['network_hostname'] = network_hostname
                    nodes_data[hostname]['bmc_address'] = bmc_address
                    nodes_data[hostname]['interfaces'] = interfaces #keep for parity checks
             
                    if hostname in sites_data.keys():
                        nodes_data[hostname]['location'] = sites_data[hostname]
                    else:
                        nodes_data[hostname]['location'] = ""

                    # Add interfaces to the node data
                    # Only add the most relevant interface
                    nodes_data[hostname]["mac_address"] = ""
                    nodes_data[hostname]["ipv4_address"] = ""
                    # nodes_data[hostname]["netmask"] = ""
                    # nodes_data[hostname]["gateway"] = ""
                    nodes_data[hostname]["ipv6_address"] = ""
                    if interfaces is not None and len(interfaces) > 0: #only do this if we actually have an interface to look at
                        for ifkey in list(interfaces.keys()) + ["em1", "eth0", "ib0"]: #make sure we do some specific interfaces last TODO: get help on which interface provides the "real" address
                            if ifkey not in interfaces:
                                continue

                            for nodedictkey, ifdictkey in [('mac_address', 'HWADDR'), ('ipv4_address', 'IPADDR'), ('ipv6_address', 'IPV6ADDR')]:
                                if interfaces[ifkey][ifdictkey] is not None and interfaces[ifkey][ifdictkey] != "":

                                    nodes_data[hostname][nodedictkey] = interfaces[ifkey][ifdictkey]
                            # nodes_data[hostname]["mac_address"] = if interfaces[ifkey]['HWADDR'] is None else interfaces[ifkey]['HWADDR'].upper()
                            # nodes_data[hostname]["ipv4_address"] = interfaces[ifkey]['IPADDR']
                            # # nodes_data[hostname]["netmask"] = interfaces[ifkey]['netmask']
                            # # nodes_data[hostname]["gateway"] = interfaces[ifkey]['if_gateway']
                            # nodes_data[hostname]["ipv6_address"] = interfaces[ifkey]['IPV6ADDR']

                except yaml.YAMLError as e:
                    print(f"Error parsing YAML file {filepath}: {e}")
    return nodes_data


def perform_parity_checks(nodes_data):
    ipv4_addresses = set()
    ipv6_addresses = set()
    bmc_addresses = set()
    failed_checks = []
    for node, info in nodes_data.items():
        # Check for duplicate BMC addresses
        # print("====================================")
        # print(node)
        # print(info)
        
        if (info is None or len(info) == 0):
            print(f"Node {node} has no data.")
            continue

        if info['bmc_address']:
            if info['bmc_address'] in bmc_addresses:
                failed_checks.append(f"Duplicate BMC address detected: {info['bmc_address']} in node {node}")
            else:
                bmc_addresses.add(info['bmc_address'])
        if (info['interfaces'] is None or len(info['interfaces']) == 0):
            continue
        for interface in info['interfaces'].values():
            # Check for duplicate IPv4/IPv6 addresses
            if interface['IPADDR']:
                if interface['IPADDR'] in ipv4_addresses:
                    failed_checks.append(f"Duplicate IPv4 address detected: {interface['IPADDR']} in node {node}")
                else:
                    ipv4_addresses.add(interface['IPADDR'])
            
            if interface['IPV6ADDR']:
                if interface['IPV6ADDR'] in ipv6_addresses:
                    failed_checks.append(f"Duplicate IPv6 address detected: {interface['IPV6ADDR']} in node {node}")
                else:
                    ipv6_addresses.add(interface['IPV6ADDR'])
            
            # TODO: Check if primary NICs have HWADDR unless they are virtual devices
            if interface['interface'].startswith("ifcfg-eth") and not interface['HWADDR']:
                failed_checks.append(f"Primary NIC {interface['interface']} in node {node} has no HWADDR.")
            
            # Check for missing IPV6 configuration
            if not interface['IPV6ADDR']:
                failed_checks.append(f"Interface {interface['interface']} in node {node} is missing an IPV6 address.")

    return failed_checks

def puppet_to_dict(puppet_data_path:str = "../puppet_data") -> dict:
    return load_yaml_files(puppet_data_path)



if __name__ == "__main__":
    puppet_data_path = '../puppet_data' #TODO: change this back to '../puppet_data' when done testing
    #run this if called through command line
    if len(sys.argv) == 1:
        pass
    elif len(sys.argv) == 2:
        if sys.argv[1] == '-h' or sys.argv[1] == '--help':
            print('Usage: python3 puppet_data.py [path_to_puppet_data]')
            print('This script loads the json files in the puppet_data repository into a dictionary')
            sys.exit(0)
        else:
            puppet_data_path = sys.argv[1]
    # Running this file with no args will run the parity checks
    nodes_data = load_yaml_files(puppet_data_path)
    parity_check_results = perform_parity_checks(nodes_data)
    if parity_check_results:
        print("Parity Check Failures:")
        for failure in parity_check_results:
            print(failure)
    else:
        print("All parity checks passed.")

    #pprint.pprint(nodes_data) #print everything
