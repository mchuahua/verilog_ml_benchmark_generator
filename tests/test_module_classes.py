#!/usr/bin/env python

"""Tests for `verilog_ml_benchmark_generator` pyMTL Components."""
import numpy
import pytest
import random
import math
import os
import sys
from pymtl3 import *

from click.testing import CliRunner

from verilog_ml_benchmark_generator import utils
from verilog_ml_benchmark_generator import module_classes
from verilog_ml_benchmark_generator import cli

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from test_helpers import *


def test_RELU():
    """Test Component class RELU"""
    test_vecs = [
        {"ins":[4,4, False], "outs":[[7,7],[8,0]]},
        {"ins":[4,2, False], "outs":[[3,3],[5,1],[9,0]]},
        {"ins":[3,5, False], "outs":[[3,Bits5(3)],[4,Bits5(0)]]},
        {"ins":[4,4, True], "outs":[[7,7],[8,0]]},
        {"ins":[4,2, True], "outs":[[3,3],[5,1],[9,0]]},
        {"ins":[3,5, True], "outs":[[3,Bits5(3)],[4,Bits5(0)]]},
    ]
    for testvec in test_vecs:
        testinst = module_classes.RELU(testvec["ins"][0],
                                       testvec["ins"][1],
                                       testvec["ins"][2])
        testinst.elaborate()
        testinst.apply(DefaultPassGroup()) 
        for pair in testvec["outs"]:
            testinst.sim_reset()
            testinst.activation_function_in @= pair[0]
            testinst.sim_tick()
            assert testinst.activation_function_out == pair[1]
    
def test_ActivationWrapper():
    """Test Component class RELU"""
    test_vecs = [
        {"ins":[4,4, False], "outs":[[7,7],[8,0]]},
        {"ins":[4,2, False], "outs":[[3,3],[5,1],[9,0]]},
        {"ins":[3,5, False], "outs":[[3,Bits5(3)],[4,Bits5(0)]]},
        {"ins":[4,4, True], "outs":[[7,7],[8,0]]},
        {"ins":[4,2, True], "outs":[[3,3],[5,1],[9,0]]},
        {"ins":[3,5, True], "outs":[[3,Bits5(3)],[4,Bits5(0)]]},
    ]
    for testvec in test_vecs:
        testinst = module_classes.ActivationWrapper(len(testvec["outs"]), "RELU",
                                       testvec["ins"][0],
                                       testvec["ins"][1],
                                       testvec["ins"][2])
        testinst.elaborate()
        testinst.apply(DefaultPassGroup())
        for pairidx in range(len(testvec["outs"])):
            input_bus = getattr(testinst, "activation_function_in_"+ \
                                str(pairidx))
            input_bus @= testvec["outs"][pairidx][0]
        testinst.sim_tick()
        for pairidx in range(len(testvec["outs"])):
            output_bus = getattr(testinst, "activation_function_out_"+ \
                                 str(pairidx))
            assert output_bus == testvec["outs"][pairidx][1]

    testinst = module_classes.ActivationWrapper(2, "notrelu",
                                                test_vecs[0]["ins"][0],
                                                test_vecs[0]["ins"][1],
                                                test_vecs[0]["ins"][2])
                                                
    with pytest.raises(AssertionError):
        testinst.elaborate()
    

def test_HWB():
    """Test Component class HWB"""
    spec = {
        "block_name": "test_block",
        "ports": [{"name":"A", "width":5, "direction": "in", "type":"C"},
                  {"name":"B", "width":5, "direction": "out", "type":"C"},
                  {"name":"C", "width":5, "direction": "in", "type":"ADDRESS"},
                  {"name":"D", "width":5, "direction": "out", "type":"ADDRESS"},
                  {"name":"E", "width":5, "direction": "in", "type":"OTHER"},
                  {"name":"F", "width":5, "direction": "out", "type":"OTHER"},
                  ]
    }
    testinst = module_classes.HWB_Sim(spec)
    testinst.elaborate()
    
    spec = {
        "block_name": "test_block",
        "ports": [{"name":"A", "width":5, "direction": "in", "type":"C"},
                  {"name":"B", "width":5, "direction": "out", "type":"C"},
                  {"name":"C", "width":5, "direction": "in", "type":"W"},
                  {"name":"D", "width":5, "direction": "out", "type":"W"},
                  {"name":"E", "width":5, "direction": "in", "type":"I"},
                  {"name":"F", "width":5, "direction": "out", "type":"I"},
                  {"name":"G", "width":5, "direction": "out", "type":"I"},
                  ],
        "MAC_info": {"num_units":4}
    }
    # Basic case
    proj_spec = {'URN':{'value':1},'URW':{'value':1},
                  'UB':{'value':1},'UE':{'value':1},
                  'UG':{'value':1}}
    testinst = module_classes.HWB_Sim(spec, proj_spec)
    testinst.elaborate()
        
