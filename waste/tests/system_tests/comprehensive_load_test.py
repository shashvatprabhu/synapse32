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
        0x00122023,  # sw x1, 0(x4)        # Store 1 to mem[0]
        0x00222223,  # sw x2, 4(x4)        # Store 2 to mem[4]
        0x00322423,  # sw x3, 8(x4)        # Store 3 to mem[8]
        
        # Test 1: Basic load-use hazard
        0x00022283,  # lw x5, 0(x4)        # Load 1 -> x5
        0x00528313,  # addi x6, x5, 5      # x6 = x5 + 5 = 6 (LOAD-USE HAZARD)
        
        # Test 2: Back-to-back loads with dependency
        0x00422383,  # lw x7, 4(x4)        # Load 2 -> x7
        0x00822403,  # lw x8, 8(x4)        # Load 3 -> x8
        0x008383b3,  # add x7, x7, x8      # x7 = 2 + 3 = 5 (LOAD-USE HAZARD on both)
        
        # Test 3: Load with multiple dependent instructions
        0x00022483,  # lw x9, 0(x4)        # Load 1 -> x9
        0x00948513,  # addi x10, x9, 9     # x10 = 1 + 9 = 10 (LOAD-USE HAZARD)
        0x00948593,  # addi x11, x9, 9     # x11 = 1 + 9 = 10 (uses same loaded value)
        
        # Test 4: Load-use with store
        0x00422603,  # lw x12, 4(x4)       # Load 2 -> x12
        0x00c22623,  # sw x12, 12(x4)      # Store x12 to mem[12] (LOAD-USE HAZARD)
        
        # Test 5: Chain of dependent loads/operations (FIXED ALIGNMENT)
        0x00022683,  # lw x13, 0(x4)       # Load 1 -> x13
        0x00168693,  # addi x13, x13, 1    # x13 = 1 + 1 = 2 (LOAD-USE HAZARD)
        0x00d22823,  # sw x13, 16(x4)      # Store x13=2 to mem[16] (WORD-ALIGNED!)
        0x01022703,  # lw x14, 16(x4)      # Load back -> x14 = 2
        0x00170713,  # addi x14, x14, 1    # x14 = 2 + 1 = 3 (LOAD-USE HAZARD)
        
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
    
    # Read final register values
    try:
        rf = dut.cpu_inst.rf_inst0.register_file
        results = {}
        
        for i in range(5, 15):
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
            print("\n🎉 ALL TESTS PASSED!")
        else:
            print("\n❌ SOME TESTS FAILED!")
        
        assert all_passed, "Not all register values are correct"
        
    except Exception as e:
        print(f"Test failed: {e}")
        raise

def runCocotbTests():
    """Run comprehensive load-use test"""
    from cocotb_test.simulator import run
    import shutil
    import os
    
    hex_file = create_comprehensive_test_hex()
    print(f"Created comprehensive test hex: {hex_file}")
    
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