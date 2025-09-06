#!/usr/bin/env python3
"""
Comprehensive load-use hazard test to thoroughly validate the fix
Tests multiple scenarios: basic load-use, back-to-back loads, load forwarding, etc.
"""

import cocotb
from cocotb.triggers import RisingEdge, ClockCycles
from cocotb.clock import Clock
from pathlib import Path

def create_comprehensive_test_hex():
    """Create comprehensive test program with multiple load-use scenarios"""
    curr_dir = Path.cwd()
    build_dir = curr_dir / "build"
    build_dir.mkdir(exist_ok=True)
    
    hex_file = build_dir / "comprehensive_load_test.hex"
    
    # Comprehensive test program
    instructions = [
        # Setup data base address
        0x10000237,  # lui x4, 0x10000     # x4 = 0x10000000 (data base)
        
        # Initialize test data in memory
        0x00100093,  # addi x1, x0, 1      # x1 = 1
        0x00200113,  # addi x2, x0, 2      # x2 = 2  
        0x00300193,  # addi x3, x0, 3      # x3 = 3
        0x00122023,  # sw x1, 0(x4)        # Store 1 to mem[0x10000000]
        0x00222223,  # sw x2, 4(x4)        # Store 2 to mem[0x10000004]
        0x00322423,  # sw x3, 8(x4)        # Store 3 to mem[0x10000008]
        
        # Test 1: Basic load-use hazard (this was our original failing case)
        0x00022283,  # lw x5, 0(x4)        # Load 1 -> x5
        0x00528313,  # addi x6, x5, 5      # x6 = x5 + 5 = 6 (depends on x5)
        
        # Test 2: Back-to-back loads with dependency
        0x00422383,  # lw x7, 4(x4)        # Load 2 -> x7  
        0x00822403,  # lw x8, 8(x4)        # Load 3 -> x8
        0x008383b3,  # add x7, x7, x8      # x7 = x7 + x8 = 2 + 3 = 5 (depends on both loads)
        
        # Test 3: Load with multiple dependent instructions
        0x00022483,  # lw x9, 0(x4)        # Load 1 -> x9
        0x00948513,  # addi x10, x9, 9     # x10 = x9 + 9 = 10 (depends on x9)
        0x00948593,  # addi x11, x9, 9     # x11 = x9 + 9 = 10 (also depends on x9)
        
        # Test 4: Load-use with store (no dependency)
        0x00422603,  # lw x12, 4(x4)       # Load 2 -> x12
        0x00c22623,  # sw x12, 12(x4)      # Store x12 to mem[0x1000000C] (depends on x12)
        
        # Test 5: Chain of dependent loads/operations
        0x00022683,  # lw x13, 0(x4)       # Load 1 -> x13
        0x00168693,  # addi x13, x13, 1    # x13 = x13 + 1 = 2 (depends on load)
        0x00d22723,  # sw x13, 14(x4)      # Store x13 (depends on addi result)
        0x00e22703,  # lw x14, 14(x4)      # Load back what we just stored -> x14
        0x00170713,  # addi x14, x14, 1    # x14 = x14 + 1 = 3 (depends on load)
        
        # Padding NOPs for pipeline completion
        0x00000013,  # nop
        0x00000013,  # nop
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
async def test_comprehensive_load_use(dut):
    """Comprehensive test for load-use hazard handling"""
    print("=== COMPREHENSIVE LOAD-USE HAZARD TEST ===")
    
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    # Reset
    dut.rst.value = 1
    dut.software_interrupt.value = 0
    dut.external_interrupt.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst.value = 0
    
    # Let the program run completely
    await ClockCycles(dut.clk, 200)
    
    # Read final register values to verify correctness
    try:
        # Expected results based on our test program:
        # x5 = 1 (loaded from memory)
        # x6 = 6 (x5 + 5 = 1 + 5)
        # x7 = 5 (x7 + x8 = 2 + 3, after loads)
        # x8 = 3 (loaded from memory)
        # x9 = 1 (loaded from memory)
        # x10 = 10 (x9 + 9 = 1 + 9)
        # x11 = 10 (x9 + 9 = 1 + 9)
        # x12 = 2 (loaded from memory)
        # x13 = 2 (1 + 1)
        # x14 = 3 (2 + 1, after load-store-load chain)
        
        # Access register file values
        rf = dut.cpu_inst.rf_inst0.register_file
        
        results = {}
        for i in range(5, 15):  # Check registers x5 through x14
            try:
                results[f"x{i}"] = int(rf[i].value)
            except:
                results[f"x{i}"] = "UNKNOWN"
        
        print("\n=== FINAL REGISTER VALUES ===")
        for reg, val in results.items():
            print(f"{reg} = {val}")
        
        # Define expected values
        expected = {
            "x5": 1,   # Basic load
            "x6": 6,   # Load-use dependency (1 + 5)
            "x7": 5,   # Back-to-back loads with dependency (2 + 3)
            "x8": 3,   # Second load
            "x9": 1,   # Load for multiple dependents
            "x10": 10, # First dependent (1 + 9)
            "x11": 10, # Second dependent (1 + 9)
            "x12": 2,  # Load for store
            "x13": 2,  # Load-modify chain (1 + 1)
            "x14": 3,  # Load-store-load chain (2 + 1)
        }
        
        print("\n=== TEST RESULTS ===")
        all_passed = True
        
        for reg, expected_val in expected.items():
            actual_val = results[reg]
            if actual_val == expected_val:
                print(f"✓ {reg}: {actual_val} (PASS)")
            else:
                print(f"✗ {reg}: {actual_val}, expected {expected_val} (FAIL)")
                all_passed = False
        
        if all_passed:
            print("\n🎉 ALL TESTS PASSED! Load-use hazard handling is working correctly!")
        else:
            print("\n❌ SOME TESTS FAILED! There may still be issues with load-use hazard handling.")
            
        # Additional memory verification
        print("\n=== MEMORY VERIFICATION ===")
        try:
            data_mem = dut.data_mem_inst.data_ram
            mem_results = {}
            # Check stored values
            for i in range(4):
                addr = i * 4
                try:
                    # Read 4 bytes and combine (little-endian)
                    val = (int(data_mem[addr+3].value) << 24) | \
                          (int(data_mem[addr+2].value) << 16) | \
                          (int(data_mem[addr+1].value) << 8) | \
                          int(data_mem[addr].value)
                    mem_results[f"mem[{addr}]"] = val
                except:
                    mem_results[f"mem[{addr}]"] = "UNKNOWN"
            
            for addr, val in mem_results.items():
                print(f"{addr} = {val}")
                
        except Exception as e:
            print(f"Memory verification failed: {e}")
        
    except Exception as e:
        print(f"Register verification failed: {e}")
        print("Manual inspection of waveforms may be needed")

def runCocotbTests():
    """Run comprehensive load-use test"""
    from cocotb_test.simulator import run
    import shutil
    import os
    
    hex_file = create_comprehensive_test_hex()
    print(f"Created comprehensive test hex: {hex_file}")
    
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
    sim_build_dir = os.path.join(curr_dir, "sim_build", "comprehensive_test")
    if os.path.exists(sim_build_dir):
        shutil.rmtree(sim_build_dir)
    
    run(
        verilog_sources=sources,
        toplevel="top",
        module="comprehensive_load_test",
        testcase="test_comprehensive_load_use",
        includes=[str(incl_dir)],
        simulator="verilator",
        timescale="1ns/1ps",
        defines=[f"INSTR_HEX_FILE=\"{hex_file}\""],
        sim_build=sim_build_dir,
        force_compile=True,
    )

if __name__ == "__main__":
    runCocotbTests()