def test_HWB_Wrapper():
    """Test Component class HWB Wrapper"""
    spec = {
        "block_name": "test_block",
        "ports": [{"name":"A", "width":5, "direction": "in", "type":"C"},
                  {"name":"B", "width":5, "direction": "out", "type":"C"},
                  {"name":"C", "width":5, "direction": "in", "type":"ADDRESS"},
                  {"name":"D", "width":5, "direction": "out", "type":"ADDRESS"},
                  {"name":"E", "width":5, "direction": "in", "type":"OTHER"},
                  {"name":"F", "width":5, "direction": "out", "type":"OTHER"},
                  ]
    }
    testinst = module_classes.HWB_Wrapper(spec,2)
    testinst.elaborate()
    testinst.apply(DefaultPassGroup()) 
    testinst.A @= 8
    testinst.C @= 9
    testinst.E_0 @= 10
    testinst.E_1 @= 11
    testinst.sim_tick()
    assert testinst.test_block_inst_0.A == 8
    assert testinst.test_block_inst_1.A == 8
    assert testinst.test_block_inst_0.C == 9
    assert testinst.test_block_inst_1.C == 9
    assert testinst.test_block_inst_0.E == 10
    assert testinst.test_block_inst_1.E == 11
    assert testinst.B_0 == 0
    assert testinst.B_1 == 0
    assert testinst.D_0 == 0
    assert testinst.D_1 == 0
    assert testinst.F_0 == 0
    assert testinst.F_1 == 0
        
def test_MergeBusses():
    """Test Component class MergeBusses"""
    test_vecs = [
        {"ins":[2,4,4,4,1], "outs":[[0,1,2,3],[0,1,2,3]]},
        {"ins":[2,4,5,2,2], "outs":[[0,1,2,3],[4,14]]},
        {"ins":[3,8,23,4,6], "outs":[[0,1,2,3,4,5,6,7],[181896,62,0,0]]},
        {"ins":[2,4,4,4], "outs":[[0,1,2,3],[4,14,0,0]]},
        {"ins":[2,4,5,2], "outs":[[0,1,2,3],[4,14]]},
        {"ins":[3,8,23,4], "outs":[[0,1,2,3,4,5,6,7],[1754760,7,0,0]]},
    ]
    for testvec in test_vecs:
        if len(testvec["ins"]) == 5:
            testinst = module_classes.MergeBusses(testvec["ins"][0],
                        testvec["ins"][1], testvec["ins"][2], testvec["ins"][3],
                        testvec["ins"][4])
        else:
            testinst = module_classes.MergeBusses(testvec["ins"][0],
                        testvec["ins"][1], testvec["ins"][2], testvec["ins"][3])
        testinst.elaborate()
        testinst.apply(DefaultPassGroup())
        for i in range(len(testvec["outs"][0])):
            in_bus = getattr(testinst, "input_"+str(i))
            in_bus @= testvec["outs"][0][i]
        testinst.sim_tick()
        for i in range(len(testvec["outs"][1])):
            out_bus = getattr(testinst, "output_"+str(i))
            assert out_bus == testvec["outs"][1][i]
      
    illegal_test_vecs = [
        {"ins":[2,4,5,8,3]}, # ins per out not possible 
        {"ins":[2,8,16,3,2]}, # not enough outputs 
        {"ins":[2,8,6,2]} # no possible solution 
    ]  
    for testvec in illegal_test_vecs:
        if len(testvec["ins"]) == 5:
            testinst = module_classes.MergeBusses(testvec["ins"][0],
                        testvec["ins"][1], testvec["ins"][2], testvec["ins"][3],
                        testvec["ins"][4])
        else:
            testinst = module_classes.MergeBusses(testvec["ins"][0],
                        testvec["ins"][1], testvec["ins"][2], testvec["ins"][3])
        with pytest.raises(AssertionError):
            testinst.elaborate()
        
