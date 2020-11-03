"""Utility functions"""
import math
import re
from pymtl3 import *

def get_var_product(projection, var_array):
    """ Multiply a subset of projection factors

    :param projection: Projection definition (according to projection yaml schema) 
    :type projection: dict
    :param var_array: Names of factors to multiply - none by default
    :type var_array: array
    :return: Product 
    :rtype: int
    """
    product = 1
    for var in var_array:
        assert var in projection, "Key " + var + " not found in projection definition."
        product *= int(projection[var]['value'])
    return product

def get_mlb_count(projection):
    """ Calculate the number of ML Blocks required based on the projection definition 
    (``projections``)

    :param projection: Projection definition (according to projection yaml schema) 
    :type projection: dict
    :return: Number of blocks required
    :rtype: int
    """
    return get_var_product(projection, ['URN','URW','UB','UE','UG'])

def get_proj_chain_length(projection, dtype):
    """ Calculate cascade chain length

    :param projection: Projection definition (according to projection yaml schema) 
    :type projection: dict
    :param dtype: datatype considered - all by default 
    :type dtype: string
    :return: dtype
    :rtype: int
    """
    assert re.search(r"^[WIO]*$",dtype), "Unknown type " + dtype
    if ('W' == dtype):
        return get_var_product(projection, ['URW'])
    elif ('I' == dtype):
        return get_var_product(projection, ['URW'])
    elif ('O' in dtype):
        return get_var_product(projection, ['URW','URN'])
    return 0

def get_proj_stream_count(projection, dtype='WIO'):
    """ Calculate the number of input or output streams required in total.
    (The total width is this number * the total width of that datatype at the inner 
instance boundary)

    :param projection: Projection definition (according to projection yaml schema) 
    :type projection: dict
    :param dtype: datatype considered - all by default 
    :type dtype: string
    :return: dtype
    :rtype: int
    """
    assert re.search(r"^[WIO]*$",dtype), "Unknown type " + dtype
    sum = 0
    if ('W' in dtype):
        ws = get_var_product(projection, ['URW','URN','UE','UG'])
        if 'PRELOAD' in projection:
            for pload in projection["PRELOAD"]:
                if pload["dtype"] == 'W':
                    ws = pload["bus_count"]
        sum += ws
    if ('I' in dtype):
        wi = get_var_product(projection, ['URN','UB','UG'])
        if 'PRELOAD' in projection:
            for pload in projection["PRELOAD"]:
                if pload["dtype"] == 'I':
                    wi = pload["bus_count"]
        sum += wi
    if ('O' in dtype):
        wo= get_var_product(projection, ['UE','UB','UG'])
        if 'PRELOAD' in projection:
            for pload in projection["PRELOAD"]:
                if pload["dtype"] == 'O':
                    wo = pload["bus_count"]
        sum += wo
    return sum

def get_activation_function_name(projection):
    """ Lookup the name of the activation function in the projection yaml schema 
    (``projections``).

    :return: Activation function name
    :rtype: string
    """
    assert 'activation_function' in projection, \
        "Key activation_function not found in projection definition"
    return projection['activation_function']

def get_ports_of_type(hw_spec, type, dir=["in","out"]):
    """ Find and return all input ports of given type from the hardware specification 
    (``hw_spec``)

    :param hw_spec: Hardware definition (according to hardware yaml schema) 
    :type hw_spec: dict
    :param type: Type to match
    :type type: string
    :param dir: port directions to include - both by default
    :type dir: list
    :return: Ports with type ``type``
    :rtype: list
    """
    return filter(lambda port: (port['type'] == type) and (port["direction"] in dir),
                  hw_spec['ports'])

def get_sum_datatype_width(hw_spec, type, dir=['in', 'out']):
    """ Calculate the total sum of widths of ports of type ``type`` and with direction 
    ``dir``

    :param hw_spec: Hardware definition (according to hardware yaml schema) 
    :type hw_spec: dict
    :param type: Type to match
    :type type: string
    :param dir: port directions to include - both by default
    :type dir: list
    :return: Sum of port widths
    :rtype: int
    """
    return sum(map(lambda port: port['width'] if ((port['type'] == type) and
                                                  (port['direction'] in dir)) else 0,
               hw_spec['ports']))
    
