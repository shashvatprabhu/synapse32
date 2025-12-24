"""
Minimal test to debug the HALT issue
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

def encode_r_type(opcode, rd, funct3, rs1, rs2, funct7):
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

def encode_i_type(opcode, rd, funct3, rs1, imm):
    imm = imm & 0xFFF
    return (imm << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

def ADD(rd, rs1, rs2):
    return encode_r_type(0x33, rd, 0x0, rs1, rs2, 0x00)

def ADDI(rd, rs1, imm):
    return encode_i_type(0x13, rd, 0x0, rs1, imm)

def HALT():
    return 0x00000073

async def reset_dut(dut):
    dut.rst.value = 1
    await ClockCycles(dut.clk, 5)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 2)

async def load_program(dut, instructions):
    for i, instr in enumerate(instructions):
        dut.instr_mem_inst.instr_ram[i].value = instr

def get_register(dut, reg_num):
    if reg_num == 0:
        return 0
    return int(dut.cpu_inst.rf_inst0.register_file[reg_num].value)

@cocotb.test()
async def test_add_before_halt(dut):
    """Minimal test: Simple ADD right before HALT"""

    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    # Minimal program: just a few ADDs and then HALT
    program = [
        ADDI(1, 0, 5),      # x1 = 5
        ADDI(2, 0, 3),      # x2 = 3
        ADD(3, 1, 2),       # x3 = x1 + x2 = 8  (first ADD, should work)
        ADD(4, 3, 1),       # x4 = x3 + x1 = 13 (second ADD before HALT)
        HALT(),             # ECALL
    ]
    await load_program(dut, program)

    # Run for enough cycles
    for cycle in range(50):
        await RisingEdge(dut.clk)

        # Log register values and pipeline state
        x3 = get_register(dut, 3)
        x4 = get_register(dut, 4)

        # Log pipeline stages
        if_id_instr = int(dut.if_id_inst0.instruction_out.value)
        id_ex_rd = int(dut.id_ex_inst0.rd_addr_out.value)
        id_ex_rd_valid = int(dut.id_ex_inst0.rd_valid_out.value)
        ex_mem_rd = int(dut.ex_mem_inst0.rd_addr_out.value)
        ex_mem_rd_valid = int(dut.ex_mem_inst0.rd_valid_out.value)
        mem_wb_rd = int(dut.mem_wb_inst0.rd_addr_out.value)
        mem_wb_rd_valid = int(dut.mem_wb_inst0.rd_valid_out.value)

        print(f"Cycle {cycle}: x3={x3}, x4={x4} | "
              f"ID_EX(rd={id_ex_rd},v={id_ex_rd_valid}) "
              f"EX_MEM(rd={ex_mem_rd},v={ex_mem_rd_valid}) "
              f"MEM_WB(rd={mem_wb_rd},v={mem_wb_rd_valid})")

    print(f"\nFinal: x3={get_register(dut, 3)} (expected 8)")
    print(f"Final: x4={get_register(dut, 4)} (expected 13)")

    assert get_register(dut, 3) == 8, f"x3 should be 8, got {get_register(dut, 3)}"
    assert get_register(dut, 4) == 13, f"x4 should be 13, got {get_register(dut, 4)}"


if __name__ == "__main__":
    from cocotb_test.simulator import run
    import os

    root_dir = os.getcwd()
    while not os.path.exists(os.path.join(root_dir, "rtl")):
        if os.path.dirname(root_dir) == root_dir:
            raise FileNotFoundError("rtl directory not found")
        root_dir = os.path.dirname(root_dir)

    rtl_dir = os.path.join(root_dir, "rtl")
    incl_dir = os.path.join(rtl_dir, "include")

    sources = []
    for root, _, files in os.walk(rtl_dir):
        for file in files:
            if file.endswith(".v"):
                sources.append(os.path.join(root, file))

    run(
        verilog_sources=sources,
        toplevel="top",
        module="debug_test",
        includes=[incl_dir],
        simulator="verilator",
        timescale="1ns/1ps",
    )