def test_WeightInterconnect():
    """Test Component class WeightInterconnect"""
    test_vecs = [ # bufferwidth, mlbwidth, mlbwidthused, num_buffers, num_mlbs, proj.
        {"ins":[8,8,3,4,10,{'URN':{'value':2},'URW':{'value':1},
                          'UB':{'value':2},'UE':{'value':2},
                          'UG':{'value':1}}],  
         "outs":[[8,26,44,62],[0,1,2,3,0,1,2,3,0,0]]},
        {"ins":[8,8,3,4,15,{'URN':{'value':1},'URW':{'value':2},
                          'UB':{'value':3},'UE':{'value':1},
                          'UG':{'value':2}}],  
         "outs":[[8,26,44,62],[0,1,0,1,0,1,2,3,2,3,2,3,0,0,0]]},
    ]
    for testvec in test_vecs:
        testinst = module_classes.WeightInterconnect(testvec["ins"][0],
                    testvec["ins"][1], testvec["ins"][2], testvec["ins"][3],
                    testvec["ins"][4], testvec["ins"][5])
        testinst.elaborate()
        testinst.apply(DefaultPassGroup())
        for i in range(len(testvec["outs"][0])):
            in_bus = getattr(testinst, "inputs_from_buffer_"+str(i))
            in_bus @= testvec["outs"][0][i]
        testinst.sim_tick()
        for i in range(len(testvec["outs"][1])):
            out_bus = getattr(testinst, "outputs_to_mlb_"+str(i))
            assert out_bus == testvec["outs"][1][i]
            
    illegal_test_vecs = [
        {"ins":[8,2,3,4,10,{'URN':{'value':2},'URW':{'value':1},
                          'UB':{'value':2},'UE':{'value':2},
                          'UG':{'value':1}}]}, # mlb bitwidths dont make sense
        {"ins":[8,8,3,400,15,{'URN':{'value':1},'URW':{'value':2},
                          'UB':{'value':3},'UE':{'value':10},
                          'UG':{'value':2}}]}, # not enough mlbs
        {"ins":[8,8,3,4,1000,{'URN':{'value':1},'URW':{'value':2},
                          'UB':{'value':3},'UE':{'value':10},
                          'UG':{'value':2}}]}, # not enough buffers
        {"ins":[5,8,3,3,15,{'URN':{'value':1},'URW':{'value':2},
                          'UB':{'value':3},'UE':{'value':1},
                          'UG':{'value':2}}]}, # buffer not wide enough
    ] 
    for testvec in illegal_test_vecs:
        with pytest.raises(AssertionError):
            testinst = module_classes.WeightInterconnect(testvec["ins"][0],
                        testvec["ins"][1], testvec["ins"][2], testvec["ins"][3],
                        testvec["ins"][4], testvec["ins"][5])
            testinst.elaborate()
        
def test_InputInterconnect():
    """Test Component class InputInterconnect"""
    test_vecs = [ # bufferwidth, mlbwidth, mlbwidthused, num_buffers, num_mlbs, proj.
        {"ins":[8,8,3,2,10,{'URN':{'value':1},'URW':{'value':2},
                          'UB':{'value':4},'UE':{'value':1},
                          'UG':{'value':1}}],  
         "outs":[[62,26],[1,2,3,4,5,6,7,8,9,10],[6,1,7,3,2,5,3,7,0,0]]},
        {"ins":[8,8,3,2,10,{'URN':{'value':1},'URW':{'value':2},
                          'UB':{'value':2},'UE':{'value':2},
                          'UG':{'value':1}}],  
         "outs":[[62,26],[1,2,3,4,5,6,7,8,9,10],[6,1,6,3,7,5,7,7,0,0]]}
    ]
    for testvec in test_vecs:
        testinst = module_classes.InputInterconnect(testvec["ins"][0],
                    testvec["ins"][1], testvec["ins"][2], testvec["ins"][3],
                    testvec["ins"][4], testvec["ins"][5])
        testinst.elaborate()
        testinst.apply(DefaultPassGroup())
        for i in range(len(testvec["outs"][0])):
            in_bus = getattr(testinst, "inputs_from_buffer_"+str(i))
            in_bus @= testvec["outs"][0][i]
        for i in range(len(testvec["outs"][1])):
            in_bus = getattr(testinst, "inputs_from_mlb_"+str(i))
            in_bus @= testvec["outs"][1][i]
        testinst.sim_tick()
        for i in range(len(testvec["outs"][2])):
            out_bus = getattr(testinst, "outputs_to_mlb_"+str(i))
            assert out_bus == testvec["outs"][2][i]
        