def get_num_buffers_reqd(buffer_spec, stream_count, stream_width):
    """ Calculate the number of buffers required given IO requirements

    :param buffer_spec: Buffer hardware definition (according to hardware yaml schema) 
    :type buffer_spec: dict
    :param stream_count: Number of streams that need to connect to buffers. Each stream must
                         connect to a single buffer and isn't split between them. 
    :type stream_count: int
    :param stream_width: Bit-width of each stream
    :type stream_width: int
    :return: Number of buffers to be instantiated
    :rtype: int
    """
    streams_per_buffer = math.floor(get_sum_datatype_width(buffer_spec, 'DATAOUT') \
                                    / stream_width)
    assert get_sum_datatype_width(buffer_spec, 'DATAOUT') > 0, \
        "Buffer DATAOUT port width of zero"
    assert streams_per_buffer > 0, "Streams per buffer=" + \
        str(get_sum_datatype_width(buffer_spec, 'DATAOUT')) + "/" + str(stream_width)
    return math.ceil(stream_count/streams_per_buffer)

def get_overall_idx(projection, idxs):
    """ Calculate the inner block instance number based on loop unrolling factors

    :param projection: Projection definition (according to projection yaml schema) 
    :type projection: dict
    :param idxs: Unrolling factors to specify some instance
    :type idxs: dict
    :return: Instance number of specified instance
    :rtype: int
    """
    product = 1
    total = 0
    for item in idxs:
        assert item in ['URW','URN','UE','UB','UG']
    for item in ['URW','URN','UE','UB','UG']:
        if item in idxs:
            assert item in projection
            assert idxs[item] < projection[item]['value']
            assert idxs[item] >= 0
            total += product*idxs[item]
            product *= projection[item]['value']    
    return total

def AddInPort(s, width, newname):   
    """ Create a new input port at level ``s`` (if it doesn't already
    exist), and name it ``newname``
    Do nothing for clk and reset ports.

    :param s: Module at which to create a new port 
    :type s: Component class
    :param newname: Name of port to be created
    :type newname: string
    :return: The newly created port
    """
    if newname in s.__dict__.keys():
        return getattr(s, newname)
    else:
        newinport = InPort(width)
        setattr(s, newname, newinport)
        # Tie it off in case we don't use it
        tie_off_port(s,newinport)
        return newinport

def AddOutPort(s, width, newname):   
    """ Create a new output port at level ``s`` (if it doesn't already
    exist), and name it ``newname``
    Do nothing for clk and reset ports.

    :param s: Module at which to create a new port 
    :type s: Component class
    :param newname: Name of port to be created
    :type newname: string
    :return: The newly created port
    """
    if newname in s.__dict__.keys():
        return getattr(s, newname)
    else:
        newoutport = OutPort(width)
        setattr(s, newname, newoutport)
        return newoutport
    
def connect_in_to_top(s, port, newname):   
    """ Create a new input port at level ``s`` (if it doesn't already
    exist), and connect ``port`` to the new top level port.
    Do nothing for clk and reset ports.

    :param s: Module at which to create a new port 
    :type s: Component class
    :param port: port of module instance instantiated within ``s``
    :type port: Component class
    :param newname: Name of port to be created
    :type newname: string
    """
    if port._dsl.my_name == "clk" or port._dsl.my_name == "reset":
        return
    newinport = AddInPort(s,port._dsl.Type,newname)
    port //= newinport
    
def connect_out_to_top(s, port, newname): 
    """ Create a new output port at level ``s``, and connect ``port``
    to the new top level port, unless it already exists

    :param s: Module at which to create a new port 
    :type s: Component class
    :param port: port of module instance instantiated within ``s``
    :type port: Component class
    :param newname: Name of port to be created
    :type newname: string
    """       
    newoutport = AddOutPort(s, port._dsl.Type, newname)
    newoutport //= port
    
