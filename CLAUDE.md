# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL RULES - READ FIRST

### Modification Permissions

**ALLOWED without permission:**
- ✅ Write new test files in `tests/`
- ✅ Write documentation files (`.md`) in `docs/`
- ✅ Run existing tests
- ✅ Read and analyze any files

**REQUIRES USER PERMISSION:**
- ❌ Modify ANY files in `rtl/` (Verilog hardware files)
- ❌ Modify existing test files in `tests/`
- ❌ Modify build scripts or configuration files
- ❌ Delete any files
- ❌ Make git commits

**When you need to modify RTL or existing tests:**
1. Explain what needs to change and why
2. Show the proposed changes
3. Wait for explicit user approval
4. Only then make the changes

## Project Overview

Synapse-32 is a 32-bit RISC-V CPU core written in Verilog, supporting RV32I instructions plus Zicsr and Zifencei extensions. It implements a classic 5-stage pipeline (IF, ID, EX, MEM, WB) with data forwarding, load-use hazard detection, and a 4-way set-associative instruction cache.

## Common Development Commands

### Running Tests

```bash
# Run full regression test suite
cd tests
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest

# Run specific test file
pytest system_tests/test_full_integration.py -v

# Run single test
pytest system_tests/test_full_integration.py::test_cache_cold_start -v
```

### Simulating C Programs

```bash
# Compile and run a C program on the CPU
cd sim
python -m venv .venv
source .venv/bin/activate
pip install -r ../tests/requirements.txt
python run_c_code.py test_uart_hello.c

# View waveform (generated as dump.vcd)
gtkwave dump.vcd
```

### Linting Verilog

```bash
# Lint specific module
verilator --lint-only -Wall rtl/riscv_cpu.v

# Use veridian.yml for IDE integration
```

## Architecture Overview

### Directory Structure

- **`rtl/`** - Hardware design (Verilog modules)
  - `core_modules/` - CPU building blocks (ALU, registers, decoder, CSRs, UART, timer)
  - `pipeline_stages/` - Pipeline registers and hazard logic (IF_ID, ID_EX, EX_MEM, MEM_WB)
  - `include/` - Shared constants (`instr_defines.vh`, `memory_map.vh`)
  - Top-level: `top.v` (system integration), `riscv_cpu.v` (5-stage pipeline)

- **`tests/`** - Cocotb + pytest testing infrastructure
  - `unit_tests/` - Individual component tests (ALU, decoder)
  - `system_tests/` - 29 integration tests covering all instruction types and hazards

- **`sim/`** - C program simulation support
  - `run_c_code.py` - Main simulator script
  - `link.ld` - Linker script for RISC-V programs
  - `start.S` - Assembly startup code

### Pipeline Stages and Hazard Handling

**5-Stage Pipeline:**
1. **IF (Instruction Fetch)** - PC + Instruction Cache + Instruction Memory
2. **ID (Instruction Decode)** - Decoder + Register File Read
3. **EX (Execute)** - ALU + Branch Logic + CSR Operations
4. **MEM (Memory Access)** - Data Memory + Timer + UART
5. **WB (Write Back)** - Write-back Multiplexer

**Hazard Mitigation:**
- **Forwarding Unit** (`rtl/pipeline_stages/forwarding_unit.v`) - Resolves RAW hazards by forwarding from EX/MEM and MEM/WB stages
- **Load-Use Detector** (`rtl/pipeline_stages/load_use_detector.v`) - Inserts 1-cycle stall when load result needed immediately
- **Branch Flush** - Clears IF_ID and ID_EX on taken branches (in `riscv_cpu.v`)

**Critical Implementation Detail:** Branch flush MUST override cache stall for IF_ID stage to prevent delay slot behavior:
```verilog
assign if_id_stall = combined_stall && !branch_flush;
```

### Instruction Cache

**Configuration** (in `rtl/icache_nway_multiword.v`):
- 4-way set-associative
- 64 sets
- 4 words per cache line (16 bytes)
- Total size: 4KB
- Round-robin replacement policy
- FENCE.I support for cache invalidation

**Integration:** Cache sits between CPU and instruction memory in `top.v`. Stall signal (`icache_stall`) propagates to CPU pipeline.

### Memory Map

Defined in `rtl/include/memory_map.vh`:
- **Instruction Memory:** 0x00000000 - 0x0007FFFF (512KB)
- **Data Memory:** 0x10000000 - 0x100FFFFF (1MB)
- **Timer:** 0x20000000 - 0x20000007 (MTIME, MTIMECMP)
- **UART:** 0x30000000 - 0x30000003 (TX/RX registers)

### Key Modules

- **`riscv_cpu.v`** - Top-level CPU module, instantiates all pipeline stages and hazard logic
- **`alu.v`** - Arithmetic/Logic Unit (10 operations: ADD, SUB, AND, OR, XOR, SLL, SRL, SRA, SLT, SLTU)
- **`registerfile.v`** - 32 x 32-bit registers with synchronous reset and write-through forwarding
- **`decoder.v`** - Decodes 34 instruction types (RV32I + Zicsr + Zifencei)
- **`execution_unit.v`** - Combines ALU, branch resolution, and CSR operations
- **`memory_unit.v`** - Load/store controller with byte enables
- **`icache_nway_multiword.v`** - N-way set-associative instruction cache

