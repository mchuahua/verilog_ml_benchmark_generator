""""
PYM-TL Component Classes Implementing different parts of the dataflow
ASSUMPTIONS:
- Weights are always preloaded
- Weight stationary flow
- Inputs don't require muxing

"""
from pymtl3 import *
from pymtl3.passes.backends.verilog import *
from pymtl3.passes.backends.yosys import *
import sys
import math
import os
import copy
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import *
import module_helper_classes
from module_helper_classes import *
il = 1

class RELU(Component):
    """" This class implements a RELU function. It can either be registered
         or unregistered (at compile time) and has a single input and output
         in addition to clk and reset.
         RELU function: fout = (fin > 0)? fin : 0.
         Input and output widths are specified, and either one could be wider.

         :param activation_function_in: Input port (fin)
         :type activation_function_in: Component class
         :param activation_function_out: Output port (fout)
         :type activation_function_out: Component class
         :param internal_out0/1: Internal port used to connect input to out
         :type internal_out0/1: Component class
    """
    def construct(s, input_width=1, output_width=1, registered=False):
        """ Constructor for RELU
         :param input_width: Bit-width of ``activation_function_in``
         :type input_width: int
         :param output_width: Bit-width of ``activation_function_out``
         :type output_width: int
         :param registered: Whether to register the RELU output
         :type registered: Boolean
        """
        # Shorten the module name to the provided name.
        s.activation_function_in = InPort(input_width)
        s.activation_function_out = OutPort(output_width)
        utils.tie_off_clk_reset(s)
        min_width = min(input_width, output_width)
        max_width = max(input_width, output_width)
        s.internal_out0 = Wire(min_width)
        s.internal_out1 = Wire(max(output_width - min_width, 1))

        if registered:
            @update_ff
            def upblk0():
                if s.reset:
                    s.internal_out0 <<= 0
                    s.internal_out1 <<= 0
                else:
                    s.internal_out0 <<= (s.activation_function_in[0:min_width]
                                         if (s.activation_function_in[
                                                 input_width - 1] == 0) else 0)
        else:
            @update
            def upblk3():
                s.internal_out0 @= (s.activation_function_in[0:min_width]
                                    if (s.activation_function_in[
                                            input_width - 1] == 0) else 0)
                s.internal_out1 @= 0
        s.activation_function_out[0:min_width] //= s.internal_out0
        if (output_width > min_width):
            s.activation_function_out[min_width:max_width] //= s.internal_out1


class ActivationWrapper(Component):
    """" This module wraps several instantiations of an activation function.
         It has the same inputs and outputs as the activation function * the
         number of functions, named <activation_function_port>_<instance>.
         Clock and reset are common.
    """
    def construct(s, count=1, function="RELU", input_width=1,
                  output_width=1, registered=False):
        """ Constructor for ActivationWrapper

         :param count: Number of activation functions to instantiate
         :type count: int
         :param function: Type of activation function (eg "RELU")
         :type function: string
         :param input_width: Bit-width of ``activation_function_in``
         :type input_width: int
         :param output_width: Bit-width of ``activation_function_out``
         :type output_width: int
         :param registered: Whether to register the RELU output
         :type registered: Boolean
        """
        for i in range(count):
            assert (function == "RELU"), \
                "NON-RELU functions not currently implemented."
            curr_inst = RELU(input_width, output_width, registered)
            setattr(s, function + '_inst_' + str(i), curr_inst)

            for port in curr_inst.get_input_value_ports():
                utils.connect_in_to_top(s, port, port._dsl.my_name + "_" +
                                        str(i))
            for port in curr_inst.get_output_value_ports():
                utils.connect_out_to_top(s, port, port._dsl.my_name + "_" +
                                         str(i))