def add_n_inputs(s, n, width, prefix, start_idx=0):
    """ Create ``n`` new inputs on module ``s``, with width ``width``.
    Ports are named ``prefix``_i, where i begins at ``start_idx``.

    :param s: Module at which to create new ports 
    :type s: Component class
    :param n: Number of ports to add
    :type n: int
    :param width: Bit-width of new ports
    :type width: int
    :param start_idx: Index at which to start for port naming
    :type start_idx: int
    :param prefix: Prefix of names of new ports
    :type prefix: string
    """               
    for i in range(start_idx,start_idx+n):
        newin = AddInPort(s, width, prefix+str(i))
        
def add_n_outputs(s, n, width, prefix, start_idx=0): 
    """ Create ``n`` new outputs on module ``s``, with width ``width``.
    Ports are named ``prefix``_i, where i begins at ``start_idx``.

    :param s: Module at which to create new ports 
    :type s: Component class
    :param n: Number of ports to add
    :type n: int
    :param width: Bit-width of new ports
    :type width: int
    :param start_idx: Index at which to start for port naming
    :type start_idx: int
    :param prefix: Prefix of names of new ports
    :type prefix: string
    """             
    for i in range(start_idx, start_idx+n):
        newout = AddOutPort(s, width, prefix+str(i))
        
def tie_off_clk_reset(s):  
    """ Create internal ports and connect them to clk and reset inputs
        This is helpful because ODIN will error out otherwise.

    :param s: Module at which to tie off clk and reset
    :type s: Component class
    """            
    tie_off_port(s,s.clk)
    tie_off_port(s,s.reset)

def tie_off_port(s, port):  
    """ Create internal wire and connect it to ``port``
        This is helpful because ODIN will error out otherwise.

    :param s: Module at which to tie off clk and reset
    :type s: Component class
    :param port: Port to tie off
    :type port: Component class
    """            
    newwire = Wire(port._dsl.Type.nbits)
    setattr(s, port._dsl.my_name+"_tieoff", newwire)
    newwire //= port
    
def connect_ports_by_name(inst1, name1, inst2, name2, factor1=1, factor2=1):
    """ Connect ports named ``name1``_<#*``factor1``> on ``inst1`` to ports named
    ``name2``_<#*``factor2``> on 

    :param inst1: Module instance with output ports to be connected 
    :type inst1: Component class
    :param inst2: Module instance with input ports to be connected 
    :type inst2: Component class
    :param name1: Prefix of names of output ports of ``inst1``
    :type name1: string
    :param name2: Prefix of names of input ports of ``inst2``
    :type name2: string
    :param factor1: Factor used to match port indexes (p1[i*factor1] <==> p2[i*factor2]) 
    :type factor1: string
    :param factor2: Factor used to match port indexes (p1[i*factor1] <==> p2[i*factor2]) 
    :type factor2: string
    """             
    match_dict = {}
    connected_ins = []
    for port in inst1.get_output_value_ports():
        port1name = port._dsl.my_name
        foundname1 = re.search(name1+r"_(\d+)$", port1name)
        if foundname1:
            match_dict[str(int(foundname1.group(1))*factor1)] = port
    assert len(match_dict) > 0, "Should have found outputs with name "+ name1 + \
        " in " + str(inst1.get_output_value_ports())
   
    for port in inst2.get_input_value_ports():
        port2name = port._dsl.my_name
        foundname2 = re.search(name2+r"_(\d+)$", port2name)
        if foundname2:
            assert str(int(foundname2.group(1))*factor2) in match_dict, \
                "Should have found output with name "+ name1 + "_" + \
                str(int(foundname2.group(1))*factor2) + " in " + str(match_dict)
            connect(match_dict[str(int(foundname2.group(1))*factor2)], port)
            connected_ins += [port]
            del match_dict[str(int(foundname2.group(1))*factor2)]
    assert len(match_dict) == 0, "Match_dict: " + str(match_dict) + \
        " should match input of name "+ name2
    return connected_ins

    
