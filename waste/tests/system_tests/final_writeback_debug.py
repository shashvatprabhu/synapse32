#!/usr/bin/env python3
"""
Updated final instruction debug to track writeback stage data flow
Now includes mem_data_direct to verify the fix
"""

import cocotb
from cocotb.triggers import RisingEdge, ClockCycles
from cocotb.clock import Clock
from pathlib import Path

def create_memory_debug_hex():
    """Create test program to debug memory operations"""
    curr_dir = Path.cwd()
    build_dir = curr_dir / "build"
    build_dir.mkdir(exist_ok=True)
    
    hex_file = build_dir / "memory_debug.hex"
    
    # Very simple test program
    instructions = [
        0x10000237,  # lui x4, 0x10000     # x4 = 0x10000000 (data base)
        0x00100093,  # addi x1, x0, 1      # x1 = 1
        0x00000113,  # addi x2, x0, 0      # x2 = 0 (for debugging)
        0x00122023,  # sw x1, 0(x4)        # Store 1 to memory[0x10000000]
        0x00022283,  # lw x5, 0(x4)        # Load from memory[0x10000000] -> x5
        0x00528313,  # addi x6, x5, 5      # x6 = x5 + 5 (should be 6)
        0x00000013,  # nop
        0x00000013,  # nop
    ]
    
    with open(hex_file, 'w') as f:
        f.write("@00000000\n")
        
        # Write as hex
        for i in range(0, len(instructions), 4):
            line = " ".join(f"{instructions[j]:08x}" for j in range(i, min(i+4, len(instructions))))
            f.write(f"{line}\n")
        
        # Add padding
        for _ in range(32):
            f.write("00000013 00000013 00000013 00000013\n")
    
    return str(hex_file.absolute())