class MLB_Wrapper(Component):
    """" This module represents some block, as specified in a json description
         The point is to provide the interface of the actual hardware block
         so that it can be instantiated in other modules, and a simulation
         model.
         Simulation type specifies which sim model to use.
         Otherwise, the contents of this block is
         empty, and all outputs are tied to zero.
         One port is added for each port listed in the json port list.
         The module will end up being named "HWB_Sim__<block_name>"
    """
    def construct(s, spec={}, projs={}, sim=True):
        """ Constructor for HWB

         :param spec: Dictionary describing hardware block ports and
                      functionality
         :type spec: dict
         :param proj: Dictionary describing projection of computations
                            onto ML block
         :type proj: dict
        """
        copy_projs = copy.deepcopy(projs)
        ports_by_type = {}
        special_outs=[]
        if "simulation_model" in spec:
           special_outs=["DATA", "W", "I", "O", "AVALON_READDATA", "AVALON_WAITREQUEST",
                         "AVALON_READDATAVALID"]
        
        for port in spec['ports']:
            if not port["type"] in ("CLK", "RESET"):
                if (port["direction"] == "in"):
                    newport = utils.AddInPort(s, port["width"], port["name"])
                else:
                    if port["name"] not in s.__dict__.keys():
                        newport = utils.AddOutPort(s, port["width"],
                                                  port["name"])
                        if port["type"] not in special_outs:
                            newport //= newport._dsl.Type(0)
                typename = port["type"] + "_" + port["direction"]
                if typename in ports_by_type:
                    ports_by_type[typename] += [[port, newport]]
                else:
                    ports_by_type[typename] = [[port, newport]]
        s._dsl.args = [spec.get('block_name', "unnamed")]
        
        assert(spec.get("simulation_model","") == "MLB" or \
                 spec.get("simulation_model","") == "ML_Block")
        assert len(projs) > 0
        for req_port in ["W_in", "W_out", "I_in", "I_out",
                         "O_in", "O_out"]:
            assert req_port in ports_by_type, \
                "To run simulation, you need port of type " + req_port
        for req_port in ["W_EN_in", "I_EN_in", "ACC_EN_in"]:
            assert req_port in ports_by_type, \
                "To run simulation, you need port of type " + req_port + \
                " in definition of " + spec["block_name"] 
            assert len(ports_by_type[req_port]) == 1

        inner_projs = [proj['inner_projection'] for proj in copy_projs]
        if ("possible_projections" in spec):
            spec_keys = copy.deepcopy(spec["possible_projections"])
            for ip in inner_projs:
                total_product = 1
                max_product = 1
                for key in ["URW","URN","UE","UB","UG"]:
                    total_product *= ip[key]["value"]
                    max_product *= spec_keys[key]
                assert (total_product <= max_product)

                if (ip["URW"]["value"] > spec_keys["URW"]):
                    assert(spec_keys["URW"] == 1)
                    if ("chans") in ip["URN"]:
                        ip["URN"]["y"] = ip["URN"]["y"]*ip["URW"]["value"]
                    ip["URN"]["value"] = ip["URN"]["value"]*ip["URW"]["value"]
                    ip["URW"]["value"] = 1
                    if ("x" in ip["URW"]): 
                        ip["URW"]["x"] = 1
                    if ("y" in ip["URW"]): 
                        ip["URW"]["y"] = 1
                    
                assert(ip["URN"]["value"] <= spec_keys["URN"])
                if (ip["URN"]["value"] > spec_keys["URN"]):
                    assert(spec_keys["URN"] == 1)
                    assert (ip["URN"]["value"] <= spec_keys["UG"])
                    ip["UG"]["value"] = ip["URN"]["value"]*ip["UG"]["value"]
                    ip["URN"]["value"] = 1
                    if ("chans" in ip["URN"]): 
                        ip["URN"]["chans"] = 1
                    if ("x" in ip["URN"]): 
                        ip["URN"]["x"] = 1
                    if ("y" in ip["URN"]): 
                        ip["URN"]["y"] = 1
                    
                if (ip["UB"]["value"] > spec_keys["UB"]):
                    assert(spec_keys["UB"] == 1)
                    assert (ip["UB"]["value"] <= spec_keys["UG"])
                    ip["UG"]["value"] = ip["UB"]["value"]*ip["UG"]["value"]
                    ip["UB"]["value"] = 1
                    if ("batches" in ip["UB"]): 
                        ip["UB"]["batches"] = 1
                    if ("x" in ip["UB"]): 
                        ip["UB"]["x"] = 1
                    if ("y" in ip["UB"]): 
                        ip["UB"]["y"] = 1
                    
                if (ip["UE"]["value"] > spec_keys["UE"]):
                    assert(spec_keys["UE"] == 1)
                    assert (ip["UE"]["value"] <= spec_keys["UG"]) 
                    ip["UG"]["value"] = ip["UE"]["value"]*ip["UG"]["value"]
                    ip["UE"]["value"] = 1
    
                assert(ip["UG"]["value"] <= spec_keys["UG"])
        
        s.sim_model = module_helper_classes.MLB(copy_projs, sim=sim)
        MAC_datatypes = ['W', 'I', 'O']
        inner_bus_counts = {
            dtype: [utils.get_proj_stream_count(inner_proj, dtype)
                    for inner_proj in inner_projs]
            for dtype in MAC_datatypes}
        inner_bus_widths = {dtype: [inner_bus_count * proj['stream_info'][dtype]
                for (proj, inner_bus_count) in zip(copy_projs, inner_bus_counts[dtype])]
                for dtype in MAC_datatypes}
        assert(ports_by_type["I_out"][0][0]['width'] == ports_by_type["I_in"][0][0]['width']), \
                    "Input and output stream widths should be equal (MLB I ports)"
        i_out = ports_by_type["I_out"][0][1]
        assert(ports_by_type["W_out"][0][0]['width'] == ports_by_type["W_in"][0][0]['width']), \
                    "Input and output stream widths should be equal (MLB W ports)"
        assert(ports_by_type["O_out"][0][0]['width'] == ports_by_type["O_in"][0][0]['width']), \
                    "Input and output stream widths should be equal (MLB O ports)"
        o_out = ports_by_type["O_out"][0][1]
        assert(max(inner_bus_widths['W']) <= ports_by_type["W_in"][0][0]['width']),\
                    "Specified MLB port width not wide enough for desired unrolling scheme"
        w_in = ports_by_type["W_in"][0][1]
        assert(max(inner_bus_widths['I']) <= ports_by_type["I_in"][0][0]['width']), \
                    "Specified MLB port width not wide enough for desired unrolling scheme"
        i_in = ports_by_type["I_in"][0][1]
        assert(max(inner_bus_widths['O']) <= ports_by_type["O_in"][0][0]['width']), \
                    "Specified MLB port width not wide enough for desired unrolling scheme"
        o_in = ports_by_type["O_in"][0][1]
        connect(ports_by_type["W_EN_in"][0][1], s.sim_model.W_EN)
        connect(ports_by_type["W_out"][0][1][0:max(inner_bus_widths['W'])],s.sim_model.W_OUT)
        connect(ports_by_type["I_EN_in"][0][1], s.sim_model.I_EN)
        connect(ports_by_type["ACC_EN_in"][0][1], s.sim_model.ACC_EN)
        if ("MODE_in" in ports_by_type):
            connect(ports_by_type["MODE_in"][0][1], s.sim_model.sel)
        else:
            s.sim_model.sel //= 0
        inner_projs = [proj['inner_projection'] for proj in projs]
        inner_projs_new = [proj['inner_projection'] for proj in copy_projs]
        if ("possible_projections" in spec):
            ip = inner_projs[0]
            ip_new = inner_projs_new[0]
            dataw = projs[0]['stream_info']['I']
            
            if (ip["UE"]["value"] > spec_keys["UE"]):
                reqd_ue = ip["UE"]["value"]
                assert(spec_keys["UE"] == 1)
                s.ue_in = Wire(ports_by_type["I_in"][0][0]['width']*reqd_ue)
                for urny in range(ip["URN"].get("y",1)):
                    for urnc in range(ip["URN"].get("chans",ip["URN"].get("value",1))):
                        for ug in range(ip["UG"].get("value",1)):
                            for ubb in range(ip["UB"].get("batches",ip["UB"].get("value",1))):
                                for uby in range(ip["UB"].get("y",1)):
                                    in_chain = utils.get_overall_idx_new(ip,
                                                {'URN': {'y':urny, 'chans':urnc}, 'UB': {'y':uby, 'batches':ubb}, 'UG': {'value': ug}},
                                                order=utils.input_order,
                                                default=['batches','chans'])
                                    for ue in range(reqd_ue):
                                        out_chain = utils.get_overall_idx_new(ip_new,
                                                {'URN': {'y':urny, 'chans':urnc}, 'UB': {'y':uby, 'batches':ubb}, 'UG': {'value': ug*reqd_ue+ue}},
                                                order=utils.input_order,
                                                default=['batches','chans'])
                                        s.ue_in[out_chain*dataw:(out_chain+1)*dataw] //= i_in[(in_chain*dataw):(in_chain+1)*dataw]
                i_in = s.ue_in
                
            preload = False
            preload_bus_count = 0
            if "PRELOAD" in projs[0]:
                for pload_type in projs[0]["PRELOAD"]:
                    if pload_type["dtype"] == 'W':
                        preload = True
            if ((ip["UB"]["value"] > spec_keys["UB"]) and not preload):
                reqd_ub = ip["UB"]["value"]
                assert(spec_keys["UB"] == 1)
                s.ub_in = Wire(ports_by_type["W_in"][0][0]['width']*reqd_ub)
                for urw in range(ip["URW"].get("value",1)):
                    for urn in range(ip["URN"].get("value",1)):
                        for ug in range(ip["UG"].get("value",1)):
                            for ue in range(ip["UE"].get("value",1)):
                                in_chain = utils.get_overall_idx(
                                    ip, {'URW': urw, 'URN': urn,
                                                 'UE': ue, 'UG': ug})
                                for ub in range(reqd_ub):
                                    out_chain = utils.get_overall_idx(
                                        ip_new, {'URW': urw, 'URN': urn,
                                                     'UE': ue, 'UG': ug*reqd_ub+ub})
                                    s.ub_in[out_chain*dataw:(out_chain+1)*dataw] //= w_in[(in_chain*dataw):(in_chain+1)*dataw]
                w_in = s.ub_in
                
            if (ip["URW"]["value"] > spec_keys["URW"]):
                assert(spec_keys["URW"] == 1)
                reqd_urw = ip["URW"]["value"]
                assert(ip["URW"]["value"] <= spec_keys["URN"])
                num_chains = ip["URN"]["value"]*ip["UB"]["value"]*ip["UG"]["value"]
                dataw = projs[0]['stream_info']['I']
                for urny in range(ip["URN"].get("y",1)):
                    for urnc in range(ip["URN"].get("chans",ip["URN"].get("value",1))):
                        for ug in range(ip["UG"].get("value",1)):
                            for ubb in range(ip["UB"].get("batches",ip["UB"].get("value",1))):
                                for uby in range(ip["UB"].get("y",1)):
                                    chain = utils.get_overall_idx_new(ip,
                                                {'URN': {'y':urny, 'chans':urnc}, 'UB': {'y':uby, 'batches':ubb}, 'UG': {'value': ug}},
                                                order=utils.input_order,
                                                default=['batches','chans'])
                                    # Instantiate a reg. chain
                                    # Connect the reg. chain outputs to different parts of s.sim_model.I_IN
                                    curr_shift_reg = module_helper_classes.ShiftRegister(
                                        reg_width=dataw,
                                        length=reqd_urw, sim=False)
                                    setattr(s,"SR"+str(chain), curr_shift_reg)
                                    curr_shift_reg.input_data //= i_in[dataw*chain:dataw*(chain+1)]
                                    curr_shift_reg.ena //= ports_by_type["I_EN_in"][0][1]
                                    i_out[dataw*chain:dataw*(chain+1)] //= curr_shift_reg.output_data
                                    for reg in range(reqd_urw):
                                        stream_idx = utils.get_overall_idx_new(ip_new,
                                                {'URN': {'y':urny*reqd_urw+reg, 'chans':urnc}, 'UB': {'y':uby, 'batches':ubb}, 'UG': {'value': ug}},
                                                order=utils.input_order,
                                                default=['batches','chans'])
                                        if (reg == 0):
                                            s.sim_model.I_IN[stream_idx*dataw:(stream_idx+1)*dataw] //= i_in[chain*dataw:(chain+1)*dataw]
                                        else:
                                            regout = getattr(curr_shift_reg, "out"+str(reg-1))
                                            s.sim_model.I_IN[stream_idx*dataw:(stream_idx+1)*dataw] //= regout
            else:
                connect(i_in[0:max(inner_bus_widths['I'])], s.sim_model.I_IN)
                connect(i_out[0:max(inner_bus_widths['I'])], s.sim_model.I_OUT)
            
        else:
            connect(i_in[0:max(inner_bus_widths['I'])], s.sim_model.I_IN)
            connect(i_out[0:max(inner_bus_widths['I'])], s.sim_model.I_OUT)
                        
        connect(w_in[0:max(inner_bus_widths['W'])], s.sim_model.W_IN)
        connect(o_in[0:max(inner_bus_widths['O'])], s.sim_model.O_IN)
        connect(o_out[0:max(inner_bus_widths['O'])], s.sim_model.O_OUT)

        
