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
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import utils
from module_helper_classes import *


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
    def construct(s, spec={}, inner_proj={}):
        """ Constructor for HWB

         :param spec: Dictionary describing hardware block ports and
                      functionality
         :type spec: dict
         :param inner_proj: Dictionary describing projection of computations
                            onto ML block
         :type inner_proj: dict
        """
        # If this is an ML block, add behavioural info
        if "simulation_model" in spec:
            assert len(inner_proj) > 0

        for port in spec['ports']:
            if not port["type"] in ("CLK", "RESET"):
                if (port["direction"] == "in"):
                    utils.AddInPort(s, port["width"], port["name"])
                else:
                    if port["name"] not in s.__dict__.keys():
                        newout = utils.AddOutPort(s, port["width"],
                                                  port["name"])
                        newout //= newout._dsl.Type(0)
        s._dsl.args = [spec.get('block_name', "unnamed")]


class HWB_Wrapper(Component):
    """" This module wraps several instantiations of some specified block
         (``spec``). Input ports with datatype "C" (config) and "ADDRESS" are
         shared between all instances. All other ports are duplicated one for
         each instance on the top level, and named
         <instance_port_name>_<instance>. Clock and reset are common.
    """
    def construct(s, spec={}, count=1, name="_v1", projection={}):
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
        for port in spec['ports']:
            if ((port['direction'] == "in") and ((port['type'] == 'C') or
                                                 (port['type'] == 'ADDRESS'))):
                utils.AddInPort(s, port['width'], port["name"])

        for i in range(count):
            curr_inst = HWB_Sim(spec, projection)
            setattr(s, spec.get('block_name', "unnamed") + '_inst_' + str(i),
                    curr_inst)
            for port in spec['ports']:
                if ((port['type'] == 'C' or port['type'] == 'ADDRESS')
                        and port["direction"] == "in"):
                    instport = getattr(curr_inst, port["name"])
                    instport //= getattr(s, port["name"])
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
                  ins_per_out=0):
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
        assert ins_per_out*num_outs >= num_ins, "Merge busses: Ins/out: " + \
            str(ins_per_out) + " num_outs:" + str(num_outs) + ", num_ins:" + \
            str(num_ins)

        # Add outputs to activation functions
        utils.add_n_inputs(s, num_ins, in_width, "input_")
        utils.add_n_outputs(s, num_outs, out_width, "output_")

        # Add input and output ports from each MLB
        for inp in range(num_ins):
            bus_idx = math.floor(inp/ins_per_out)
            bus_start = (inp % ins_per_out) * in_width
            bus_end = ((inp % ins_per_out)+1) * in_width
            input_bus = getattr(s, "input_"+str(inp))
            output_bus = getattr(s, "output_"+str(bus_idx))
            connect(input_bus[0:in_width], output_bus[bus_start:bus_end])

        for i in range(num_outs):
            output_bus = getattr(s, "output_" + str(i))
            if (i > math.floor(num_ins / ins_per_out)):
                output_bus //= 0
            elif ((ins_per_out*in_width < out_width)):
                output_bus[ins_per_out * in_width:out_width] //= 0

        utils.tie_off_clk_reset(s)


