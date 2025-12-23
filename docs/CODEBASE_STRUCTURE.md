# Synapse-32 RISC-V CPU Codebase Structure and Architecture

## Executive Summary

Synapse-32 is a 32-bit RISC-V CPU core implementing the RV32I base instruction set with Zicsr (Control and Status Register) and Zifencei (Fence.I) extensions. The codebase is organized into clear functional domains: RTL modules, test suites, simulation infrastructure, and configuration files. The system features a 5-stage pipeline with comprehensive hazard handling, an integrated instruction cache, and full support for interrupts and CSR operations.

---

## 1. Directory Structure and Purpose

### Root Level Files
```
/home/shashvat/cursor/synapse32/
├── README.md                      # User-facing documentation
├── RISC V CPU Project.md         # Project overview document
├── veridian.yml                  # Verilator/linting configuration
├── .gitignore                    # Git ignore patterns
├── .devcontainer/               # Development container config
├── .github/                     # GitHub actions and workflows
├── .vscode/                     # VS Code workspace settings
└── .git/                        # Git repository metadata
```

### Core Directories

#### `/rtl` - Register Transfer Level Design
The complete hardware implementation using SystemVerilog/Verilog.

**Subdirectories:**
- **`core_modules/`** - Fundamental CPU components
- **`pipeline_stages/`** - 5-stage pipeline register and hazard logic
- **`include/`** - Shared header files with instruction and memory definitions

**Key Files:**
- `top.v` - Top-level system integration (connects CPU, memories, peripherals)
- `riscv_cpu.v` - Main CPU pipeline core
- `execution_unit.v` - Execution stage ALU and operations
- `memory_unit.v` - Load/store control logic
- `writeback.v` - Write-back stage multiplexer
- `icache_nway_multiword.v` - 4-way set-associative instruction cache (NEW)
- `instr_mem.v` - Instruction memory
- `data_mem.v` - Data memory
- `seven_seg.v` - Seven-segment display driver

#### `/rtl/core_modules` - Fundamental Building Blocks

| Module | Purpose |
|--------|---------|
| `alu.v` | 32-bit arithmetic/logic unit (ADD, SUB, AND, OR, XOR, SLL, SRL, SRA, SLT, SLTU) |
| `registerfile.v` | 32 x 32-bit register bank with read/write ports |
| `decoder.v` | Instruction decoder (converts RISC-V to internal signals) |
| `pc.v` | Program counter with stall and jump handling |
| `csr_file.v` | Control and Status Register file (mstatus, mie, mip, mtvec, mepc, mcause, etc.) |
| `csr_exec.v` | CSR operation executor (CSRRW, CSRRS, CSRRC, immediate variants) |
| `interrupt_controller.v` | Interrupt priority and delegation logic |
| `timer.v` | Machine-mode timer with mtime/mtimecmp |
| `uart.v` | Universal asynchronous receiver/transmitter |

#### `/rtl/pipeline_stages` - Pipeline Stage Registers and Hazard Logic

| Module | Purpose |
|--------|---------|
| `IF_ID.v` | Instruction Fetch → Decode pipeline register (32-bit PC, instruction) |
| `ID_EX.v` | Instruction Decode → Execute pipeline register |
| `EX_MEM.v` | Execute → Memory pipeline register |
| `MEM_WB.v` | Memory → Write-back pipeline register |
| `forwarding_unit.v` | Data forwarding logic (resolves RAW hazards) |
| `load_use_detector.v` | Detects when load result needed immediately (stalls pipeline) |
| `store_load_detector.v` | Detects WAR/WAW conflicts between stores and subsequent loads |
| `store_load_forward.v` | Forwards store data to later loads (memory-to-memory optimization) |

#### `/rtl/include` - Header Files with Definitions