def test_OutputPSInterconnect():
    """Test Component class InputInterconnect"""
    test_vecs = [ # afwidth, mlbwidth, mlbwidthused, num_afs, num_mlbs, proj.
        {"ins":[3,10,6,6,10,{'URN':{'value':2},'URW':{'value':2},
                          'UB':{'value':2},'UE':{'value':1},
                          'UG':{'value':1}}],  
         "outs":[[62,0,0,62,26,0,0,26,0,0],[6,7,2,3,0,0],[0,62,0,0,0,26,0,0,0,0]]}
    ]
    for testvec in test_vecs:
        testinst = module_classes.OutputPSInterconnect(testvec["ins"][0],
                    testvec["ins"][1], testvec["ins"][2], testvec["ins"][3],
                    testvec["ins"][4], testvec["ins"][5])
        testinst.elaborate()
        testinst.apply(DefaultPassGroup())
        for i in range(len(testvec["outs"][0])):
            in_bus = getattr(testinst, "inputs_from_mlb_"+str(i))
            in_bus @= testvec["outs"][0][i]
        testinst.sim_tick()
        for i in range(len(testvec["outs"][1])):
            out_bus = getattr(testinst, "outputs_to_afs_"+str(i))
            assert out_bus == Bits3(testvec["outs"][1][i])
        for i in range(len(testvec["outs"][2])):
            out_bus = getattr(testinst, "outputs_to_mlb_"+str(i))
            assert out_bus == testvec["outs"][2][i]