class HWB_Sim(Component):
    """" This module represents some block, as specified in a json description
         The point is to provide the interface of the actual hardware block
         so that it can be instantiated in other modules, and a simulation
         model.
         Simulation type specifies which sim model to use.
         Otherwise, the contents of this block is
         empty, and all outputs are tied to zero.
         One port is added for each port listed in the json port list.
         The module will end up being named "HWB_Sim__<block_name>"
    """
    def construct(s, spec={}, projs={}, sim=True):
        """ Constructor for HWB

         :param spec: Dictionary describing hardware block ports and
                      functionality
         :type spec: dict
         :param proj: Dictionary describing projection of computations
                            onto ML block
         :type proj: dict
        """
        ports_by_type = {}
        special_outs=[]
        if "simulation_model" in spec:
           special_outs=["DATA", "W", "I", "O", "AVALON_READDATA", "AVALON_WAITREQUEST",
                         "AVALON_READDATAVALID"]
        
        for port in spec['ports']:
            if not port["type"] in ("CLK", "RESET"):
                if (port["direction"] == "in"):
                    newport = utils.AddInPort(s, port["width"], port["name"])
                else:
                    if port["name"] not in s.__dict__.keys():
                        newport = utils.AddOutPort(s, port["width"],
                                                  port["name"])
                        if port["type"] not in special_outs:
                            newport //= newport._dsl.Type(0)
                typename = port["type"] + "_" + port["direction"]
                if typename in ports_by_type:
                    ports_by_type[typename] += [[port, newport]]
                else:
                    ports_by_type[typename] = [[port, newport]]
        s._dsl.args = [spec.get('block_name', "unnamed")]
        
        # If this is an ML block, add behavioural info
        if "simulation_model" not in spec:
            utils.print_warning(il, "HW block " + spec.get("block_name","unnamed") + \
                  "has no sim model - all outputs tied off")
        else:
            if spec.get("simulation_model","") == "Buffer":
                for req in ["ADDRESS_in", "WEN_in", "DATA_in", "DATA_out"]:
                    assert req in ports_by_type, \
                        "To run simulation, you need port of type " + \
                        req +" in definition of " + spec["block_name"] 
                assert len(ports_by_type["ADDRESS_in"]) == 1  # Todo
                assert len(ports_by_type["ADDRESS_in"]) == \
                       len(ports_by_type["DATA_out"])
                assert len(ports_by_type["ADDRESS_in"]) == \
                       len(ports_by_type["WEN_in"])
                assert len(ports_by_type["ADDRESS_in"]) == \
                       len(ports_by_type["DATA_in"])
                for buffer_inst in range(len(ports_by_type["ADDRESS_in"])):
                    assert ports_by_type["DATA_out"][buffer_inst][0]["width"] == \
                           ports_by_type["DATA_in"][buffer_inst][0]["width"]
                    assert ports_by_type["WEN_in"][buffer_inst][0]["width"] == 1
                    datalen = ports_by_type["DATA_in"][buffer_inst][0]["width"]
                    addrlen = ports_by_type["ADDRESS_in"][buffer_inst][0]["width"]
                    size = 2**addrlen
                    sim_model = module_helper_classes.Buffer(datalen,
                                                             size, keepdata=False, sim=sim)
                    setattr(s,"sim_model_inst" + str(buffer_inst), sim_model)
                    connect(ports_by_type["DATA_in"][buffer_inst][1],
                            sim_model.datain)
                    connect(ports_by_type["DATA_out"][buffer_inst][1],
                            sim_model.dataout)
                    connect(ports_by_type["ADDRESS_in"][buffer_inst][1],
                            sim_model.address)
                    connect(ports_by_type["WEN_in"][buffer_inst][1],
                            sim_model.wen)
            elif spec.get("simulation_model","") == "MLB" or \
                 spec.get("simulation_model","") == "ML_Block":
                assert len(projs) > 0
                for req_port in ["W_in", "W_out", "I_in", "I_out",
                                 "O_in", "O_out"]:
                    assert req_port in ports_by_type, \
                        "To run simulation, you need port of type " + req_port
                for req_port in ["W_EN_in", "I_EN_in", "ACC_EN_in"]:
                    assert req_port in ports_by_type, \
                        "To run simulation, you need port of type " + req_port + \
                        " in definition of " + spec["block_name"] 
                    assert len(ports_by_type[req_port]) == 1
                s.sim_model = module_helper_classes.MLB(projs, sim=sim)
                MAC_datatypes = ['W', 'I', 'O']
                inner_projs = [proj['inner_projection'] for proj in projs]
                inner_bus_counts = {
                    dtype: [utils.get_proj_stream_count(inner_proj, dtype)
                            for inner_proj in inner_projs]
                    for dtype in MAC_datatypes}
                inner_bus_widths = {dtype: [inner_bus_count *
                                            proj['stream_info'][dtype]
                                            for (proj, inner_bus_count) in zip(projs, inner_bus_counts[dtype])]
                                    for dtype in MAC_datatypes}
                assert(ports_by_type["I_out"][0][0]['width'] == ports_by_type["I_in"][0][0]['width']), \
                    "Input and output stream widths should be equal (MLB I ports)"
                assert(ports_by_type["W_out"][0][0]['width'] == ports_by_type["W_in"][0][0]['width']), \
                    "Input and output stream widths should be equal (MLB W ports)"
                assert(ports_by_type["O_out"][0][0]['width'] == ports_by_type["O_in"][0][0]['width']), \
                    "Input and output stream widths should be equal (MLB O ports)"
                assert(max(inner_bus_widths['W']) <= ports_by_type["W_in"][0][0]['width']),\
                    "Specified MLB port width not wide enough for desired unrolling scheme"
                assert(max(inner_bus_widths['I']) <= ports_by_type["I_in"][0][0]['width']), \
                    "Specified MLB port width not wide enough for desired unrolling scheme"
                assert(max(inner_bus_widths['O']) <= ports_by_type["O_in"][0][0]['width']), \
                    "Specified MLB port width not wide enough for desired unrolling scheme"
                connect(ports_by_type["W_in"][0][1][0:max(inner_bus_widths['W'])],
                        s.sim_model.W_IN)
                connect(ports_by_type["W_EN_in"][0][1], s.sim_model.W_EN)
                connect(ports_by_type["W_out"][0][1][0:max(inner_bus_widths['W'])],
                        s.sim_model.W_OUT)
                connect(ports_by_type["I_in"][0][1][0:max(inner_bus_widths['I'])],
                        s.sim_model.I_IN)
                connect(ports_by_type["I_EN_in"][0][1], s.sim_model.I_EN)
                connect(ports_by_type["I_out"][0][1][0:max(inner_bus_widths['I'])],
                        s.sim_model.I_OUT)
                connect(ports_by_type["O_in"][0][1][0:max(inner_bus_widths['O'])],
                        s.sim_model.O_IN)
                connect(ports_by_type["ACC_EN_in"][0][1], s.sim_model.ACC_EN)
                connect(ports_by_type["O_out"][0][1][0:max(inner_bus_widths['O'])],
                        s.sim_model.O_OUT)
                if ("MODE_in" in ports_by_type):
                    connect(ports_by_type["MODE_in"][0][1], s.sim_model.sel)
                else:
                    s.sim_model.sel //= 0
            elif spec.get("simulation_model","") == "EMIF":
                for req_port in ["AVALON_ADDRESS_in", "AVALON_READDATA_out",
                                 "AVALON_WRITEDATA_in",
                                 "AVALON_READDATAVALID_out", "AVALON_WAITREQUEST_out",
                                 "AVALON_READ_in", "AVALON_WRITE_in"]:
                    assert req_port in ports_by_type, \
                        "To run simulation, you need port of type " + req_port + \
                        " in definition of " + spec["block_name"] 
                    assert len(ports_by_type[req_port]) == 1
                s.sim_model = module_helper_classes.EMIF(
                    datawidth=ports_by_type["AVALON_WRITEDATA_in"][0][0]["width"],
                    length=2**ports_by_type["AVALON_ADDRESS_in"][0][0]["width"],
                    startaddr=0,
                    preload_vector=spec.get('parameters',{}).get('fill', False),
                    pipelined=spec.get('parameters',{}).get('pipelined', False),
                    max_pipeline_transfers=spec.get('max_pipeline_transfers',
                                                    {}).get('max_pipeline_transfers', 4),
                    sim=True)
                connect(ports_by_type["AVALON_ADDRESS_in"][0][1], s.sim_model.avalon_address)
                connect(ports_by_type["AVALON_WRITEDATA_in"][0][1],
                        s.sim_model.avalon_writedata)
                connect(s.sim_model.avalon_readdata,
                        ports_by_type["AVALON_READDATA_out"][0][1])
                connect(ports_by_type["AVALON_READ_in"][0][1], s.sim_model.avalon_read,)
                connect(ports_by_type["AVALON_WRITE_in"][0][1], s.sim_model.avalon_write)
                connect(s.sim_model.avalon_readdatavalid,
                        ports_by_type["AVALON_READDATAVALID_out"][0][1])
                connect(s.sim_model.avalon_waitrequest,
                        ports_by_type["AVALON_WAITREQUEST_out"][0][1])
                            


class HWB_Wrapper(Component):
    """" This module wraps several instantiations of some specified block
         (``spec``). Input ports with datatype "C" (config) and "ADDRESS" are
         shared between all instances. All other ports are duplicated one for
         each instance on the top level, and named
         <instance_port_name>_<instance>. Clock and reset are common.
    """
    def construct(s, spec={}, count=1, name="_v1", projections={}):
        """ Constructor for HWB_Wrapper

         :param spec: Dictionary describing hardware block ports and
                      functionality
         :type spec: dict
         :param count: Number of blocks to instantiate
         :type count: int
         :param name: String appended to resultant module name to avoid name
                      collision bug.
         :type count: string
        """
        # Add ports shared between instances to the top level
        for i in range(count):
            if  (spec.get("simulation_model","") == "MLB" or \
                 spec.get("simulation_model","") == "ML_Block"):
                curr_inst = MLB_Wrapper(spec, projections, sim=True)
            else:
                curr_inst = HWB_Sim(spec, projections, sim=True)
            setattr(s, spec.get('block_name', "unnamed") + '_inst_' + str(i),
                    curr_inst)
            for port in spec['ports']:
                if ((port['type'] == 'C' or port['type'] == 'ADDRESS' or
                     port['type'] == 'W_EN' or port['type'] == 'I_EN' or
                     port['type'] == 'ACC_EN' or port['type'] == 'MODE')
                        and port["direction"] == "in"):
                    instport = getattr(curr_inst, port["name"])
                    #if (port['type'] == 'MODE'):
                    #    instport //= 1
                    instport //= utils.AddInPort(s,  port['width'], port["name"])
                elif port['type'] not in ('CLK', 'RESET'):
                    if (port['direction'] == "in"):
                        utils.connect_in_to_top(s, getattr(curr_inst,
                                                           port["name"]),
                                                port["name"] + "_" + str(i))
                    else:
                        utils.connect_out_to_top(s, getattr(curr_inst,
                                                            port["name"]),
                                                 port["name"] + "_" + str(i))
        utils.tie_off_clk_reset(s)