class WeightInterconnect(Component):
    """" This module connects the weight ports between the inner instances and
         the buffers.

         1) Connect weight buffers to MLBs
            Assume that entire input bus of each MLB should connect to the
            same buffer to simplify things. One buffer can connect to many
            MLBs though if the output is wide enough.

         TODO: Allow for directly connecting weights between instances
         TODO: Allow for preloading all weights from a single buffer

         :param inputs_from_buffer_<i>: Input port from weight buffer for i
                                        from 0 to ``num_buffers``
         :type inputs_from_buffer_<i>: Component class
         :param inputs_from_mlb_<i>: Input port from MLB (currently
                                     disconnected)
         :type inputs_from_mlb_<i>: Component class
         :param outputs_to_mlb_<i>: Output port to MLB
         :type outputs_to_mlb_<i>: Component class
    """
    def construct(s, buffer_width=1, mlb_width=1, mlb_width_used=1,
                  num_buffers=1, num_mlbs=1, projection={}):
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
        streams_per_buffer = math.floor(buffer_width/mlb_width_used)
        assert mlb_width_used <= mlb_width
        assert streams_per_buffer > 0, "Insufficiently wide input buffer"
        assert num_mlbs >= utils.get_var_product(
            projection, ['UG', 'UE', 'UB', 'URN', 'URW']), \
            "Insufficient number of MLBs"
        assert num_buffers >= math.ceil(
            utils.get_var_product(
                projection, ['UG', 'UE', 'URN', 'URW']) / streams_per_buffer),\
            "Insufficient number of weight buffers"

        # Add inputs from buffers
        utils.add_n_inputs(s, num_buffers, buffer_width, "inputs_from_buffer_")

        for ug in range(projection['UG']['value']):
            for ue in range(projection['UE']['value']):
                for ub in range(projection['UB']['value']):
                    for urn in range(projection['URN']['value']):
                        for urw in range(projection['URW']['value']):
                            # Get instance number of the MLB
                            out_idx = utils.get_overall_idx(
                                projection, {'URW': urw, 'URN': urn, 'UB': ub,
                                             'UE': ue, 'UG': ug})

                            # Create ports to and from the MLB
                            newout = utils.AddOutPort(s, mlb_width,
                                                      "outputs_to_mlb_" +
                                                      str(out_idx))
                            utils.AddInPort(s, mlb_width, "inputs_from_mlb_" +
                                            str(out_idx))

                            # Connect all MLB weight inputs to buffers
                            stream_idx = utils.get_overall_idx(
                                projection, {'URW': urw, 'URN': urn, 'UE': ue,
                                             'UG': ug})
                            input_bus_idx = math.floor(stream_idx /
                                                       streams_per_buffer)
                            input_bus = getattr(s, "inputs_from_buffer_" +
                                                str(input_bus_idx))
                            section_idx = stream_idx % streams_per_buffer
                            input_bus_start = section_idx * mlb_width_used
                            input_bus_end = (section_idx + 1) * mlb_width_used
                            connect(newout[0:mlb_width_used],
                                    input_bus[input_bus_start:input_bus_end])

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
    def construct(s, buffer_width=1, mlb_width=1, mlb_width_used=1,
                  num_buffers=1, num_mlbs=1, projection={}):
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
        streams_per_buffer = math.floor(buffer_width/mlb_width_used)
        assert mlb_width_used <= mlb_width
        assert streams_per_buffer > 0, "Insufficiently wide input buffer"
        assert num_mlbs >= utils.get_var_product(projection, ['UG', 'UE', 'UB',
                                                              'URN', 'URW']), \
            "Insufficient number of MLBs"
        assert num_buffers >= math.ceil(
            utils.get_var_product(projection, ['UG', 'UB', 'URN']) /
                                  streams_per_buffer), \
            "Insufficient number of input buffers"

        # Add inputs from buffers
        utils.add_n_inputs(s, num_buffers, buffer_width, "inputs_from_buffer_")

        # Add input and output ports from each MLB
        for ug in range(projection['UG']['value']):
            for ue in range(projection['UE']['value']):
                for ub in range(projection['UB']['value']):
                    for urn in range(projection['URN']['value']):
                        for urw in range(projection['URW']['value']):
                            mlb_idx = utils.get_overall_idx(
                                projection, {'URW': urw, 'URN': urn, 'UB': ub,
                                             'UE': ue, 'UG': ug})
                            newout = utils.AddOutPort(s, mlb_width,
                                                      "outputs_to_mlb_" +
                                                      str(mlb_idx))
                            utils.AddInPort(s, mlb_width,
                                            "inputs_from_mlb_" +
                                            str(mlb_idx))

                            # Connect adjacent inputs
                            if (urw > 0):
                                mlb_idx_prev = utils.get_overall_idx(
                                    projection, {'URW': urw - 1, 'URN': urn,
                                                 'UB': ub, 'UE': ue, 'UG': ug})
                                prev_input = getattr(s, "inputs_from_mlb_" +
                                                     str(mlb_idx_prev))
                                connect(newout[0:mlb_width_used],
                                        prev_input[0:mlb_width_used])
                            else:
                                # Figure out which input to connect it to
                                stream_idx = utils.get_overall_idx(projection,
                                                                   {'URN': urn,
                                                                    'UB': ub,
                                                                    'UG': ug})
                                input_bus_idx = math.floor(stream_idx /
                                                           streams_per_buffer)
                                input_bus = getattr(s, "inputs_from_buffer_" +
                                                    str(input_bus_idx))
                                section_idx = stream_idx % streams_per_buffer
                                input_bus_start = section_idx * mlb_width_used
                                input_bus_end = (section_idx + 1) * \
                                    mlb_width_used
                                connect(newout[0:mlb_width_used],
                                        input_bus[input_bus_start:
                                                  input_bus_end])

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
    def construct(s, af_width=1, mlb_width=1, mlb_width_used=1, num_afs=1,
                  num_mlbs=1, projection={}):
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
        utils.add_n_outputs(s, num_afs, af_width, "outputs_to_afs_")

        # Add input and output ports from each MLB
        for ug in range(projection['UG']['value']):
            for ue in range(projection['UE']['value']):
                for ub in range(projection['UB']['value']):
                    for urn in range(projection['URN']['value']):
                        for urw in range(projection['URW']['value']):
                            mlb_idx = utils.get_overall_idx(projection,
                                                            {'URW': urw,
                                                             'URN': urn,
                                                             'UB': ub,
                                                             'UE': ue,
                                                             'UG': ug})
                            newout = utils.AddOutPort(s, mlb_width,
                                                      "outputs_to_mlb_" +
                                                      str(mlb_idx))
                            newin = utils.AddInPort(s, mlb_width,
                                                    "inputs_from_mlb_" +
                                                    str(mlb_idx))

                            # Connect only the last output of the chain out
                            if ((urw == projection['URW']['value'] - 1) and
                                    (urn == projection['URN']['value'] - 1)):
                                # Figure out which output to connect it to
                                stream_idx = utils.get_overall_idx(projection,
                                                                   {'UB': ub,
                                                                    'UE': ue,
                                                                    'UG': ug})
                                output_bus_idx = stream_idx * acts_per_stream
                                for out_part in range(acts_per_stream):
                                    output_bus = getattr(s, "outputs_to_afs_" +
                                                         str(output_bus_idx +
                                                             out_part))
                                    output_bus_start = out_part * af_width
                                    output_bus_end = (out_part + 1) * af_width
                                    connect(output_bus,
                                            newin[output_bus_start:
                                                  output_bus_end])
                            if (urw > 0) or (urn > 0):
                                # Connect the other blocks in the chain
                                if (urw > 0):
                                    mlb_idx_prev = utils.get_overall_idx(
                                        projection,
                                        {'URW': urw - 1, 'URN': urn, 'UB': ub,
                                         'UE': ue, 'UG': ug})
                                else:
                                    mlb_idx_prev = utils.get_overall_idx(
                                        projection,
                                        {'URW': projection['URW']['value'] - 1,
                                         'URN': urn - 1, 'UB': ub, 'UE': ue,
                                         'UG': ug})
                                prev_input = getattr(s, "inputs_from_mlb_" +
                                                     str(mlb_idx_prev))
                                connect(newout[0:mlb_width_used],
                                        prev_input[0:mlb_width_used])
                            else:
                                newout[0:mlb_width_used] //= 0

        # Tie disconnected MLBs to 0
        for i in range(num_mlbs):
            if ("outputs_to_mlb_" + str(i) not in s.__dict__.keys()):
                newout = OutPort(mlb_width)
                setattr(s, "outputs_to_mlb_" + str(i), newout)
                newout //= 0
            newin = utils.AddInPort(s, mlb_width, "inputs_from_mlb_" +
                                    str(i))
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
                  proj_spec={}):
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
        print("{:=^60}".format(" Constructing Datapath with MLB block " +
                               str(mlb_spec.get('block_name', "unnamed") +
                                   " ")))
        MAC_datatypes = ['W', 'I', 'O']
        buffer_specs = {'W': wb_spec, 'I': ib_spec, 'O': ob_spec}

        # Calculate required MLB interface widths and print information
        inner_proj = proj_spec['inner_projection']
        MAC_count = utils.get_mlb_count(inner_proj)
        inner_bus_counts = {dtype: utils.get_proj_stream_count(inner_proj,
                                                               dtype)
                            for dtype in MAC_datatypes}
        inner_data_widths = {dtype: proj_spec['stream_info'][dtype]
                             for dtype in MAC_datatypes}
        inner_bus_widths = {dtype: inner_bus_counts[dtype] *
                            inner_data_widths[dtype]
                            for dtype in MAC_datatypes}
        print(utils.print_table("ML Block Details, Projection " +
                                proj_spec.get("name", "unnamed"),
                                [["Num MACs", MAC_count,
                                  "(MACs within each MLB)"],
                                 ["bandwidth by type", inner_bus_counts,
                                  "(number of in and output values per MLB)"],
                                 ["data widths by type", inner_data_widths,
                                  "(bit-width of each value)"],
                                 ["total bus width, by type", inner_bus_widths,
                                  "(bit-width of MLB interface)"]]) + "\n")

        # Check that this configuration is supported by the hardware model
        assert MAC_count <= mlb_spec['MAC_info']['num_units']
        for dtype in MAC_datatypes:
            assert inner_bus_widths[dtype] <= \
                utils.get_sum_datatype_width(mlb_spec, dtype)
            assert inner_data_widths[dtype] <= \
                mlb_spec['MAC_info']['data_widths'][dtype]

        # Calculate required number of MLBs, IO streams, activations
        outer_proj = proj_spec['outer_projection']
        MLB_count = utils.get_mlb_count(outer_proj)
        outer_bus_counts = {dtype: utils.get_proj_stream_count(outer_proj,
                                                               dtype)
                            for dtype in MAC_datatypes}
        outer_bus_widths = {dtype: outer_bus_counts[dtype] *
                            inner_bus_widths[dtype]
                            for dtype in MAC_datatypes}
        total_bus_counts = {dtype: outer_bus_counts[dtype] *
                            inner_bus_counts[dtype]
                            for dtype in MAC_datatypes}
        buffer_counts = {dtype: utils.get_num_buffers_reqd(buffer_specs[dtype],
                         outer_bus_counts[dtype], inner_bus_widths[dtype])
                         for dtype in ['I', 'W']}
        buffer_counts['O'] = utils.get_num_buffers_reqd(buffer_specs['O'],
                                                        outer_bus_counts['O'] *
                                                        inner_bus_counts['O'],
                                                        inner_data_widths['I'])
        print(utils.print_table("Dataflow Details, Projection " +
                                proj_spec.get("name", "unnamed"),
                                [["Num MLBs", MAC_count,
                                  "(Number of MLBs required for projection)"],
                                 ["total data widths by type",
                                  outer_bus_widths,
                                  "(total data width from buffers)"],
                                 ["bandwidth, by type", total_bus_counts,
                                  "(total # values from buffers)"],
                                 ["# buffers, by type", buffer_counts]]
                                ) + "\n")

        # Instantiate MLBs, buffers
        s.mlb_modules = HWB_Wrapper(mlb_spec, MLB_count,
                                    projection=inner_proj)
        s.weight_modules = HWB_Wrapper(buffer_specs['W'],
                                       buffer_counts['W'])
        s.input_act_modules = HWB_Wrapper(buffer_specs['I'],
                                          buffer_counts['I'])
        s.output_act_modules = HWB_Wrapper(buffer_specs['O'],
                                           buffer_counts['O'],
                                           name='_v2')
        s.activation_function_modules = ActivationWrapper(
            count=total_bus_counts['O'],
            function=utils.get_activation_function_name(proj_spec),
            input_width=inner_data_widths['O'],
            output_width=inner_data_widths['I'],
            registered=False)

        # Instantiate interconnects
        s.weight_interconnect = WeightInterconnect(
            buffer_width=utils.get_sum_datatype_width(buffer_specs['W'],
                                                      'DATAOUT'),
            mlb_width=utils.get_sum_datatype_width(mlb_spec, 'W', ["in"]),
            mlb_width_used=inner_bus_widths['W'],
            num_buffers=buffer_counts['W'],
            num_mlbs=MLB_count,
            projection=outer_proj)
        s.input_interconnect = InputInterconnect(
            buffer_width=utils.get_sum_datatype_width(buffer_specs['I'],
                                                      'DATAOUT'),
            mlb_width=utils.get_sum_datatype_width(mlb_spec, 'I', ["in"]),
            mlb_width_used=inner_bus_widths['I'],
            num_buffers=buffer_counts['I'],
            num_mlbs=MLB_count,
            projection=outer_proj)
        s.output_ps_interconnect = OutputPSInterconnect(
            af_width=inner_data_widths['O'],
            mlb_width=utils.get_sum_datatype_width(mlb_spec, 'O', ["in"]),
            mlb_width_used=inner_bus_widths['O'],
            num_afs=total_bus_counts['O'],
            num_mlbs=MLB_count,
            projection=outer_proj)
        s.output_interconnect = MergeBusses(in_width=inner_data_widths['I'],
                                            num_ins=total_bus_counts['O'],
                                            out_width=utils.
                                            get_sum_datatype_width(
                                                buffer_specs['O'], 'DATAIN'),
                                            num_outs=buffer_counts['O'])

        # Connect weight interconnect
        connected_ins = []
        for portname in utils.get_ports_of_type(mlb_spec, 'W', ["out"]):
            connected_ins += utils.connect_ports_by_name(s.mlb_modules,
                                                         portname["name"],
                                                         s.weight_interconnect,
                                                         "inputs_from_mlb")
        for portname in utils.get_ports_of_type(mlb_spec, 'W', ["in"]):
            connected_ins += utils.connect_ports_by_name(
                s.weight_interconnect, "outputs_to_mlb", s.mlb_modules,
                portname["name"])
        for portname in utils.get_ports_of_type(buffer_specs['W'], 'DATAOUT',
                                                ["out"]):
            connected_ins += utils.connect_ports_by_name(s.weight_modules,
                                                         portname["name"],
                                                         s.weight_interconnect,
                                                         "inputs_from_buffer")

        # Connect input interconnect
        for portname in utils.get_ports_of_type(mlb_spec, 'I', ["out"]):
            connected_ins += utils.connect_ports_by_name(s.mlb_modules,
                                                         portname["name"],
                                                         s.input_interconnect,
                                                         "inputs_from_mlb")
        for portname in utils.get_ports_of_type(mlb_spec, 'I', ["in"]):
            connected_ins += utils.connect_ports_by_name(s.input_interconnect,
                                                         "outputs_to_mlb",
                                                         s.mlb_modules,
                                                         portname["name"])
        for portname in utils.get_ports_of_type(buffer_specs['I'], 'DATAOUT',
                                                ["out"]):
            connected_ins += utils.connect_ports_by_name(s.input_act_modules,
                                                         portname["name"],
                                                         s.input_interconnect,
                                                         "inputs_from_buffer")

        # Connect partial sum interconnect
        for portname in utils.get_ports_of_type(mlb_spec, 'O', ["out"]):
            connected_ins += utils.connect_ports_by_name(s.mlb_modules,
                portname["name"], s.output_ps_interconnect, "inputs_from_mlb")
        for portname in utils.get_ports_of_type(mlb_spec, 'O', ["in"]):
            connected_ins += utils.connect_ports_by_name(
                s.output_ps_interconnect, "outputs_to_mlb",
                s.mlb_modules, portname["name"])
        connected_ins += utils.connect_ports_by_name(
            s.output_ps_interconnect, "outputs_to_afs",
            s.activation_function_modules, "activation_function_in")

        # Connect output activations
        connected_ins += utils.connect_ports_by_name(
            s.activation_function_modules, "activation_function_out",
            s.output_interconnect, "input")
        for portname in utils.get_ports_of_type(buffer_specs['O'], 'DATAIN',
                                                ["in"]):
            connected_ins += utils.connect_ports_by_name(
                s.output_interconnect, "output", s.output_act_modules,
                portname["name"])

        # Connect output buffers to top
        for port in s.output_act_modules.get_output_value_ports():
            for dout in utils.get_ports_of_type(buffer_specs['O'], 'DATAOUT',
                                                ["out"]):
                if dout["name"] in port._dsl.my_name:
                    utils.connect_out_to_top(s, port, port._dsl.my_name)
        # Connect all inputs not otherwise connected to top
        for inst in [s.activation_function_modules, s.mlb_modules,
                     s.mlb_modules, s.output_act_modules, s.input_act_modules,
                     s.weight_interconnect, s.output_ps_interconnect,
                     s.input_interconnect, s.weight_modules]:
            for port in (inst.get_input_value_ports()):
                if (port._dsl.my_name not in s.__dict__.keys()) and \
                   (port not in connected_ins):
                    utils.connect_in_to_top(s, port, inst._dsl.my_name + "_" +
                                            port._dsl.my_name+"_top")

        # print(s.__dict__)
        # TODAY
        # Get the full simulation working for toy
        #    (that means doing the MLB sim model)
        # better memory interfaces
        # Output stationary option (update W, I, o interfaces)

        # THURS
        # Think aboud preloading the memories ... how?
        
        # FRIDAY
        # Method to switch between interconnects
        # Different types of blocks

        # Later...
        # Method to map hw blocks to physical locations and to match
        # up different projections
        # Method to decide which buffers to write to when (a table?)

        # Look into modelling MLB for simulations
        # Run whole simulations here in python...
        #    Make sure whole thing is runnable
        #    Write golden comparison