| File | Content |
|------|---------|
| `instr_defines.vh` | Instruction type constants (INSTR_ADD = 6'h01, etc.) |
| `memory_map.vh` | Memory layout (instruction mem: 0x00000000, data mem: 0x10000000, peripherals) |

#### `/tests` - Testing Infrastructure

**Organization:**
```
tests/
├── pytest.ini                    # Pytest configuration
├── requirements.txt              # Python dependencies (cocotb, pytest, numpy)
├── unit_tests/                  # Individual module tests
├── system_tests/                # Full integration tests
├── build/                       # Build artifacts
├── sim_build/                   # Simulation build outputs
└── waveforms/                   # Generated waveform files
```

**Unit Tests** (`/unit_tests`)
- `test_alu.py` - ALU operation verification (ADD, SUB, SLL, SRL, SRA, SLT, SLTU)
- `test_decoder_gcc.py` - Instruction decoder with GCC-compiled code

**System Tests** (`/system_tests`)
- `test_full_integration.py` - Comprehensive 29-test suite covering all features
- `test_riscv_cpu_basic.py` - Basic CPU operation and RAW hazard testing
- `test_csr.py` - Control and Status Register operations
- `test_interrupts.py` - Interrupt handling and priority
- `test_uart_cpu.py` - UART communication testing
- `test_fibonacci.py` - Fibonacci calculation (stress test)
- `test_icache.py` - Instruction cache unit tests

#### `/sim` - Simulation Support

| File | Purpose |
|------|---------|
| `run_c_code.py` | Main simulation runner - compiles C code and runs verilator simulation |
| `c_runner.mk` | Makefile for C program compilation to RISC-V |
| `link.ld` | Linker script defining memory layout for C programs |
| `start.S` | Assembly startup code for C programs |
| `fibonacci.c` | Example C program (Fibonacci calculation) |
| `test_uart_hello.c` | Example UART communication program |

#### `/tb` - Old Testbenches (Legacy)

SystemVerilog testbenches for individual modules (mostly superseded by cocotb tests).

#### `/docs` - Documentation

- `CHANGES_ICACHE_INTEGRATION.md` - Recent instruction cache integration details
- `cursor_suggestions.md` - Cursor AI suggestions (generated)

#### `/flash` - Reserved for Flash Storage

Currently empty; intended for flash memory interface development.

---

## 2. Main RTL Modules and Their Relationships

### System-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          TOP MODULE                             │
│                        (top.v)                                  │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   RISC-V CPU     │  │    ICACHE    │  │  INSTR_MEM   │    │
│  │  (riscv_cpu.v)   │◄─┤(icache_nway) ├─►│ (instr_mem.v)│    │
│  │                  │  │  multiword   │  │              │    │
│  │  Controls:       │  └──────────────┘  └──────────────┘    │
│  │  - PC            │         ▲                                │
│  │  - IF/ID/EX/...  │         │ FENCE.I                        │
│  │  - Forwarding    │         │ invalidate                      │
│  │  - Hazard detect │         │                                │
│  └────┬──┬──────────┘         │                                │
│       │  │                    │                                │
│       │  └────────────────────┘                                │
│       │                                                         │
│  ┌────▼──────────────────┐  ┌──────────────┐  ┌──────────┐   │
│  │   DATA MEMORY         │  │  TIMER       │  │   UART   │   │
│  │  (data_mem.v)         │  │ (timer.v)    │  │(uart.v)  │   │
│  │  1MB, 0x10000000      │  │              │  │          │   │
│  └───────────────────────┘  └──────────────┘  └──────────┘   │
│                                                                 │
│  Memory-mapped I/O routing (top.v)                             │
└─────────────────────────────────────────────────────────────────┘
```

### CPU Pipeline Architecture

The 5-stage pipeline with hazard mitigation:

```
┌─────────────────────────────────────────────────────────────────┐
│                    RISC-V CPU PIPELINE                          │
│                    (riscv_cpu.v)                               │
└─────────────────────────────────────────────────────────────────┘

1. FETCH (IF)
   ├─ PC Module (pc.v)
   │  ├─ Input: j_signal, jump address, stall
   │  └─ Output: next address
   └─ Instruction Cache → Instruction Memory

2. DECODE (ID)
   ├─ IF_ID Pipeline Register (IF_ID.v)
   │  ├─ Latches: PC, instruction
   │  └─ Stall control for load-use / cache miss
   │
   ├─ Decoder (decoder.v)
   │  ├─ Extracts: opcode, rs1, rs2, rd, immediate
   │  └─ Generates: control signals, instruction ID
   │
   └─ Register File Read (registerfile.v)
      ├─ Synchronous reset on rst signal
      └─ Forwarding bypass path (write-through on same cycle)

3. EXECUTE (EX)
   ├─ ID_EX Pipeline Register (ID_EX.v)
   │  └─ Latches: registers values, immediates, control signals
   │
   ├─ Forwarding Unit (forwarding_unit.v)
   │  ├─ Monitors: MEM and WB stage results
   │  └─ Controls: 2-bit forward_a, forward_b signals
   │
   ├─ Execution Unit (execution_unit.v)
   │  ├─ Data routing with forwarding multiplexer
   │  ├─ ALU (alu.v) - arithmetic/logical operations
   │  ├─ Branch resolution (BEQ, BNE, BLT, BGE, etc.)
   │  └─ Jump address calculation (JAL, JALR)
   │
   ├─ CSR Execution (inside execution_unit.v)
   │  ├─ Read from CSR file
   │  └─ Write CSR values
   │
   └─ Outputs: exec_output, jump_signal, jump_addr, mem_addr

4. MEMORY (MEM)
   ├─ EX_MEM Pipeline Register (EX_MEM.v)
   │  └─ Latches: result, memory address, register write data
   │
   ├─ Memory Unit (memory_unit.v)
   │  ├─ Decode: LW, LB, LBU, LH, LHU (loads)
   │  ├─ Decode: SW, SB, SH (stores)
   │  ├─ Byte enable generation (alignment checking)
   │  └─ Load type signals (for sign extension)
   │
   ├─ Store/Load Detection (store_load_detector.v, store_load_forward.v)
   │  └─ Optimizes memory write-to-read forwarding
   │
   ├─ Data Memory (data_mem.v)
   │  └─ 1MB @ 0x10000000
   │
   └─ Peripherals (Timer, UART) via memory mapping

5. WRITE-BACK (WB)
   ├─ MEM_WB Pipeline Register (MEM_WB.v)
   │  └─ Latches: memory read data, ALU result
   │
   ├─ Write-back Mux (writeback.v)
   │  ├─ Selects: ALU result vs. memory data
   │  └─ Routes to register file
   │
   └─ Register File Write (registerfile.v)
      └─ Updates register with selected data
```

### Hazard Resolution Pipeline

**Three hazard mitigation mechanisms:**

1. **Data Forwarding** (forwarding_unit.v)
   - Detects RAW (Read-After-Write) hazards
   - Forwards EX/MEM and MEM/WB results to EX stage inputs
   - Eliminates most stalls
   - Does NOT forward from load in MEM (must wait for WB)

2. **Load-Use Hazard Detection** (load_use_detector.v)
   - Detects: instruction in MEM is a load, next instruction needs that register
   - Action: Inserts 1-cycle stall (stall_pipeline signal)
   - Combined with icache_stall: `combined_stall = stall_pipeline || icache_stall`

3. **Control Hazard (Branch Flush)**
   - Branch decision made in EX stage
   - IF_ID flushed with NOP (instruction → 32'h13)
   - **Critical:** IF/ID flush overrides cache stall
   - PC updated to branch target

---

## 3. Test Structure

### Testing Framework
- **Framework:** Cocotb (Python-based hardware testing)
- **Simulator:** Verilator (synthesizable RTL simulation)
- **Waveform Viewer:** GTKWave (optional, for debug)
- **Test Runner:** Pytest (orchestrates cocotb tests)

### Test Organization

#### Unit Tests
**Location:** `/tests/unit_tests/`

`test_alu.py`:
- Tests individual ALU operations
- Covers ADD, SUB, XOR, OR, AND, SLL, SRL, SRA, SLT, SLTU
- Tests normal cases and corner cases (overflow, sign extension)
- Helper function: `verify_alu_operation()`

`test_decoder_gcc.py`:
- Tests instruction decoder with actual RISC-V encoded instructions
- Uses GCC-generated instruction encodings
- Validates opcode extraction and field decoding

#### System Tests
**Location:** `/tests/system_tests/`

`test_full_integration.py` (29 comprehensive tests):
- **Cache Operations (5 tests)**
  - Cold start miss, cache hits, line boundary, multi-line programs, stall handling
  
- **Instruction Types (12 tests)**
  - R-type: ADD, SUB, AND, OR, XOR, SLL, SRL, SRA, SLT, SLTU
  - I-type: ADDI, ANDI, ORI, XORI, SLTI, SLTIU, SLLI, SRLI, SRAI
  - Loads: LW, LB, LBU, LH, LHU
  - Stores: SW, SB, SH
  
- **Control Flow (4 tests)**
  - Branches: BEQ, BNE, BLT, BGE, BLTU, BGEU
  - Jumps: JAL, JALR
  
- **Hazards (3 tests)**
  - RAW (Read-After-Write)
  - Load-Use detection
  - Control (branch flush)
  
- **FENCE.I (1 test)**
  - Cache invalidation
  
- **CSR Operations (2 tests)**
  - Read/Write operations
  - Immediate variants
  
- **Complex Programs (3 tests)**
  - Nested loops
  - Function calls
  - Memory-intensive operations

`test_riscv_cpu_basic.py`:
- RAW hazard testing with back-to-back dependencies
- Program helper function: `run_test_program()`
- Register value verification

`test_csr.py`:
- Control and Status Register operations
- Tests mstatus, mie, mip, mtvec, mepc, mcause
- Interrupt cause encoding

`test_interrupts.py`:
- Interrupt request and handling
- Priority arbitration
- Interrupt handler invocation
- MRET instruction (return from interrupt)

`test_uart_cpu.py`:
- UART TX communication
- Baud rate verification (5208 divisor @ 100MHz = 19,200 baud)
- Byte transmission and reception
- Integration with CPU execution

`test_fibonacci.py`:
- Fibonacci number calculation
- Tests sustained computation
- Memory and register usage

`test_icache.py`:
- Instruction cache unit tests
- Cache hit/miss scenarios
- FENCE.I invalidation
- Cache refill timing

### Test Infrastructure Files

`pytest.ini`:
```ini
[pytest]
python_functions = runCocotbTests
```
- Restricts pytest test discovery to cocotb test runner function
- Prevents pytest from trying to run cocotb tests directly

`requirements.txt`:
- cocotb==1.9.2
- cocotb-test==0.2.6
- pytest==8.3.5
- numpy, supporting packages

---

## 4. Simulation Workflow

### How C Programs Run on the CPU

```
C Program Flow:
┌────────────────────────────────────────────────────────────────┐
│ 1. User writes C code (fibonacci.c, test_uart_hello.c)         │
│                                                                 │
│ 2. run_c_code.py script:                                       │
│    ├─ Invokes compile_c_files()                                │
│    │  └─ Runs: riscv32-unknown-elf-gcc with:                   │
│    │     ├─ start.S (assembly startup)                         │
│    │     ├─ link.ld (linker script)                            │
│    │     └─ C source files                                     │
│    │                                                            │
│    ├─ Generates: program.hex (instruction memory initialization)│
│    │                                                            │
│    ├─ Calls: verilator with cocotb                             │
│    │     ├─ Loads: program.hex into instruction memory         │
│    │     ├─ Sets: CPU clock frequency (100MHz, 10ns period)    │
│    │     ├─ Monitors: UART TX line via UartMonitor class       │
│    │     └─ Runs: simulation until CPU halts                   │
│    │                                                            │
│    └─ Outputs:                                                 │
│       ├─ Waveform file (GTKWave compatible)                    │
│       ├─ UART output (captured characters)                     │
│       └─ Test results (PASS/FAIL)                              │
└────────────────────────────────────────────────────────────────┘
```

### Key Components of run_c_code.py

**UartMonitor Class:**
- Monitors UART TX line (bit-by-bit)
- Detects start/stop bits
- Samples 8 data bits at baud rate centers
- Stores received bytes and converts to ASCII string
- Tracks simulation time with nanosecond precision

**compile_c_files() Function:**
- Command: `riscv32-unknown-elf-gcc -march=rv32i -mabi=ilp32 ...`
- Includes: startup code, linker script, C source files
- Output: ELF binary → disassembled to assembly (optional)
- Final output: program.hex (Intel HEX format for memory initialization)

**Simulation Runner:**
- Cocotb test harness
- Clock generation: Clock(dut.clk, 10ns) = 100MHz
- Memory initialization from program.hex
- Runs until CPU stops or timeout

### Memory Initialization

**Link Script (link.ld):**
```
MEMORY {
  INSTR_MEM (rx) : ORIGIN = 0x00000000, LENGTH = 512K
  DATA_MEM  (rwx): ORIGIN = 0x10000000, LENGTH = 1M
  STACK            : ORIGIN = 0x100FFFFF (grows down)
}
```

**Startup Code (start.S):**
- Initializes stack pointer (sp/x2)
- Calls main()
- Infinite loop on return

### Simulation Timing

- **CPU Clock:** 100MHz (10ns period)
- **UART Baud Rate:** 100MHz / 5208 = ~19,200 baud
- **Bit Period:** 5208 CPU cycles ≈ 52.08 µs
- **Monitor:** Samples at 1.5 bit periods from start bit

---

## 5. Key Configuration and Build Files

### veridian.yml - Linting and Syntax Configuration

```yaml
include_dirs:
  - rtl
  - tb

source_dirs:
  - rtl          # Recursively searched for .v/.sv files
  - tb

verilator:
  syntax:
    enabled: true
    path: "verilator"
    args:
      - --lint-only   # Check for syntax errors
      - -Wall         # Enable all warnings
      - -Irtl         # Include directories
      - -Itb

log_level: Debug
```

**Purpose:** Automated syntax checking and linting before simulation.

### Makefile (sim/c_runner.mk)

```makefile
TOPLEVEL_LANG = verilog
TOPLEVEL = top
MODULE = run_c_code
VERILOG_SOURCES = $(wildcard $(shell pwd)/../rtl/**/*.v) ...
INCLUDES = -I$(shell pwd)/../rtl/include/ ...
SIM = verilator

EXTRA_ARGS += --trace -DINSTR_HEX_FILE=\"$(INSTRUCTION_MEMORY_HEX)\"
include $(shell cocotb-config --makefiles)/Makefile.sim
```

**Purpose:** Cocotb makefile configuration for compiling simulations.

### Memory Map Header (rtl/include/memory_map.vh)

```verilog
`define INSTR_MEM_BASE   32'h00000000  // Instruction memory
`define INSTR_MEM_SIZE   32'h00080000  // 512KB
`define DATA_MEM_BASE    32'h10000000  // Data memory
`define DATA_MEM_SIZE    32'h00100000  // 1MB
`define TIMER_BASE       32'h02004000  // Machine timer
`define UART_BASE        32'h20000000  // UART peripheral
```

**Purpose:** Centralized memory layout definition used by all modules.

### Instruction Decoder Header (rtl/include/instr_defines.vh)

```verilog
localparam [5:0] INSTR_ADD    = 6'h01;
localparam [5:0] INSTR_ADDI   = 6'h0B;
localparam [5:0] INSTR_LW     = 6'h16;
localparam [5:0] INSTR_BEQ    = 6'h1C;
localparam [5:0] INSTR_JAL    = 6'h22;
localparam [5:0] INSTR_FENCE_I = 6'h26;
localparam [5:0] INSTR_CSRRW  = 6'h27;
// ... 34 instruction types total
```

**Purpose:** Single source of truth for instruction type constants.

### Linker Script (sim/link.ld)

```ld
MEMORY {
  INSTR_MEM (rx)  : ORIGIN = 0x00000000, LENGTH = 512K
  DATA_MEM (rwx)  : ORIGIN = 0x10000000, LENGTH = 1M
}

SECTIONS {
  .text : {
    *(.text*) *(.rodata*)
  } > INSTR_MEM
  
  .data : {
    *(.data*) *(.bss*)
  } > DATA_MEM
}
```

**Purpose:** Defines memory layout for compiled C programs.

---

## 6. Recent Additions: Instruction Cache Integration

### New Module: icache_nway_multiword.v

**Configuration:**
- **Associativity:** 4-way set-associative
- **Sets:** 64 (6-bit index)
- **Words per line:** 4 (2-bit offset)
- **Total size:** 4 KB (64 sets × 4 ways × 4 words × 4 bytes)
- **Replacement:** Round-robin policy

**Interface:**
```verilog
module icache #(
    parameter NUM_WAYS = 4,
    parameter NUM_SETS = 64,
    parameter CACHE_LINE_WORDS = 4
)(
    // CPU side
    input [31:0] cpu_addr,
    input cpu_req,
    output reg [31:0] cpu_data,
    output reg cpu_valid,        // Hit signal
    output reg cpu_stall,        // Miss signal
    
    // Memory side
    output reg [31:0] mem_addr,
    output reg mem_req,
    input [31:0] mem_data,
    input mem_valid,
    
    // Control
    input invalidate             // FENCE.I signal
);
```

**Key Features:**
- **Cache Hit:** cpu_valid=1, cpu_stall=0 (instruction available)
- **Cache Miss:** cpu_valid=0, cpu_stall=1 (request goes to memory)
- **Refill:** On mem_valid, updates cache and asserts cpu_valid
- **FENCE.I:** Clears all valid bits (invalidate signal)

### Modified Files for Cache Integration

**riscv_cpu.v:**
- Added icache_stall and fence_i_signal ports
- Combined stall sources: `combined_stall = stall_pipeline || icache_stall`
- **Critical fix:** Branch flush overrides cache stall in IF_ID

**top.v:**
- Instantiated icache between CPU and instruction memory
- Connected fence_i_signal from CPU to cache invalidate
- Added cache interface wires

**registerfile.v:**
- Added synchronous reset (rst input)
- Changed from initial blocks to always@(posedge clk or posedge rst)
- All registers clear on reset

**alu.v:**
- **Bug fix:** SLT/SLTU return values (was 0xFFFFFFFF, now 0 or 1)

---

## 7. Key Design Patterns

### Pattern 1: Pipeline Register with Stall Support
All pipeline registers (IF_ID, ID_EX, EX_MEM, MEM_WB) follow:
```verilog
always @(posedge clk or posedge rst) begin
    if (rst)
        output <= initial_value;
    else if (!stall)
        output <= input;
    // else: hold current value on stall