class InputBufferWrapper(Component):
    """" This module wraps several instantiations of some specified block
         (``spec``). Input ports with datatype "C" (config) and "ADDRESS" are
         shared between all instances. All other ports are duplicated one for
         each instance on the top level, and named
         <instance_port_name>_<instance>. Clock and reset are common.
    """
    def construct(s, spec={}, count=1, name="_v1", projections={}, mux=True):
        # Add ports shared between instances to the top level
        # How many address muxes are required? URNYxURNB
        muxes = [[] for proj in projections]
        j = 0
        addr_width =0
        addr_names = ''
        addrp1 = None
        for port in spec['ports']:
            if (port['type'] == 'ADDRESS'):
                addr_width = port['width']
                addr_names = port['name']
                addrp1 = utils.AddInPort(s,  port['width'], port["name"])
                addrp2 = utils.AddInPort(s,  port['width'], port["name"] + "_b")
        mux_sizes = [proj['outer_projection']['UB'].get('y',1)*proj['inner_projection']['UB'].get('y',1)* \
                     proj['inner_projection']['URN'].get('y',1)*proj['outer_projection']['URN'].get('y',1)
                     for proj in projections]
        if (max(mux_sizes)>1):
            s.addr_sel = InPort(math.ceil(math.log(max(max(mux_sizes),2),2)))
            utils.tie_off_port(s, s.addr_sel)
        s.sel = InPort(math.ceil(math.log(max(len(projections),2),2)))
        utils.tie_off_port(s, s.sel)
        
        for proj in projections:
            k = 0
            if ((proj['inner_projection']['URN'].get('y',1)*proj['outer_projection']['URN'].get('y',1) > 0)):
                for mux in range(mux_sizes[j]):
                    newmux = module_helper_classes.MUX2(
                                addr_width, math.ceil(math.log(max(mux_sizes[j],2),2)), k)
                    setattr(s, "mux_addr" + str(j) + "_" + str(k), newmux)
                    if (mux_sizes[j] > 1):
                        newmux.sel //= s.addr_sel[0:math.ceil(math.log(max(mux_sizes[j],2),2))]
                    else:
                        newmux.sel //= 0
                    newmux.in0 //= addrp1
                    newmux.in1 //= addrp2
                    muxes[j] += [newmux]
                    k = k+1
            j += 1
        
        for i in range(count):
            curr_inst = HWB_Sim(spec, projections, sim=True)
            setattr(s, spec.get('block_name', "unnamed") + '_inst_' + str(i),
                    curr_inst)
            
            for port in spec['ports']:
                if ((port['type'] == 'C' or
                     port['type'] == 'W_EN' or port['type'] == 'I_EN' or
                     port['type'] == 'ACC_EN' or port['type'] == 'MODE')
                        and port["direction"] == "in"):
                    instport = getattr(curr_inst, port["name"])
                    instport //= utils.AddInPort(s,  port['width'], port["name"])
                elif (port['type'] == 'ADDRESS'):
                    instport = getattr(curr_inst, port["name"])
                    muxs = [] # List muxes from different projections corresponding to this input image addr.
                    for pj in range(len(projections)):
                        buffer_idxs = utils.map_buffer_idx_to_y_idx(projections[pj], spec)
                        assert i < len(buffer_idxs)
                        muxs += [muxes[pj][buffer_idxs[i]]]
                    # Which muxes to connect to?
                    utils.mux_ports_by_name(s, muxs,
                                            "out", curr_inst, port['name'], insel=s.sel, sim=False, idx=str(i))
                elif port['type'] not in ('CLK', 'RESET'):
                    if (port['direction'] == "in"):
                        utils.connect_in_to_top(s, getattr(curr_inst,
                                                           port["name"]),
                                                port["name"] + "_" + str(i))
                    else:
                        utils.connect_out_to_top(s, getattr(curr_inst,
                                                            port["name"]),
                                                 port["name"] + "_" + str(i))
            
        utils.tie_off_clk_reset(s)


class MergeBusses(Component):
    """" This module connects narrow input busses to wider output busses.
         ``ins_per_out`` busses of width ``in_width`` are merged into output
        busses of width ``out_width``. Unconnected outputs are tied to 0.

         :param input_<i>: Input port
         :type input_<i>: Component class
         :param output_<i>: Output port
         :type output_<i>: Component class
    """
    def construct(s, in_width=1, num_ins=1, out_width=1, num_outs=1,
                  ins_per_out=0, sim=False):
        """ Constructor for MergeBusses

         :param in_width: Bit-width of input ports
         :type in_width: int
         :param num_ins: Number of input ports
         :type num_ins: int
         :param out_width: Bit-width of output ports
         :type out_width: int
         :param num_outs: Number of output ports
         :type num_outs: int
         :param ins_per_out: Number of output ports connecting to each input.
                             The maximum possible by default.
         :type ins_per_out: int
        """
        if (ins_per_out == 0):
            ins_per_out = math.floor(out_width/in_width)
        assert ins_per_out > 0
        #assert ins_per_out*num_outs >= num_ins, "Merge busses: Ins/out: " + \
        #    str(ins_per_out) + " num_outs:" + str(num_outs) + ", num_ins:" + \
        #    str(num_ins)
        num_ins_used = min(ins_per_out*num_outs, num_ins)

        # Add outputs to activation functions
        utils.add_n_inputs(s, num_ins, in_width, "input_")
        utils.add_n_outputs(s, num_outs, out_width, "output_")

        # Add input and output ports from each MLB
        for inp in range(num_ins_used):
            bus_idx = math.floor(inp/ins_per_out)
            bus_start = (inp % ins_per_out) * in_width
            bus_end = ((inp % ins_per_out)+1) * in_width
            input_bus = getattr(s, "input_"+str(inp))
            output_bus = getattr(s, "output_"+str(bus_idx))
            connect(input_bus[0:in_width], output_bus[bus_start:bus_end])

        for i in range(num_outs):
            output_bus = getattr(s, "output_" + str(i))
            if (i > math.floor(num_ins_used / ins_per_out)):
                output_bus //= 0
            elif ((ins_per_out*in_width < out_width)):
                output_bus[ins_per_out * in_width:out_width] //= 0

        utils.tie_off_clk_reset(s)
    
