from .userside import get_device_model, get_node_id, get_task_prefixes, \
    get_task_vlans, get_parent_switch_port
from .netbox import get_prefix, get_and_reserve_ip, get_vlan, get_prefix_info
from .snmp import get_vlan_list
from .kea import create_host_and_options
from .ztp import generate_initial_config