@cocotb.test()
async def test_final_writeback_debug(dut):
    """Final debug to identify where memory data gets lost - now with mem_data_direct"""
    print("=== FINAL WRITEBACK DEBUG WITH mem_data_direct ===")
    
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Reset
    dut.rst.value = 1
    dut.software_interrupt.value = 0
    dut.external_interrupt.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst.value = 0
    
    # Let cache warm up
    await ClockCycles(dut.clk, 25)
    
    print("=== TRACKING MEMORY DATA PATH WITH NEW FIX ===")
    
    for cycle in range(25):
        await RisingEdge(dut.clk)
        
        # Initialize all variables with defaults
        pc = 0
        instr_fetched = 0
        instr_id_decoded = 0
        id_ex_instr_id = 0
        ex_mem_instr_id = 0
        mem_wb_instr_id = 0
        mem_read_data = 0
        cpu_input_data = 0
        rf_wr_en = 0
        rf_rd_addr = 0
        rf_rd_value = 0
        wb_mem_data_in = -999
        wb_mem_data_direct = -999  # NEW: Track direct memory input
        wb_is_load = -999
        wb_rd_value_out = -999
        wb_instr_id = -999
        
        try:
            pc = int(dut.pc_debug.value)
            instr_fetched = int(dut.cpu_inst.if_id_inst0.instruction_out.value)
            instr_id_decoded = int(dut.cpu_inst.decoder_inst0.instr_id.value)
            id_ex_instr_id = int(dut.cpu_inst.id_ex_inst0.instr_id_out.value)
            ex_mem_instr_id = int(dut.cpu_inst.ex_mem_inst0.instr_id_out.value)
            mem_wb_instr_id = int(dut.cpu_inst.mem_wb_inst0.instr_id_out.value)
            mem_read_data = int(getattr(dut, 'mem_read_data', type('obj', (object,), {'value': 0})).value)
            cpu_input_data = int(getattr(dut.cpu_inst, 'module_read_data_in', type('obj', (object,), {'value': 0})).value)
            rf_wr_en = int(dut.cpu_inst.rf_inst0_wr_en.value)
            rf_rd_addr = int(dut.cpu_inst.rf_inst0_rd_in.value)
            rf_rd_value = int(dut.cpu_inst.rf_inst0_rd_value_in.value)
        except:
            pass
        
        # Try to get writeback signals individually
        try:
            wb_mem_data_in = int(dut.cpu_inst.wb_inst0.mem_data_in.value)
        except:
            try:
                wb_mem_data_in = int(dut.cpu_inst.writeback_inst.mem_data_in.value)
            except:
                wb_mem_data_in = -999
        
        # NEW: Try to get direct memory data
        try:
            wb_mem_data_direct = int(dut.cpu_inst.wb_inst0.mem_data_direct.value)
        except:
            try:
                wb_mem_data_direct = int(dut.cpu_inst.writeback_inst.mem_data_direct.value)
            except:
                wb_mem_data_direct = -999
        
        try:
            wb_is_load = int(dut.cpu_inst.wb_inst0.is_load_instr.value)
        except:
            try:
                wb_is_load = int(dut.cpu_inst.writeback_inst.is_load_instr.value)
            except:
                wb_is_load = -999
        
        try:
            wb_rd_value_out = int(dut.cpu_inst.wb_inst0.rd_value_out.value)
        except:
            try:
                wb_rd_value_out = int(dut.cpu_inst.writeback_inst.rd_value_out.value)
            except:
                wb_rd_value_out = -999
        
        try:
            wb_instr_id = int(dut.cpu_inst.wb_inst0.instr_id_in.value)
        except:
            try:
                wb_instr_id = int(dut.cpu_inst.writeback_inst.instr_id_in.value)
            except:
                wb_instr_id = -999
        
        # Show only critical cycles
        show_cycle = (instr_fetched == 0x00022283 or
                      instr_id_decoded == 22 or
                      id_ex_instr_id == 22 or
                      ex_mem_instr_id == 22 or
                      mem_wb_instr_id == 22 or
                      (rf_wr_en and rf_rd_addr == 5) or
                      cycle < 5)  # Always show first few cycles
        
        if show_cycle:
            print(f"\nCycle {cycle}: PC=0x{pc:08x}")
            print(f"  PIPELINE: fetched=0x{instr_fetched:08x} decoded_id={instr_id_decoded}")
            print(f"            ID_EX={id_ex_instr_id} EX_MEM={ex_mem_instr_id} MEM_WB={mem_wb_instr_id}")
            print(f"  MEMORY:   mem_read_data={mem_read_data} cpu_input_data={cpu_input_data}")
            print(f"  WB_STAGE: mem_data_in={wb_mem_data_in} mem_data_direct={wb_mem_data_direct} is_load={wb_is_load}")
            print(f"            rd_value_out={wb_rd_value_out} instr_id={wb_instr_id}")
            print(f"  REG_FILE: wr_en={rf_wr_en} addr={rf_rd_addr} value={rf_rd_value}")
            
            if instr_fetched == 0x00022283:
                print(f"    *** LW INSTRUCTION FETCHED ***")
            if mem_wb_instr_id == 22:
                print(f"    *** LW IN WRITEBACK STAGE ***")
                if wb_mem_data_direct == 1:
                    print(f"    *** SUCCESS: mem_data_direct has correct value! ***")
                elif wb_mem_data_direct == 0:
                    print(f"    *** ISSUE: mem_data_direct still 0 ***")
            if rf_wr_en and rf_rd_addr == 5:
                print(f"    *** WRITING TO x5 = {rf_rd_value} ***")
                if rf_rd_value == 1:
                    print(f"    *** SUCCESS: Writing correct value to x5! ***")
                else:
                    print(f"    *** ISSUE: Still writing wrong value to x5 ***")
        
        # Stop after completing the test
        if cycle > 20 and pc > 0x20:
            break
    
    print("\n=== FINAL DEBUG COMPLETE ===")
    print("Key things to check:")
    print("1. When LW is in WB stage (MEM_WB=22), does mem_data_direct=1?")
    print("2. Does rd_value_out become 1 instead of 0?")
    print("3. Does REG_FILE write value=1 to addr=5?")

def runCocotbTests():
    """Run final writeback debug test"""
    from cocotb_test.simulator import run
    import shutil
    import os
    
    hex_file = create_memory_debug_hex()
    print(f"Created memory debug hex: {hex_file}")
    
    # Setup build
    curr_dir = os.getcwd()
    root_dir = curr_dir
    while not os.path.exists(os.path.join(root_dir, "rtl")):
        root_dir = os.path.dirname(root_dir)
    
    sources = []
    rtl_dir = os.path.join(root_dir, "rtl")
    for root, _, files in os.walk(rtl_dir):
        for file in files:
            if file.endswith(".v"):
                sources.append(os.path.join(root, file))
    
    incl_dir = os.path.join(rtl_dir, "include")
    sim_build_dir = os.path.join(curr_dir, "sim_build", "final_debug_fixed")
    if os.path.exists(sim_build_dir):
        shutil.rmtree(sim_build_dir)
    
    run(
        verilog_sources=sources,
        toplevel="top",
        module="final_writeback_debug",
        testcase="test_final_writeback_debug",
        includes=[str(incl_dir)],
        simulator="verilator",
        timescale="1ns/1ps",
        defines=[f"INSTR_HEX_FILE=\"{hex_file}\""],
        sim_build=sim_build_dir,
        force_compile=True,
    )

if __name__ == "__main__":
    runCocotbTests()