end
```

### Pattern 2: Forwarding Control Signals
```verilog
localparam NO_FORWARDING = 2'b00;
localparam FORWARD_FROM_MEM = 2'b01;
localparam FORWARD_FROM_WB = 2'b10;

// 2-bit signals control multiplexer
wire [1:0] forward_a, forward_b;  // For ALU inputs
```

### Pattern 3: Memory-Mapped I/O Decoding
```verilog
wire data_mem_access = `IS_DATA_MEM(addr);
wire timer_access = `IS_TIMER_MEM(addr);
wire uart_access = `IS_UART_MEM(addr);

// Select correct read data based on access type
assign mem_read_data = timer_access ? timer_data :
                       data_mem_access ? data_mem_data :
                       uart_access ? uart_data : 32'h0;
```

### Pattern 4: Instruction Type Constant Usage
All control logic references 6-bit instruction IDs from instr_defines.vh:
```verilog
always @(*) begin
    case (instr_id)
        INSTR_ADD:  alu_result = rs1 + rs2;
        INSTR_SUB:  alu_result = rs1 - rs2;
        INSTR_BEQ:  branch_taken = (rs1 == rs2);
        // ...
    endcase
end
```

---

## 8. Important Notes for Future Development

### Critical Invariants
1. **PC is 4-byte-aligned** (implicit in architecture)
2. **Register x0 is always 0** (hard-wired in registerfile)
3. **Branch flush overrides cache stall** (prevents delay slot bug)
4. **Load result not forwarded from MEM stage** (must wait for WB)
5. **FENCE.I clears all cache entries** (not fine-grained invalidation)

