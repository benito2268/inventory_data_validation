#This main function gets the dictionaries from the 3 sources and compares them

import cobbler_data_formatter
import puppet_data_formatter
import inventory_data_formatter

try:
    import tabulate
except ImportError:
    print("Please install tabulate with 'pip install tabulate'")
    exit(1)

def main():
    cobbler_db = cobbler_data_formatter.cobbler_to_dict()
    puppet_db = puppet_data_formatter.puppet_to_dict()
    inventory_db = inventory_data_formatter.inventory_to_dict()

    cobbler_hosts = set(cobbler_db.keys())
    puppet_hosts = set(puppet_db.keys())
    inventory_hosts = set(inventory_db.keys())

    print(f"Total tracked hosts: {len(cobbler_hosts or puppet_hosts or inventory_hosts)}")
    print(f"Total hosts tracked in all 3 sources: {len(cobbler_hosts and puppet_hosts and inventory_hosts)}")

    print(f"Num hosts in cobbler but not puppet or inventory: {len(cobbler_hosts - puppet_hosts - inventory_hosts)}")
    print(f"Num hosts in puppet but not cobbler or inventory: {len(puppet_hosts - cobbler_hosts - inventory_hosts)}")
    print(f"Num hosts in inventory but not cobbler or puppet: {len(inventory_hosts - cobbler_hosts - puppet_hosts)}")

    puppet_cobbler_ipv4_mismatch = []
    print("Puppet and Cobbler IPv4 Mismatch:")
    for host in puppet_hosts & cobbler_hosts:
        if puppet_db[host]['ipv4_address'].lower() != cobbler_db[host]['ipv4_address'].lower():
            puppet_cobbler_ipv4_mismatch.append([host, puppet_db[host]['ipv4_address'], cobbler_db[host]['ipv4_address']])
            #print(f"{host}: puppet {puppet_db[host]['ipv4_address']} cobbler {cobbler_db[host]['ipv4_address']}")
    print(tabulate.tabulate(puppet_cobbler_ipv4_mismatch, headers=["Host", "Puppet IPv4", "Cobbler IPv4"]))

    puppet_cobbler_mac_mismatch = []
    print("Puppet and Cobbler MAC Mismatch:")
    for host in puppet_hosts & cobbler_hosts:
        if puppet_db[host]['mac_address'].lower() != cobbler_db[host]['mac_address'].lower():
            puppet_cobbler_mac_mismatch.append([host, puppet_db[host]['mac_address'], cobbler_db[host]['mac_address']])
            #print(f"{host}: puppet {puppet_db[host]['mac_address']} cobbler {cobbler_db[host]['mac_address']}")
    print(tabulate.tabulate(puppet_cobbler_mac_mismatch, headers=["Host", "Puppet MAC", "Cobbler MAC"]))

    print("Puppet and Cobbler OS Mismatch:")
    puppet_cobbler_os_mismatch = []
    for host in puppet_hosts & cobbler_hosts:
        if puppet_db[host]['os_version'] != cobbler_db[host]['os_version']:
            puppet_cobbler_os_mismatch.append([host, puppet_db[host]['os_version'], cobbler_db[host]['os_version']])
            #print(f"{host}\t{puppet_db[host]['os_version']}\t{cobbler_db[host]['os_version']}")
    print(tabulate.tabulate(puppet_cobbler_os_mismatch, headers=["Host", "Puppet Version", "Cobbler Version"]))

    #print(f"Hosts existing only in Cobbler:{sorted(cobbler_hosts - puppet_hosts - inventory_hosts)}") #example
    #print(f"Hosts existing only in Puppet:{sorted(puppet_hosts - cobbler_hosts - inventory_hosts)}")

    # find site mismatch
    # puppet doesn't store rack or elevation but we can check building/room
    print()
    print("Puppet and Inventory Site Mismatch")
    puppet_inventory_site_mismatch = []
    for host in puppet_hosts & inventory_hosts:
        inventory_site = inventory_db[host]["location"]
        puppet_site = puppet_db[host]["location"]

        if inventory_site != puppet_site:
            puppet_inventory_site_mismatch.append([host, inventory_site, puppet_site])
    print(tabulate.tabulate(puppet_inventory_site_mismatch, headers=["Host", "Inventory Site", "Puppet Site"]))

    print()
    print("Mismatch summary:")
    print(f"IPv4 Mismatch: {len(puppet_cobbler_ipv4_mismatch)} / {len(puppet_hosts & cobbler_hosts)}")
    print(f"MAC Mismatch: {len(puppet_cobbler_mac_mismatch)} / {len(puppet_hosts & cobbler_hosts)}")
    print(f"OS Mismatch: {len(puppet_cobbler_os_mismatch)} / {len(puppet_hosts & cobbler_hosts)}")
    print(f"Site Mismatch: {len(puppet_inventory_site_mismatch)} / {len(puppet_hosts & inventory_hosts)}")

main()