class WeightInterconnect(Component):
    """" This module connects the weight ports between the inner instances and
         the buffers.

         Two options:
         1) Connect weight buffers to MLBs
            Assume that entire input bus of each MLB should connect to the
            same buffer to simplify things. One buffer can connect to many
            MLBs though if the output is wide enough. 
         2) "PRELOAD": Given N inputs, split all MLBs into N groups
            and chain together their weights 

         TODO: Allow for directly connecting weights between instances

         :param inputs_from_buffer_<i>: Input port from weight buffer for i
                                        from 0 to ``num_buffers``
         :type inputs_from_buffer_<i>: Component class
         :param inputs_from_mlb_<i>: Input port from MLB (currently
                                     disconnected)
         :type inputs_from_mlb_<i>: Component class
         :param outputs_to_mlb_<i>: Output port to MLB
         :type outputs_to_mlb_<i>: Component class
         :param outputs_to_next_<i>: Outputs of chains of weights
         :type outputs_to_next_<i>: Outputs of chains of weights
    """
    def construct(s, buffer_width=1, mlb_width=-1, mlb_width_used=1,
                  num_buffers=1, num_mlbs=1, projection={}, sim=False,
                  num_mlbs_used=-1, inner_projection={}, dilx=1):
        """ Constructor for WeightInterconnect

         :param buffer_width: Bit-width of buffer datain/dataout ports
         :type buffer_width: int
         :param mlb_width: Total bit-width of the weight ports of the inner
                           instances.
         :type mlb_width: int
         :param mlb_width_used: Bit-width of the weight stream connecting to
                                each inner instance for this projection.
         :type mlb_width_used: int
         :param num_buffers: Total number of weight buffers
         :type num_buffers: int
         :param num_mlbs: Total number of inner instances
         :type num_mlbs: int
         :param projection: Projection specification
         :type projection: dict
        """
        # Validate inputs
        if mlb_width < 0:
            mlb_width = mlb_width_used
        streams_per_buffer = math.floor(buffer_width/mlb_width_used)
        assert mlb_width_used <= mlb_width
        assert streams_per_buffer > 0, "Insufficiently wide input buffer"
        assert num_mlbs >= utils.get_var_product(
            projection, ['UG', 'UE', 'UB', 'URN', 'URW']), \
            "Insufficient number of MLBs"
        if (num_mlbs_used < 0):
            num_mlbs_used = num_mlbs
            
        preload = False
        preload_bus_count = 0
        if "PRELOAD" in projection:
            for pload_type in projection["PRELOAD"]:
                if pload_type["dtype"] == 'W':
                    preload = True
                    preload_bus_count = pload_type["bus_count"]
                    
        assert preload or num_buffers >= math.ceil(
            utils.get_var_product(
                projection, ['UG', 'UE', 'URN', 'URW']) / streams_per_buffer),\
            "Insufficient number of weight buffers"
        
        # Add inputs from buffers
        utils.add_n_inputs(s, num_buffers, buffer_width, "inputs_from_buffer_")

        if preload:
            assert mlb_width_used * preload_bus_count <= \
                num_buffers * buffer_width
            # It doesn't matter in which order they are connected if things
            # are preloaded - just connect them in chains.
            chain_len = math.ceil(num_mlbs_used / num_buffers)
            for chain in range(num_buffers):
                start_idx = chain*chain_len
                end_idx = min(num_mlbs_used-1, start_idx + chain_len - 1)
                newout, newin = utils.chain_ports(s, start_idx,
                            end_idx, "inputs_from_mlb_{}",
                            "outputs_to_mlb_{}", mlb_width)
                
                # Then connect each chain input
                input_bus_idx = math.floor(chain / streams_per_buffer)
                input_bus = getattr(s, "inputs_from_buffer_" +
                                    str(input_bus_idx))
                section_idx = chain % streams_per_buffer
                input_bus_start = section_idx * mlb_width_used
                input_bus_end = (section_idx + 1) *  mlb_width_used
                connect(newout[0:mlb_width_used],
                        input_bus[input_bus_start:input_bus_end])
                
                # Then connect each chain output
                output_bus = utils.AddOutPort(s, buffer_width,
                                              "outputs_to_buffer_" + str(input_bus_idx))
                connect(newin[0:mlb_width_used],
                        output_bus[input_bus_start:input_bus_end])
                
        else: 
            for ug in range(projection['UG']['value']):
                for ue in range(projection['UE']['value']):
                    for ub in range(projection['UB']['value']):
                        for urn in range(projection['URN']['value']):
                            for urw in range(projection['URW']['value']):
                                # Get instance number of the MLB
                                out_idx = utils.get_overall_idx(
                                    projection, {'URW': urw, 'URN': urn,
                                                 'UB': ub, 'UE': ue, 'UG': ug})
            
                                # Create ports to and from the MLB
                                newout = utils.AddOutPort(s, mlb_width,
                                                          "outputs_to_mlb_" +
                                                          str(out_idx))
                                newin = utils.AddInPort(s, mlb_width,
                                                "inputs_from_mlb_" +
                                                str(out_idx))
            
                                # Connect all MLB weight inputs to buffers
                                stream_idx = utils.get_overall_idx(
                                    projection, {'URW': urw, 'URN': urn,
                                                 'UE': ue, 'UG': ug})
                                input_bus_idx = math.floor(stream_idx /
                                                           streams_per_buffer)
                                input_bus = getattr(s, "inputs_from_buffer_" +
                                                    str(input_bus_idx))
                                section_idx = stream_idx % streams_per_buffer
                                input_bus_start = section_idx * mlb_width_used
                                input_bus_end = (section_idx + 1) * \
                                                mlb_width_used
                                urw_total = 0
                                if (dilx > 1):
                                    if (inner_projection):
                                        num_weight_ins = utils.get_var_product(inner_projection, ['UG', 'UE',
                                                              'URN']) 
                                        for input_gen in range(num_weight_ins):
                                            for weight_x in range(inner_projection.get('URW').get('x',1)):
                                                input_w = input_gen*inner_projection.get('URW').get('x',1)+weight_x
                                                w_width = int(mlb_width_used/(inner_projection.get('URW').get('x',1)*num_weight_ins))
                                                start_w_idx = w_width*input_w
                                                end_w_idx = w_width*(input_w+1)
                                                total_urw = inner_projection.get('URW').get('x',1)*urw + weight_x
                                                if (total_urw % dilx == 0):
                                                    connect(newout[start_w_idx:end_w_idx],
                                                        input_bus[input_bus_start+start_w_idx:input_bus_start+end_w_idx])
                                                else:
                                                    newout[start_w_idx:end_w_idx] //= 0
                                    else:
                                        if (urw % dilx == 0):
                                            connect(newout[0:mlb_width_used],
                                                input_bus[input_bus_start:input_bus_end])
                                        else:
                                            newout[0:mlb_width_used] //= 0
                                else:
                                    connect(newout[0:mlb_width_used],
                                            input_bus[input_bus_start:input_bus_end])
                
                                # Then connect each chain output
                                if (ub == 0):
                                    output_bus = utils.AddOutPort(s, buffer_width,
                                                              "outputs_to_buffer_" + str(input_bus_idx))
                                    connect(newin[0:mlb_width_used],
                                        output_bus[input_bus_start:input_bus_end])

        # Tie disconnected MLBs to 0
        for i in range(num_mlbs):
            if (("outputs_to_mlb_" + str(i)) not in s.__dict__.keys()):
                newout = OutPort(mlb_width)
                setattr(s, "outputs_to_mlb_" + str(i), newout)
                newout //= 0
            utils.AddInPort(s, mlb_width, "inputs_from_mlb_" + str(i))
        utils.tie_off_clk_reset(s)