### Testing Best Practices
1. Always reset CPU before tests: `dut.rst.value = 1; await Timer(20ns); dut.rst.value = 0`
2. Wait for clock edge after reset: `await RisingEdge(dut.clk)`
3. For comparison operations (SLT, BLT), expect signed semantics
4. UART output requires monitoring TX line bit-by-bit
5. Cache stalls add variable latency - use polling loops carefully

### Common Pitfalls
1. Forgetting to stall on load-use hazard (will produce incorrect results)
2. Not flushing pipeline on branch (creates delay slot behavior)
3. Forwarding from load in MEM stage (correct value not yet available)
4. Misaligned memory access (SW/LW must be word-aligned)
5. CSR instructions require proper mtvec/mepc setup for interrupts

### Performance Considerations
- **Cache miss penalty:** Multiple cycles to refill from memory
- **Load-use stall:** 1 cycle per load-use dependency
- **Branch misprediction:** 1 cycle pipeline flush
- **Forwarding:** Eliminates ~90% of RAW hazard stalls

---

## 9. File Relationships and Dependencies

```
top.v (System integration)
├── riscv_cpu.v (CPU pipeline)
│   ├── pc.v (Program counter)
│   ├── IF_ID.v (Fetch/Decode register)
│   ├── decoder.v (Instruction decoder)
│   ├── registerfile.v (32 registers) ← Requires rst input
│   ├── ID_EX.v (Decode/Execute register)
│   ├── execution_unit.v (ALU and branch logic)
│   │   ├── alu.v (Arithmetic operations) ← Fixed SLT return value
│   │   ├── csr_exec.v (CSR operations)
│   │   └── CSR file access
│   ├── EX_MEM.v (Execute/Memory register)
│   ├── forwarding_unit.v (Data forwarding)
│   ├── load_use_detector.v (Hazard detection)
│   ├── memory_unit.v (Load/store control)
│   ├── MEM_WB.v (Memory/Writeback register)
│   ├── writeback.v (Result multiplexer)
│   └── store_load_detector.v, store_load_forward.v
│
├── icache.v (Instruction cache) ← NEW
│   └── Feeds: instr_to_cpu
│       Receives: fence_i_signal
│
├── instr_mem.v (Instruction memory - 512KB)
├── data_mem.v (Data memory - 1MB)
├── timer.v (Machine timer)
├── uart.v (Serial communication)
└── seven_seg.v (Display - not used in simulation)

Include files:
├── rtl/include/memory_map.vh
│   └─ Used by: top.v, tests
│
└── rtl/include/instr_defines.vh
    └─ Used by: All modules with instruction decoding
```

---

## Summary Table

| Aspect | Details |
|--------|---------|
| **Language** | SystemVerilog/Verilog |
| **Instruction Set** | RV32I + Zicsr + Zifencei |
| **Pipeline** | 5-stage with hazard mitigation |
| **Hazard Handling** | Data forwarding, load-use detection, branch flush |
| **Caches** | 4-way set-associative instruction cache (4KB) |
| **Memory** | 512KB instruction, 1MB data |
| **Peripherals** | UART (19,200 baud), Timer, 7-segment display |
| **Test Framework** | Cocotb + Pytest |
| **Simulator** | Verilator |
| **Test Count** | 29 comprehensive integration tests + unit tests |
| **Compilation** | GCC RISC-V toolchain (riscv32-unknown-elf-gcc) |