def test_Datapath():
    """Test Component class Datapath"""
    projection = {"name": "test",
                  "activation_function": "RELU",
                  "stream_info": {"W": 4,
                                  "I": 4,
                                  "O": 16},
                  "inner_projection": {'URN':{'value':2},'URW':{'value':3},
                                       'UB':{'value':2},'UE':{'value':1},
                                       'UG':{'value':2},
                                       'PRELOAD':[{'dtype':'W','bus_count':1}]},
                  "outer_projection": {'URN':{'value':2},'URW':{'value':1},
                                       'UB':{'value':2},'UE':{'value':1},
                                       'UG':{'value':2},
                                       'PRELOAD':[{'dtype':'W','bus_count':1}]}
                  }
    wb_spec = {
        "block_name": "ml_block_weights",
        "simulation_model": "Buffer",
        "ports": [
            {"name":"portaaddr", "width":4, "direction": "in", "type":"ADDRESS"},
            {"name":"portadatain", "width":16, "direction": "in", "type":"DATA"},
            {"name":"portadataout", "width":16, "direction": "out", "type":"DATA"},
            {"name":"portawe", "width":1, "direction": "in", "type":"WEN"},
         ]
    }
    ib_spec = {
        "block_name": "ml_block_inputs",
        "simulation_model": "Buffer",
        "ports": [
            {"name":"portaaddr", "width":3, "direction": "in", "type":"ADDRESS"},
            {"name":"portadatain", "width":32, "direction": "in", "type":"DATA"},
            {"name":"portadataout", "width":32, "direction": "out", "type":"DATA"},
            {"name":"portawe", "width":1, "direction": "in", "type":"WEN"},
        ]
    }
    ob_spec = {
        "block_name": "mlb_outs",
        "simulation_model": "Buffer",
        "ports": [
            {"name":"portaaddr", "width":3, "direction": "in", "type":"ADDRESS"},
            {"name":"portadatain", "width":16, "direction": "in", "type":"DATA"},
            {"name":"portadataout", "width":16, "direction": "out", "type":"DATA"},
            {"name":"portawe", "width":1, "direction": "in", "type":"WEN"},
        ]
    }
    mlb_spec = {
        "block_name": "ml_block",
        "simulation_model": "MLB",
        "MAC_info": { "num_units": 128, "data_widths": {"W":8, "I":8, "O": 32} },
        "ports": [
            {"name":"a_in", "width":32, "direction": "in", "type":"W"},
            {"name":"a_out", "width":32, "direction": "out", "type":"W"},
            {"name":"b_in", "width":64, "direction": "in", "type":"I"},
            {"name":"b_out", "width":64, "direction": "out", "type":"I"},
            {"name":"res_in", "width":128, "direction": "in", "type":"O"},
            {"name":"res_out", "width":128, "direction": "out", "type":"O"},
            {"name":"a_en", "width":1, "direction": "in", "type":"W_EN"},
            {"name":"b_en", "width":1, "direction": "in", "type":"I_EN"},
            {"name":"acc_en", "width":1, "direction": "in", "type":"ACC_EN"},
        ]
    }
    
    testinst = module_classes.Datapath(
        mlb_spec=mlb_spec,
        wb_spec=wb_spec,
        ib_spec=ib_spec,
        ob_spec=ob_spec,
        proj_spec=projection)

    testinst.elaborate()
    testinst.apply(DefaultPassGroup())
    testinst.sim_reset()
    
    # Calculate required buffers etc.
    mlb_count = utils.get_mlb_count(projection["outer_projection"])
    mac_count = utils.get_mlb_count(projection["inner_projection"])
    ibuf_len = 2**ib_spec["ports"][0]["width"]-1
    obuf_len = 2**ob_spec["ports"][0]["width"]-1
    wbuf_len = 2**wb_spec["ports"][0]["width"]-1
    print(obuf_len)
    # Load the weight buffer
    wbuf_count = 1
    weight_stream_count = utils.get_proj_stream_count(projection["outer_projection"], 'W')
    wvalues_per_stream = utils.get_proj_stream_count(projection["inner_projection"], 'W')
    wstream_bitwidth = wvalues_per_stream*projection["stream_info"]["W"]
    wstreams_per_buf = math.floor(wb_spec["ports"][1]["width"]/wstream_bitwidth)
    wbuf_count = math.ceil(weight_stream_count / wstreams_per_buf)
    wvalues_per_buf = min(wstreams_per_buf*wvalues_per_stream, wvalues_per_stream*weight_stream_count)
    
    wbuf = [[[random.randint(0,(2**projection["stream_info"]["W"])-1)
            for k in range(wvalues_per_buf)]    # values per word
            for i in range(wbuf_len)]           # words per buffer
            for j in range(wbuf_count)]         # buffer count
    load_buffers(testinst, "weight_modules_portawe_{}_top",
                "weight_modules_portaaddr_top", "weight_datain",
                wbuf, projection["stream_info"]["W"])
    check_buffers(testinst, testinst.weight_modules,
                "weight_modules_portaaddr_top", "portadataout_{}",
                wbuf, projection["stream_info"]["W"])
    
    # Calculate required buffers etc.
    iouter_stream_count = utils.get_proj_stream_count(projection["outer_projection"], 'I')
    iouter_stream_width = utils.get_proj_stream_count(projection["inner_projection"], 'I') * \
                         projection["stream_info"]["I"]
    ototal_stream_count = utils.get_proj_stream_count(projection["outer_projection"], 'O') * \
                          utils.get_proj_stream_count(projection["inner_projection"], 'O') 
    activation_width = projection["stream_info"]["I"]
    istreams_per_buf = math.floor(ib_spec["ports"][1]["width"]/iouter_stream_width)
    ivalues_per_buf = istreams_per_buf*utils.get_proj_stream_count(projection["inner_projection"], 'I')
    ostreams_per_buf = math.floor(ob_spec["ports"][1]["width"]/activation_width)
    ibuf_count = math.ceil(iouter_stream_count/istreams_per_buf)
    obuf_count = math.ceil(ototal_stream_count/ostreams_per_buf)
    
    # Load the input buffer
    # Several values per word, words per buffer, buffers...
    ibuf = [[[random.randint(0,(2**projection["stream_info"]["I"])-1)
             for k in range(ivalues_per_buf)]            # values per word
             for i in range(ibuf_len)]                   # words per buffer
             for j in range (ibuf_count)]                # buffers
    load_buffers(testinst, "input_act_modules_portawe_{}_top",
                "input_act_modules_portaaddr_top", "input_datain",
                ibuf, projection["stream_info"]["I"])
    check_buffers(testinst, testinst.input_act_modules,
                "input_act_modules_portaaddr_top", "portadataout_{}",
                ibuf, projection["stream_info"]["I"])
    
    # Now load the weights into the MLBs
    inner_ub = projection["inner_projection"]["UB"]["value"]
    outer_ub = projection["outer_projection"]["UB"]["value"]
    wbi_section_length = projection["inner_projection"]["UE"]["value"] * \
                        projection["inner_projection"]["URN"]["value"] * \
                        projection["inner_projection"]["URW"]["value"]
    wbo_section_length = projection["outer_projection"]["UE"]["value"] * \
                        projection["outer_projection"]["URN"]["value"] * \
                        projection["outer_projection"]["URW"]["value"] *\
                        projection["inner_projection"]["UG"]["value"] *  wbi_section_length
    starti = 0
    for ugo in range(projection["outer_projection"]["UG"]["value"]):
        for ubo in range(outer_ub):
            for ugi in range(projection["inner_projection"]["UG"]["value"] *
                             projection["outer_projection"]["URW"]["value"] *
                             projection["outer_projection"]["URN"]["value"] *
                             projection["outer_projection"]["UE"]["value"]):
                for ubi in range(inner_ub):
                    wbi_section_start = wbo_section_length*ugo + wbi_section_length*ugi
                    print(wbi_section_start)
                    starti = stream_mlb_values(testinst, wbi_section_length,
                              ["weight_modules_portaaddr_top"],
                              [0],
                              [wbuf_len],
                              ["mlb_modules_a_en_top"], starti=wbi_section_start)
            
    # Check they are right
    assert(check_mlb_chains_values(testinst, mlb_count, mac_count, 1, 1,
                            "ml_block_inst_{}", "weight_out_{}", wbuf,
                            projection["stream_info"]["W"],
                            wbo_section_length, outer_ub,
                                   wbi_section_length, inner_ub))
    print("OKKK")
    # Now stream the inputs, and check the outputs!
    stream_mlb_values(testinst, obuf_len,
                      ["input_act_modules_portaaddr_top", "output_act_modules_portaaddr_top"],
                      [0, -1],
                      [ibuf_len, obuf_len],
                      ["mlb_modules_b_en_top"] +
                      ["output_act_modules_portawe_{}_top".format(obi) for obi in range(obuf_count)])
      


    #print(testinst.output_act_modules.mlb_outs_inst_0.sim_model_inst0.data)
    
    obuf = [[[0
             for i in range(ostreams_per_buf)]
             for i in range(obuf_len)]
             for j in range (obuf_count)]
    obuf = get_expected_outputs(obuf, ostreams_per_buf,
                                wbuf,
                                ibuf, ivalues_per_buf,
                                projection)
    
    obuf_results = [[[[0]
             for i in range(ostreams_per_buf)]
             for i in range(obuf_len)]
             for j in range (obuf_count)]
    
    obuf_results = gather_stored_values(testinst, "output_act_modules_portaaddr_top", "dataout",
                         obuf_results, projection["stream_info"]["I"])
    
    print("EXPECTED: " + str(obuf))
    print("ACTUAL: " + str(obuf_results))
    print("W: " + str(wbuf))
    print("I: " + str(ibuf))
    for bufi in range(obuf_count):
        for olen in range(min(obuf_len,ibuf_len)-1): #(obuf_len-1): 
            assert obuf[bufi][olen] == obuf_results[bufi][olen]





    """
        print("TICK")
        print(testinst.mlb_modules.ml_block_inst_0.sim_model.mac_modules.sum_out_0)
        print(testinst.mlb_modules.ml_block_inst_0.sim_model.O_OUT)
        print(testinst.mlb_modules.ml_block_inst_0.res_out)
        print(testinst.mlb_modules.res_out_0)
        print(testinst.mlb_modules.res_in_1)
        print(testinst.mlb_modules.ml_block_inst_1.res_in)
        print(testinst.mlb_modules.ml_block_inst_1.sim_model.O_IN)
        print(testinst.mlb_modules.ml_block_inst_1.sim_model.mac_modules.sum_in_0)
        print(testinst.mlb_modules.ml_block_inst_1.sim_model.mac_modules.weight_out_0)
        print(testinst.mlb_modules.ml_block_inst_1.sim_model.mac_modules.input_out_0)
        print(testinst.mlb_modules.ml_block_inst_1.sim_model.mac_modules.sum_out_0)

    for i in range(obuf_len):
        prev_addr = i % wbuf_len
        testinst.input_act_modules_portaaddr_top @= prev_addr
        testinst.output_act_modules_portawe_0_top @= 1
        testinst.output_act_modules_portawe_1_top @= 1
        testinst.output_act_modules_portaaddr_top @= prev_addr-1
        testinst.mlb_modules_b_en_top @= 1
        testinst.sim_tick()
    #    for ibufi in range(ibuf_count): # Check the inputs are ok.
    #        #print("OUTER INPUT STREAM " + str(ibufi))
    #        # Check that input stream is right
    #        curr_out = getattr(testinst.input_act_modules, "portadataout_" + str(ibufi))
    #        assert (curr_out == merge_bus(ibuf[ibufi][prev_addr], projection["stream_info"]["W"]))   
    #    for ugbo in range(outer_ug*outer_ub): 
    #        #print("UGB_outer " + str(ugbo))
    #        # Check that input and weight and sum values of each MAC is right
    #        for ueo in range(outer_ue):
    #            print("\tUE_outer " + str(ueo))
    #            correct_sum = 0
    #            for urnw_o in range(outer_uw*outer_un):
    #                #print("\t\tURNW_outer " + str(urnw_o))
    #                mlb_inst = ugbo*outer_ue*outer_uw*outer_un + ueo*outer_uw*outer_un + urnw_o
    #                #print("\t\tMLB " + str(mlb_inst))
    #                mlb = getattr(testinst.mlb_modules, "ml_block_inst_" + str(mlb_inst))
    #                assert(mlb.sim_model.I_IN == merge_bus(ibuf[ugbo][prev_addr],8))
    #                for un in range(inner_un):
    #                    #print("\t\t\tUN: " + str(un))
    #                    for uw in range(inner_uw):
    #                        #print("\t\t\t\tUW: " + str(uw))
    #                        iv = getattr(mlb.sim_model.mac_modules, "input_out_" + str(un*3+uw))
    #                        ov = getattr(mlb.sim_model.mac_modules, "weight_out_" + str(un*3+uw))
    #                        sv = getattr(mlb.sim_model.mac_modules, "sum_out_" + str(un*3+uw))
    #                        mac_idx = mlb_inst*mac_count + un*3+uw
    #                        assert(ov == merge_bus(wbuf[(mac_count*mlb_count-mac_idx-1) % wbuf_len],8))
    #                        if (prev_addr-uw >= 0):
    #                            assert(iv == ibuf[ugbo][prev_addr-uw][un])
    #                            correct_sum += ibuf[ugbo][prev_addr-uw][un] * \
    #                                           merge_bus(wbuf[(mac_count*mlb_count-mac_idx-1)
    #                                                        % wbuf_len],8) 
    #                            assert(sv == correct_sum)
    #                        else:
    #                            assert(iv == 0)
    #                            assert(sv == correct_sum)
    #            last_mlb_idx = ugbo*outer_ue*outer_uw*outer_un + (ueo+1)*outer_uw*outer_un - 1
    #            chain_out = getattr(testinst.mlb_modules, "ml_block_inst_" + str(last_mlb_idx))
    #            assert(chain_out.res_out == correct_sum)
    #            #print("\tCHAIN_OUT "+ str(last_mlb_idx) +":" + str(chain_out.res_out))
    #            output_idx = ugbo*outer_ue*outer_uw*outer_un + ueo
    #            chain_out = getattr(testinst.output_ps_interconnect, "outputs_to_afs_" + str(output_idx))
    #            assert(chain_out == correct_sum)
    #            chain_out = getattr(testinst.output_interconnect, "input_" + str(output_idx))
    #            assert(int(chain_out) == int(correct_sum%(2**8)))
    #            buffer_idx = math.floor(output_idx / 2) 
    #            chain_out = getattr(testinst.output_interconnect, "output_" + str(buffer_idx))
    #            section_idx = output_idx%2
    #            section_start = 8*section_idx
    #            section_end = 8*(section_idx+1)
    #            section_part = int(int(chain_out)%(2**section_end))
    #            section_part = math.floor(section_part / (2**section_start))
    #            assert(section_part == int(correct_sum%(2**8)))
    #            chain_out = getattr(testinst.output_act_modules, "portadatain_" + str(buffer_idx))
    #            section_part = int(int(chain_out)%(2**section_end))
    #            section_part = math.floor(section_part / (2**section_start))
    #            assert(section_part == int(correct_sum%(2**8)))
    #            print("Input to buffer " + str(buffer_idx) + " is " + str(chain_out))"""