class InputInterconnect(Component):
    """" This module connects the input ports between the inner instances and
         the buffers.

         1) Connect input activation buffers to MLBs
            Assume that entire input bus of each MLB chain should connect to
            the same buffer to simplify things. One buffer can connect to
            many MLBs though if the output is wide enough.

         1) Connect MLBs to each other
            Chains of URW MLBs have the same input. Connect the inputs between
            these sets of blocks.

         TODO: Allow for preloading inputs instead of streaming them.
         TODO: deal with crossbars

         :param inputs_from_buffer_<i>: Input port from weight buffer for i
                                        from 0 to ``num_buffers``
         :type inputs_from_buffer_<i>: Component class
         :param inputs_from_mlb_<i>: Input port from MLB
                                     (currently disconnected)
         :type inputs_from_mlb_<i>: Component class
         :param outputs_to_mlb_<i>: Output port to MLB
         :type outputs_to_mlb_<i>: Component class
    """
    def construct(s, buffer_width=1, mlb_width=-1, mlb_width_used=1,
                  num_buffers=1, num_mlbs=1, projection={},
                  inner_projection={}, inner_width=1, mux_urn=False, sim=False, dily=1):
        """ Constructor for InputInterconnect

         :param buffer_width: Bit-width of buffer datain/dataout ports
         :type buffer_width: int
         :param mlb_width: Total bit-width of the weight ports of the inner
                           instances.
         :type mlb_width: int
         :param mlb_width_used: Bit-width of the weight stream connecting
                                to each inner instance for this projection.
         :type mlb_width_used: int
         :param num_buffers: Total number of weight buffers
         :type num_buffers: int
         :param num_mlbs: Total number of inner instances
         :type num_mlbs: int
         :param projection: Projection specification
         :type projection: dict
        """
        if ("outer_projection" in projection):
            full_projection = projection
            inner_projection = projection['inner_projection']
            projection = projection['outer_projection']
        else:
            full_projection = {"outer_projection":projection, "inner_projection":inner_projection}
        if mlb_width < 0:
            mlb_width = mlb_width_used
        streams_per_buffer = buffer_width/mlb_width_used
        assert mlb_width_used <= mlb_width
        #assert streams_per_buffer > 0, "Insufficiently wide input buffer"
        assert num_mlbs >= utils.get_var_product(projection, ['UG', 'UE', 'UB',
                                                              'URN', 'URW']), \
            "Insufficient number of MLBs"
        #assert num_buffers >= math.ceil(
        #    utils.get_var_product(projection, ['UG', 'UB', 'URN']) * buffers_per_stream), \
        #    "Insufficient number of input buffers"
        buffers_per_stream = math.ceil(1/streams_per_buffer)
        full_buffer_width = buffer_width
        ins_per_buffer = (mlb_width_used / inner_width) * streams_per_buffer
        if (num_buffers > 1):
            buffer_width = utils.get_max_input_bus_width(buffer_width,
                                                  full_projection, 'I')
            buffer_idxs = utils.map_buffer_idx_to_y_idx(full_projection, ibuf_count=num_buffers, ivalues_per_buf=buffer_width/inner_width)
            ins_per_buffer = buffer_width / inner_width
            buffers_per_stream = math.ceil((mlb_width_used / inner_width) / ins_per_buffer)
            streams_per_buffer = buffer_width/mlb_width_used
            
        # Add inputs from buffers
        utils.add_n_inputs(s, num_buffers, full_buffer_width, "inputs_from_buffer_")
        total_urn=inner_projection.get('URN',{}).get('y',1)*projection['URN'].get('y',1)
        mux_size = projection['UB'].get('y',1)*inner_projection.get('UB',{}).get('y',1)*total_urn
        max_ubbi = int(inner_projection.get('UB',{}).get('value',1)/inner_projection.get('UB',{}).get('y',1))
        max_unci = int(inner_projection.get('URN',{}).get('value',1)/inner_projection.get('URN',{}).get('y',1))
        if (total_urn == 1):
            mux_size = 1
            max_unci = 1
            max_ubbi = 1
        if (mux_urn and mux_size > 1):
            s.urn_sel = InPort(math.ceil(math.log(max(mux_size,2),2)))
            utils.tie_off_port(s, s.urn_sel)
        # Add input and output ports from each MLB
        mux_count = 0
        for ug in range(projection['UG']['value']):
            for ue in range(projection['UE']['value']):
                for ubb in range(int(projection['UB']['value']/projection['UB'].get('y',1))):
                    for urnc in range(int(projection['URN']['value']/projection['URN'].get('y',1))):
                        muxs = []
                        if (mux_size > 1) and mux_urn:
                            for mi in range(inner_projection['UG']['value'] *
                                             max_ubbi*max_unci):
                                newmux = module_helper_classes.MUX_NXN(
                                    inner_width, mux_size)
                                muxs += [newmux]
                                setattr(s, "mux" + str(mux_count), newmux)
                                newmux.sel //= s.urn_sel
                                mux_count += 1
                        
                        for uby in range(projection['UB'].get('y',1)):
                            for urny in range(projection['URN'].get('y',1)):
                                ub = ubb*projection['UB'].get('y',1) + uby
                                urn = urnc*projection['URN'].get('y',1) + urny 
                                chain_idx = utils.get_overall_idx(projection,
                                    {'URN': urn, 'UB': ub, 'UG': ug, 'UE': ue})
                                start_idx = chain_idx * projection['URW']['value']
                                end_idx = start_idx + projection['URW']['value'] - 1
                                newout, newin = utils.chain_ports(s, start_idx,
                                    end_idx, "inputs_from_mlb_{}",
                                    "outputs_to_mlb_{}", mlb_width)
                                  
                                # Connect the chain's input
                                stream_idx = utils.get_overall_idx_new(projection,
                                                                   {'URN': {'y':urny, 'chans':urnc},
                                                                    'UB': {'y':uby, 'batches':ubb},
                                                                    'UG': {'value': ug}},
                                     order=utils.input_order,
                                     default=['batches','chans'])
                                streams_per_buf_int = math.floor(streams_per_buffer)
                                for buf in range(buffers_per_stream):
                                    input_bus_idx = stream_idx*buffers_per_stream+buf
                                    input_bus_start = 0
                                    input_bus_end = min(buffer_width,mlb_width_used)
                                    if (streams_per_buffer > 1):
                                        input_bus_idx = math.floor(stream_idx / streams_per_buf_int)
                                        section_idx = stream_idx % streams_per_buf_int
                                        input_bus_start = section_idx * mlb_width_used
                                        input_bus_end = (section_idx + 1) * \
                                        mlb_width_used
                                    input_bus = getattr(s, "inputs_from_buffer_" +
                                                        str(input_bus_idx))
                                    if mux_urn and (mux_size > 1):
                                        # For each separate input image connected to this MLB...
                                        for ugi in range(inner_projection['UG']['value']):
                                            for ubbi in range(max_ubbi):
                                                for unci in range(max_unci):
                                                    # For each different input from that image,
                                                    # Connect it to the mux.
                                                    currmux = muxs[ugi*max_ubbi*max_unci+ubbi*max_unci+unci]                        
                                                    
                                                    for ubyi in range(inner_projection['UB'].get('y',1)):
                                                        for unyi in range(inner_projection['URN'].get('y',1)):
                                                            ubi = ubbi*inner_projection['UB'].get('y',1) + ubyi
                                                            uni = unci*inner_projection['URN'].get('y',1) + unyi
                                                            mlb_in_idx = utils.get_overall_idx_new(inner_projection,
                                                                   {'URN': {'y':unyi, 'chans':unci},
                                                                    'UB': {'y':ubyi, 'batches':ubbi},
                                                                    'UG': {'value': ugi}},
                                                                   order=utils.input_order,
                                                                   default=['batches','chans'])
                                                            if (math.floor(mlb_in_idx/ins_per_buffer) == buf):
                                                                curr_uby = uby*inner_projection['UB'].get('y',1)+ubyi
                                                                total_uny = inner_projection['URN'].get('y',1)*projection['URN'].get('y',1)
                                                                curr_uny = urny*inner_projection['URN'].get('y',1)+unyi
                                                                mux_in_idx = curr_uby*total_uny+curr_uny
                                                                if (num_buffers > 1):
                                                                    assert(mux_in_idx == buffer_idxs[input_bus_idx])
                                                                muxin = getattr(currmux, "in" + str(mux_in_idx))
                                                                muxout = getattr(currmux, "out" + str(mux_in_idx))
                                                                total_idx = input_bus_start+math.floor(mlb_in_idx % ins_per_buffer)*inner_width
                                                                connect(input_bus[total_idx:total_idx+inner_width], muxin)
                                                                if (curr_uny % dily == 0):
                                                                    connect(muxout, newout[mlb_in_idx*inner_width:
                                                                                       (mlb_in_idx+1)*inner_width])
                                                                else:
                                                                    newout[mlb_in_idx*inner_width:(mlb_in_idx+1)*inner_width] //= 0
                                                                
                                    else:
                                        section_w = min(buffer_width,mlb_width_used) #int(mlb_width_used/buffers_per_stream)
                                        buf_start_idx = buf*section_w
                                        connection_width = min(mlb_width, buf_start_idx+(section_w)) - buf_start_idx
                                        connect(newout[buf_start_idx:buf_start_idx + connection_width],
                                                input_bus[input_bus_start:
                                                          input_bus_start + connection_width])
                                    # And one of the outputs
                                    if (ue == 0):
                                        output_bus = utils.AddOutPort(s, buffer_width,
                                                                      "outputs_to_buffer_" +
                                                                      str(input_bus_idx))
                                        section_w = min(buffer_width,mlb_width_used) #int(mlb_width_used/buffers_per_stream)
                                        #section_w = int(mlb_width_used/buffers_per_stream)
                                        buf_start_idx = buf*section_w
                                        connection_width = min(mlb_width, buf_start_idx+(section_w)) - buf_start_idx
                                        connect(newin[buf_start_idx:buf_start_idx + connection_width],
                                                output_bus[input_bus_start:input_bus_start + connection_width])
                                        
        # Tie disconnected MLBs to 0
        for i in range(num_mlbs):
            if ("outputs_to_mlb_" + str(i) not in s.__dict__.keys()):
                newout = OutPort(mlb_width)
                setattr(s, "outputs_to_mlb_" + str(i), newout)
                newout //= 0
            utils.AddInPort(s, mlb_width, "inputs_from_mlb_" + str(i))
        utils.tie_off_clk_reset(s)


class OutputPSInterconnect(Component):
    """" This module connects the output ports between the inner instances and
         the activation functions

         1) Connect MLBs to activation functions
            Split the outputs of chains of MLBs into activations, and connect
            them to the corresponding activation functions.

         1) Connect MLBs to each other
            Chains of URW*URN MLBs have the same output. Connect the outputs
            between these sets of blocks.

         TODO: Allow for weight stationary flow
         TODO: Allow of loading partial sums from a buffer.
         TODO: Send partial sums to a buffer.

         :param outputs_to_afs_<i>: Output ports connecting to activation
                                    functions
         :type outputs_to_afs_<i>: Component class
         :param inputs_from_mlb_<i>: Input port from MLB
                                     (currently disconnected)
         :type inputs_from_mlb_<i>: Component class
         :param outputs_to_mlb_<i>: Output port to MLB
         :type outputs_to_mlb_<i>: Component class
    """
    def construct(s, af_width=1, mlb_width=-1, mlb_width_used=1, num_afs=1,
                  num_mlbs=1, projection={}, sim=False, input_buf_width=0,
                  num_input_bufs=0):
        """ Constructor for OutputInterconnect

         :param af_width: Bit-width of activation function input
         :type af_width: int
         :param mlb_width: Total bit-width of the weight ports of the inner
                           instances.
         :type mlb_width: int
         :param mlb_width_used: Bit-width of the weight stream connecting to
                                each inner instance for this projection.
         :type mlb_width_used: int
         :param num_afs: Total number of activation functions available
         :type num_afs: int
         :param num_mlbs: Total number of inner instances
         :type num_mlbs: int
         :param projection: Projection specification
         :type projection: dict
        """
        if mlb_width < 0:
            mlb_width = mlb_width_used
        acts_per_stream = math.floor(mlb_width_used / af_width)
        assert mlb_width_used <= mlb_width
        assert mlb_width_used % af_width == 0, \
            "The activation input width should be a factor of the total " + \
            "output stream width"
        assert acts_per_stream > 0, "Activation function width too wide"
        assert num_mlbs >= utils.get_var_product(projection,
                                                 ['UG', 'UE', 'UB', 'URN',
                                                  'URW']), \
            "Insufficient number of MLBs"
        assert num_afs >= math.ceil(utils.get_var_product(
            projection, ['UG', 'UB', 'UE']) * acts_per_stream), \
            "Insufficient number of activation functions"

        # Add outputs to activation functions
        outs_to_afs = utils.add_n_outputs(s, num_afs, af_width, "outputs_to_afs_")
        if (num_input_bufs > 0):
            utils.add_n_inputs(s, num_input_bufs, input_buf_width, "ps_inputs_from_buffer_")

        # Add input and output ports from each MLB
        connected_outs = []
        for ug in range(projection['UG']['value']):
            for ue in range(projection['UE']['value']):
                for ub in range(projection['UB']['value']):
                    chain_idx = utils.get_overall_idx(projection,
                            {'UB': ub, 'UG': ug, 'UE': ue})
                    chain_len = projection['URW']['value'] * \
                                projection['URN']['value']
                    start_idx = chain_idx * chain_len
                    end_idx = start_idx + chain_len - 1
                    newout, newin = utils.chain_ports(s, start_idx, end_idx,
                                         "inputs_from_mlb_{}",
                                         "outputs_to_mlb_{}", mlb_width)
                    if (num_input_bufs == 0):
                        newout[0:mlb_width_used] //= 0
                    output_bus_idx = chain_idx * acts_per_stream
                    
                    # Connect input stream.
                    if (num_input_bufs > 0):
                        assert input_buf_width >= mlb_width_used
                        streams_per_buffer = math.floor(input_buf_width /
                                                        mlb_width_used)
                        input_bus_idx = math.floor(chain_idx /
                                                   streams_per_buffer)
                        section_idx = chain_idx % streams_per_buffer
                        input_bus_start = section_idx * mlb_width_used
                        input_bus_end = (section_idx + 1) * mlb_width_used
                        input_bus = getattr(s, "ps_inputs_from_buffer_" +
                                            str(input_bus_idx))
                        connect(input_bus[input_bus_start:input_bus_end],
                                newout[0:mlb_width_used]
                                )
                        
                    for out_part in range(acts_per_stream):
                        output_bus = getattr(s, "outputs_to_afs_" +
                                             str(output_bus_idx + out_part))
                        connected_outs += [output_bus]
                        output_bus_start = out_part * af_width
                        output_bus_end = (out_part + 1) * af_width
                        connect(output_bus, newin[output_bus_start:
                                                  output_bus_end])

        # Tie disconnected MLBs to 0
        for i in range(num_mlbs):
            if ("outputs_to_mlb_" + str(i) not in s.__dict__.keys()):
                newout = OutPort(mlb_width)
                setattr(s, "outputs_to_mlb_" + str(i), newout)
                newout //= 0
            newin = utils.AddInPort(s, mlb_width, "inputs_from_mlb_" +
                                    str(i))
        # Tie disconnected outs to 0
        for out in outs_to_afs:
            if (out not in connected_outs):
                out //= 0
        utils.tie_off_clk_reset(s)