## Testing Framework

**Stack:** Cocotb (Python testbenches) + Verilator (simulator) + pytest (runner)

**Test Organization:**
- Unit tests verify individual modules (ALU operations, instruction decoding)
- System tests (`test_full_integration.py`) verify entire CPU with 29 tests:
  - Cache operations (cold start, hit/miss, line boundaries, stalls)
  - All instruction types: R, I, S, B, U, J
  - Pipeline hazards: RAW, load-use, control
  - FENCE.I cache invalidation
  - CSR operations
  - Complex programs (nested loops, function calls)

**Writing New Tests:**
- Use `tests/system_tests/test_full_integration.py` as template
- Cocotb test functions are async: `async def test_name(dut)`
- Always reset DUT: `await reset_dut(dut)`
- Wait for pipeline to fill: `await wait_cycles(dut, 5)`
- Check register values: `assert dut.cpu.rf.register_file[reg].value == expected`

## C Program Simulation

**Workflow:**
1. Write C code using standard library (limited - no malloc, no printf to stdout)
2. Use UART for output: memory-mapped writes to 0x30000000
3. Compile with `riscv32-unknown-elf-gcc` (handled by `run_c_code.py`)
4. Linker script (`link.ld`) places code at 0x00000000, data at 0x10000000
5. Startup code (`start.S`) initializes stack pointer and calls main
6. Simulator loads program.hex into instruction memory and runs

**Example UART output in C:**
```c
volatile char *uart_tx = (char *)0x30000000;
*uart_tx = 'H';
*uart_tx = 'i';
```

**Simulator Configuration:**
- Clock: 100MHz (10ns period)
- UART baud rate: 19,200 (5208 cycles per byte)
- Timeout: 100,000 cycles default

## Important Implementation Notes

### Recent Bug Fixes (Instruction Cache Integration)

1. **SLT/SLTU Return Value** (`rtl/core_modules/alu.v`):
   - **Before:** `{32{comparison}}` returned 0xFFFFFFFF when true
   - **After:** `{31'b0, comparison}` returns 0 or 1 (RISC-V spec compliant)

2. **Register File Reset** (`rtl/core_modules/registerfile.v`):
   - **Before:** Used `initial` blocks (simulation only)
   - **After:** Proper `rst` input with synchronous reset logic

3. **Branch Flush During Cache Stall** (`rtl/riscv_cpu.v`):
   - **Issue:** Branches appeared to have delay slots when cache stalled
   - **Fix:** `if_id_stall = combined_stall && !branch_flush` ensures branch flush overrides cache stall

### Verilog Coding Style

- Use `default_nettype none` for better error checking
- Prefer synchronous reset over initial blocks
- Pipeline registers use `always @(posedge clk)` with enable/stall logic
- Combinational logic uses `always @(*)` or `assign`
- Include guard pattern: `ifndef MODULE_V / define MODULE_V / endif`

### Signal Naming Conventions

- Stage-to-stage signals: `<src_stage>_<dst_stage>_<signal_name>` (e.g., `id_ex_alu_op`)
- Control signals: descriptive names (e.g., `branch_flush`, `stall_pipeline`)
- Memory interfaces: `mem_addr`, `mem_data`, `mem_we`, `mem_re`
- Active-high signals preferred (except `rst` which can be either)

## Adding New Instructions

1. Add instruction ID to `rtl/include/instr_defines.vh`
2. Update decoder in `rtl/core_modules/decoder.v`:
   - Add opcode/funct3/funct7 detection
   - Set control signals (ALU op, mem read/write, etc.)
3. Update ALU in `rtl/core_modules/alu.v` if new operation needed
4. Add test case in `tests/system_tests/test_full_integration.py`
5. Verify with `pytest tests/system_tests/test_full_integration.py::test_your_new_test -v`

## Modifying Cache Parameters

Cache is configurable via parameters in `rtl/icache_nway_multiword.v`:
```verilog
parameter NUM_WAYS = 4;           // Associativity
parameter NUM_SETS = 64;          // Number of sets
parameter CACHE_LINE_WORDS = 4;   // Words per line
```

After changing, update instantiation in `rtl/top.v` and re-run integration tests.

## Debugging Tips

- **Waveform viewing:** GTKWave with `dump.vcd` from simulations
- **Key signals to watch:**
  - `cpu_pc_out` - Current PC
  - `instr_to_cpu` - Fetched instruction
  - `if_id_instr`, `id_ex_instr`, etc. - Pipeline progression
  - `branch_flush`, `stall_pipeline`, `icache_stall` - Hazard signals
  - `register_file[1]` through `register_file[31]` - Register values
- **Common issues:**
  - Pipeline not flushing on branch → Check `branch_flush` logic
  - Wrong register values → Check forwarding paths in `forwarding_unit.v`
  - Cache misses → Verify `icache_stall` propagation
  - UART not outputting → Check memory map, verify 19,200 baud timing