class Datapath(Component):
    """" This module includes the whole datapath:

         :param mlb_modules: Contains all MLB modules
         :type mlb_modules: HWB_Wrapper Component
         :param weight_modules: Contains all weight buffers
         :type weight_modules: HWB_Wrapper Component
         :param input_act_modules: Contains all input activation buffers
         :type input_act_modules: HWB_Wrapper Component
         :param output_act_modules: Contains all output activation buffers
         :type output_act_modules: HWB_Wrapper Component
         :param activation_function_modules: Contains all activation functions
         :type activation_function_modules: ActivationWrapper Component
         :param weight_interconnect: Interconnect for weights
         :type weight_interconnect: WeightInterconnect Component
         :param input_interconnect: Interconnect for inputs
         :type input_interconnect: InputInterconnect Component
         :param output_ps_interconnect: Interconnect for partial sums
         :type output_ps_interconnect: OutputPSInterconnect Component
         :param output_interconnect: Interconnect for activation outputs
         :type output_interconnect: MargeBusses Component
    """
    def construct(s, mlb_spec={}, wb_spec={}, ib_spec={}, ob_spec={},
                  proj_specs=[]):
        """ Constructor for Datapath

         :param af_width: Bit-width of activation function input
         :type af_width: int
         :param mlb_width: Total bit-width of the weight ports of the inner
                           instances.
         :type mlb_width: int
         :param mlb_width_used: Bit-width of the weight stream connecting
                                to each inner instance for this projection.
         :type mlb_width_used: int
         :param num_afs: Total number of activation functions available
         :type num_afs: int
         :param num_mlbs: Total number of inner instances
         :type num_mlbs: int
         :param projection: Projection specification
         :type projection: dict
        """
        printi(il,"{:=^60}".format("> Constructing Datapath with MLB block " +
                               str(mlb_spec.get('block_name', "unnamed") +
                                   " <")))
        MAC_datatypes = ['W', 'I', 'O']
        buffer_specs = {'W': wb_spec, 'I': ib_spec, 'O': ob_spec}

        # Calculate required MLB interface widths and print information
        inner_projs = [proj_spec['inner_projection'] for proj_spec in proj_specs]
        MAC_counts = [utils.get_mlb_count(inner_proj) for inner_proj in inner_projs]
        inner_bus_counts = {dtype: [utils.get_proj_stream_count(inner_proj,
                                 dtype) for inner_proj in inner_projs]
                            for dtype in MAC_datatypes}
        inner_data_widths = {dtype: [proj_spec['stream_info'][dtype] for proj_spec in proj_specs]
                             for dtype in MAC_datatypes}
        inner_bus_widths = {dtype: [inner_bus_count * inner_data_width
                                 for (inner_bus_count,inner_data_width) in zip(inner_bus_counts[dtype],inner_data_widths[dtype])]
                                 for dtype in MAC_datatypes} 
        for (proj_spec, MAC_count, inner_bus_count, inner_data_width, inner_bus_width) in zip(proj_specs, MAC_counts, inner_bus_counts, inner_data_widths, inner_bus_widths):
            print(utils.print_table("ML Block Details, Projection " +
                                    proj_spec.get("name", "unnamed"),
                                    [["Num MACs", MAC_count,
                                      "(MACs within each MLB)"],
                                     ["bandwidth by type", inner_bus_count,
                                      "(number of in and output values per MLB)"],
                                     ["data widths by type", inner_data_width,
                                      "(bit-width of each value)"],
                                     ["total bus width, by type", inner_bus_width,
                                      "(bit-width of MLB interface)"]], il) + "\n")

        # Check that this configuration is supported by the hardware model
        assert MAC_count <= mlb_spec['MAC_info']['num_units']
        for dtype in MAC_datatypes:
            for i in range(len(inner_bus_widths[dtype])):
                assert inner_bus_widths[dtype][i] <= \
                    utils.get_sum_datatype_width(mlb_spec, dtype)
                if (inner_data_widths[dtype][i] > \
                    mlb_spec['MAC_info']['data_widths'][dtype]):
                    utils.print_warning(il, "MLB width insufficient to for inner projection")

        # Calculate required number of MLBs, IO streams, activations
        outer_projs = [proj_spec['outer_projection'] for proj_spec in proj_specs]
        MLB_counts = [utils.get_mlb_count(outer_proj) for outer_proj in outer_projs]
        outer_bus_counts = {dtype: [utils.get_proj_stream_count(outer_proj,
                                                               dtype)
                                for outer_proj in outer_projs] for dtype in MAC_datatypes} 
        outer_bus_widths = {dtype: [outer_bus_count * inner_bus_width
                                 for (outer_bus_count,inner_bus_width) in zip(outer_bus_counts[dtype], inner_bus_widths[dtype])]
                                for dtype in MAC_datatypes}
        total_bus_counts = {dtype: [outer_bus_count * inner_bus_count
                            for (outer_bus_count,inner_bus_count) in zip(outer_bus_counts[dtype], inner_bus_counts[dtype])]
                            for dtype in MAC_datatypes}
        buffer_counts = {}
        buffer_counts['W'] = [utils.get_num_buffers_reqd(buffer_specs['W'],
                                                            outer_bus_count, inner_bus_width)
                         for (outer_bus_count,inner_bus_width) in zip(outer_bus_counts['W'], inner_bus_widths['W'])]
        max_input_buf_widths = [utils.get_max_input_bus_width(utils.get_sum_datatype_width(buffer_specs['I'], "DATA", ["in"]), proj, 'I') for proj in proj_specs]
        buffer_counts['I'] = [utils.get_num_buffers_reqd(buffer_specs['I'],
                                                            outer_bus_count, inner_bus_width, mw)
                         for (outer_bus_count,inner_bus_width, mw) in zip(outer_bus_counts['I'], inner_bus_widths['I'], max_input_buf_widths)]
        buffer_counts['O'] = [utils.get_num_buffers_reqd(buffer_specs['O'],
                                                        outer_bus_counto *
                                                        inner_bus_counto,
                                                        inner_data_widthi)
                              for (outer_bus_counto, inner_bus_counto, inner_data_widthi) in zip(outer_bus_counts["O"],
                                                                                                 inner_bus_counts["O"],
                                                                                                 inner_data_widths["I"])]
        
        for (proj_spec, MAC_count, outer_bus_width, total_bus_count) in zip(proj_specs, MAC_counts, outer_bus_widths, total_bus_counts):
            print(utils.print_table("Dataflow Details, Projection " +
                                proj_spec.get("name", "unnamed"),
                                [["Num MLBs", MAC_count,
                                  "(Number of MLBs required for projection)"],
                                 ["total data widths by type",
                                  outer_bus_width,
                                  "(total data width from buffers)"],
                                 ["bandwidth, by type", total_bus_count,
                                  "(total # values from buffers)"],
                                 ],#["# buffers, by type", buffer_counts]],
                                  il) + "\n")

        # Instantiate MLBs, buffers
        s.sel = InPort(math.ceil(math.log(max(len(proj_specs),2),2)))
        utils.tie_off_port(s, s.sel)
        s.mlb_modules = HWB_Wrapper(mlb_spec, max(MLB_counts),
                                    projections=proj_specs)
        s.weight_modules = HWB_Wrapper(buffer_specs['W'],
                                       max(buffer_counts['W']))
        s.input_act_modules = InputBufferWrapper(buffer_specs['I'],
                                                 max(buffer_counts['I']),
                                                 projections=proj_specs)
        s.input_act_modules.sel //= s.sel
        s.output_act_modules = HWB_Wrapper(buffer_specs['O'],
                                           max(buffer_counts['O']),
                                           name='_v2')
        activation_function_modules = []
        for i in range(len(proj_specs)):
            new_act_modules = ActivationWrapper(
                count=max(total_bus_counts['O']),
                function=utils.get_activation_function_name(proj_specs[i]),
                input_width=max(inner_data_widths['O']),
                output_width=max(inner_data_widths['I']),
                registered=False)
            if (i > 0):
                newname = proj_specs[i].get("name",i)
            else:
                newname = ""
            activation_function_modules += [new_act_modules]
            setattr(s,"activation_function_modules"+newname, new_act_modules)

        # Instantiate interconnects
        weight_interconnects = []
        input_interconnects = []
        output_ps_interconnects = []
        output_interconnects = []
        for i in range(len(proj_specs)):
            if (i > 0):
                newname = proj_specs[i].get("name",i)
            else:
                newname = ""
            weight_interconnect = WeightInterconnect(
                buffer_width=utils.get_sum_datatype_width(buffer_specs['W'],
                                                          'DATA', ["in"]),
                mlb_width=utils.get_sum_datatype_width(mlb_spec, 'W', ["in"]),
                mlb_width_used=inner_bus_widths['W'][i],
                num_buffers=max(buffer_counts['W']),
                num_mlbs=max(MLB_counts),
                projection=outer_projs[i],
                inner_projection=inner_projs[i],
                dilx=proj_specs[i].get("dilation",{}).get("x",1))
            weight_interconnects += [weight_interconnect]
            setattr(s,"weight_interconnect"+newname, weight_interconnect)
            input_interconnect = InputInterconnect(
                buffer_width=utils.get_sum_datatype_width(buffer_specs['I'],
                                                          'DATA', ["in"]),
                mlb_width=utils.get_sum_datatype_width(mlb_spec, 'I', ["in"]),
                mlb_width_used=inner_bus_widths['I'][i],
                num_buffers=max(buffer_counts['I']),
                num_mlbs=max(MLB_counts),
                projection=proj_specs[i],
                inner_projection=inner_projs[i],
                inner_width=inner_data_widths['I'][i],
                mux_urn=True,
                dily=proj_specs[i].get("dilation",{}).get("y",1)
            )
            setattr(s,"input_interconnect"+newname, input_interconnect)
            input_interconnects += [input_interconnect]
            output_ps_interconnect = OutputPSInterconnect(
                af_width=inner_data_widths['O'][i],
                mlb_width=utils.get_sum_datatype_width(mlb_spec, 'O', ["in"]),
                mlb_width_used=inner_bus_widths['O'][i],
                num_afs=max(total_bus_counts['O']),
                num_mlbs=max(MLB_counts),
                projection=outer_projs[i])
            output_ps_interconnects += [output_ps_interconnect]
            setattr(s,"output_ps_interconnect"+newname, output_ps_interconnect)
            output_interconnect = MergeBusses(in_width=inner_data_widths['I'][i],
                                            num_ins=max(total_bus_counts['O']),
                                            out_width=utils.
                                            get_sum_datatype_width(
                                                buffer_specs['O'], 'DATA', ["in"]),
                                            num_outs=max(buffer_counts['O']))
            output_interconnects += [output_interconnect]
            setattr(s,"output_interconnect"+newname, output_interconnect)

        # Connect MLB sel
        modeports = list(utils.get_ports_of_type(mlb_spec, 'MODE', ["in"]))
        connected_ins = []
        if (len(modeports) > 0):
            mlb_sel_port = getattr(s.mlb_modules, modeports[0]["name"])
            connected_ins += [mlb_sel_port]
            mlb_sel_port //= s.sel
        
        # Connect weight interconnect
        for portname in utils.get_ports_of_type(mlb_spec, 'W', ["out"]):
            for i in range(len(proj_specs)):
                weight_interconnect = weight_interconnects[i]
                connected_ins += utils.connect_ports_by_name(s.mlb_modules,
                                                         portname["name"]+"_(\d+)",
                                                         weight_interconnect,
                                                         "inputs_from_mlb_(\d+)")

        for portname in utils.get_ports_of_type(mlb_spec, 'W', ["in"]):
            connected_ins += utils.mux_ports_by_name(s,
                weight_interconnects, "outputs_to_mlb_(\d+)", s.mlb_modules,
                                                     portname["name"]+"_(\d+)", insel=s.sel)

        for portname in utils.get_ports_of_type(buffer_specs['W'], 'DATA',
                                                ["out"]):
            for i in range(len(proj_specs)):
                weight_interconnect = weight_interconnects[i]
                connected_ins += utils.connect_ports_by_name(s.weight_modules,
                                                         portname["name"]+"_(\d+)",
                                                         weight_interconnect,
                                                         "inputs_from_buffer_(\d+)")

        # Connect input interconnect
        for portname in utils.get_ports_of_type(mlb_spec, 'I', ["out"]):
            for i in range(len(proj_specs)):
                input_interconnect = input_interconnects[i]
                connected_ins += utils.connect_ports_by_name(s.mlb_modules,
                                                         portname["name"]+"_(\d+)",
                                                         input_interconnect,
                                                         "inputs_from_mlb_(\d+)")

        for portname in utils.get_ports_of_type(mlb_spec, 'I', ["in"]):
            connected_ins += utils.mux_ports_by_name(s, input_interconnects,
                                                     "outputs_to_mlb_(\d+)",
                                                     s.mlb_modules,
                                                     portname["name"]+"_(\d+)",
                                                     insel=s.sel)
        
        for portname in utils.get_ports_of_type(buffer_specs['I'], 'DATA',
                                                ["out"]):
            for i in range(len(proj_specs)):
                input_interconnect = input_interconnects[i]
                connected_ins += utils.connect_ports_by_name(s.input_act_modules,
                                                         portname["name"]+"_(\d+)",
                                                         input_interconnect,
                                                         "inputs_from_buffer_(\d+)")

        # Connect partial sum interconnect
        for portname in utils.get_ports_of_type(mlb_spec, 'O', ["out"]): 
            for i in range(len(proj_specs)):
                output_ps_interconnect = output_ps_interconnects[i]
                connected_ins += utils.connect_ports_by_name(s.mlb_modules,
                    portname["name"]+"_(\d+)", output_ps_interconnect,
                    "inputs_from_mlb_(\d+)")
        for portname in utils.get_ports_of_type(mlb_spec, 'O', ["in"]):
            connected_ins += utils.mux_ports_by_name(s,
                output_ps_interconnects, "outputs_to_mlb_(\d+)",
                s.mlb_modules, portname["name"]+"_(\d+)", insel=s.sel)
    
        for i in range(len(proj_specs)):
            output_ps_interconnect = output_ps_interconnects[i]
            output_interconnect = output_interconnects[i]
            activation_functions = activation_function_modules[i]
            connected_ins += utils.connect_ports_by_name(
                output_ps_interconnect, "outputs_to_afs_(\d+)",
                activation_functions, "activation_function_in_(\d+)")
            connected_ins += utils.connect_ports_by_name(
                activation_functions, "activation_function_out_(\d+)",
                output_interconnect, "input_(\d+)")
            
        for portname in utils.get_ports_of_type(buffer_specs['O'], 'DATA',
                                                ["in"]):
            connected_ins += utils.mux_ports_by_name(s,
                output_interconnects, "output_(\d+)", s.output_act_modules,
                portname["name"]+"_(\d+)", insel=s.sel)

        # Connect output buffers to top
        for port in s.output_act_modules.get_output_value_ports():
            for dout in utils.get_ports_of_type(buffer_specs['O'], 'DATA',
                                                ["out"]):
                if dout["name"] in port._dsl.my_name:
                    utils.connect_out_to_top(s, port, port._dsl.my_name)

        # Connect input and weight datain to a common port
        utils.AddInPort(s,utils.get_sum_datatype_width(buffer_specs['I'], 'DATA', ["in"]),
                  "input_datain")
        for port in utils.get_ports_of_type(buffer_specs['I'], 'DATA', ["in"]):
            connected_ins += utils.connect_inst_ports_by_name(s, "input_datain",
                                                              s.input_act_modules,
                                                              port["name"])
        utils.AddInPort(s,utils.get_sum_datatype_width(buffer_specs['W'], 'DATA', ["in"]),
                  "weight_datain")
        for port in utils.get_ports_of_type(buffer_specs['W'], 'DATA', ["in"]):
            connected_ins += utils.connect_inst_ports_by_name(s, "weight_datain",
                                                              s.weight_modules,
                                                              port["name"])
        for inst in [s.activation_function_modules, s.mlb_modules,
                     s.mlb_modules, s.output_act_modules, s.input_act_modules,
                     s.weight_interconnect, s.output_ps_interconnect,
                     s.input_interconnect, s.weight_modules]:
            for port in (inst.get_input_value_ports()):
                if (port._dsl.my_name not in s.__dict__.keys()) and \
                   (port not in connected_ins):
                    utils.connect_in_to_top(s, port, inst._dsl.my_name + "_" +
                                            port._dsl.my_name + "_top")
