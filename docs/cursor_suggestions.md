# Cursor Suggestions for timing_fix Branch

This document contains observations, potential issues, and suggestions for the `timing_fix` branch of the Synapse-32 RISC-V CPU.

---

## Table of Contents

1. [Critical Issues](#critical-issues)
2. [Moderate Issues](#moderate-issues)
3. [Minor Issues / Observations](#minor-issues--observations)
4. [Architecture Comparison with feature/icache-integration](#architecture-comparison-with-featureicache-integration)
5. [What timing_fix Does Better](#what-timing_fix-does-better)

---

## Critical Issues

### 1. ALU SLT/SLTU/SLTI/SLTIU Return Value Bug

**File:** `rtl/core_modules/alu.v`  
**Lines:** 22-23, 31-32

**Current Code:**
```verilog
INSTR_SLT:   ALUoutput = {32{$signed(rs1) < $signed(rs2)}};
INSTR_SLTU:  ALUoutput = {32{rs1 < rs2}};
INSTR_SLTI:  ALUoutput = {32{$signed(rs1) < $signed(imm)}};
INSTR_SLTIU: ALUoutput = {32{rs1 < imm}};
```

**Problem:**  
The `{32{condition}}` syntax replicates the 1-bit comparison result 32 times. When the comparison is true, this returns `0xFFFFFFFF` (-1) instead of `1`.

**RISC-V Specification:**  
"SLT and SLTU perform signed and unsigned compares respectively, writing 1 to rd if rs1 < rs2, 0 otherwise."

**Impact:** Any code using SLT/SLTU for comparisons will get wrong results. This breaks conditional logic, sorting algorithms, and many standard programming patterns.

**Suggested Fix:**
```verilog
INSTR_SLT:   ALUoutput = {31'b0, $signed(rs1) < $signed(rs2)};
INSTR_SLTU:  ALUoutput = {31'b0, rs1 < rs2};
INSTR_SLTI:  ALUoutput = {31'b0, $signed(rs1) < $signed(imm)};
INSTR_SLTIU: ALUoutput = {31'b0, rs1 < imm};
```

---

### 2. Store Byte/Halfword Alignment Bug

**File:** `rtl/memory_unit.v`  
**Lines:** 51-61

**Current Code:**
```verilog
assign store_data_out =
    (instr_id == INSTR_SB) ? {24'b0, rs2_value[7:0]} :
    (instr_id == INSTR_SH) ? {16'b0, rs2_value[15:0]} :
    (instr_id == INSTR_SW) ? rs2_value :
    32'b0;

assign store_byte_en_out =
    (instr_id == INSTR_SB) ? 4'b0001 :
    (instr_id == INSTR_SH) ? ((mem_addr[0] == 1'b0) ? 4'b0011 : 4'b0000) :
    (instr_id == INSTR_SW) ? ((mem_addr[1:0] == 2'b00) ? 4'b1111 : 4'b0000) :
    4'b0000;
```

**Problems:**

1. **SB (Store Byte):** Always enables byte 0 (`4'b0001`) regardless of address alignment.
   - Storing to address `0x101` should enable byte 1 (`4'b0010`), not byte 0.
   - The data should be shifted to the correct byte lane.

2. **SH (Store Halfword):** Only handles aligned (`4'b0011`) or returns `4'b0000` for unaligned.
   - Address `0x102` should enable bytes 2-3 (`4'b1100`).

3. **Data not shifted:** The store data is always placed in the lower bits, but it needs to be shifted based on address alignment.

**Expected Behavior for SB:**

| Address[1:0] | Byte Enable | Data Position |
|--------------|-------------|---------------|
| 2'b00        | 4'b0001     | bits [7:0]    |
| 2'b01        | 4'b0010     | bits [15:8]   |
| 2'b10        | 4'b0100     | bits [23:16]  |
| 2'b11        | 4'b1000     | bits [31:24]  |

**Expected Behavior for SH:**

| Address[1]   | Byte Enable | Data Position |
|--------------|-------------|---------------|
| 1'b0         | 4'b0011     | bits [15:0]   |
| 1'b1         | 4'b1100     | bits [31:16]  |

---

### 3. Register File Missing Hardware Reset

**File:** `rtl/core_modules/registerfile.v`

**Current Code:**
```verilog
initial begin
    register_file[0]  = 0;
    register_file[1]  = 0;
    // ... 30 more lines
end

always @(posedge clk) begin
    register_file[0] <= 0;
    if (wr_en && rd[4:0] != 0) begin
        register_file[rd[4:0]] <= rd_value;
    end
end
```

**Problems:**

1. **No reset input:** The module has no `rst` signal.
2. **Uses `initial` blocks:** These only work in simulation and are not synthesizable for all FPGA tools.
3. **Registers persist across tests:** In simulation, register values carry over between test runs.
4. **No runtime reset capability:** Cannot clear registers without power cycling.

**Impact:**
- Unpredictable behavior on FPGA after configuration
- Test isolation issues in simulation
- Cannot implement software reset functionality

**Suggested Fix:**
```verilog
module registerfile (
    input wire clk,
    input wire rst,  // Add reset input
    // ... other ports
);
    integer i;
    
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            for (i = 0; i < 32; i = i + 1) begin
                register_file[i] <= 32'b0;
            end
        end else begin
            register_file[0] <= 32'b0;
            if (wr_en && rd != 5'b0) begin
                register_file[rd] <= rd_value;
            end
        end
    end
endmodule
```

---

## Moderate Issues

### 4. No FENCE.I Cache Invalidation

**Files:** `rtl/riscv_cpu.v`, `rtl/execution_unit.v`, `rtl/top.v`

**Current Behavior:**
```verilog
// In execution_unit.v
7'b0001111: begin // FENCE
    if (instr_id == INSTR_FENCE_I) begin
        flush_pipeline = 1;
    end
end
```

**Problem:**  
FENCE.I only flushes the pipeline but does not invalidate the instruction cache. Self-modifying code or code loading will not work correctly.

**Missing Components:**
- `fence_i_signal` output from CPU
- Connection to icache's invalidate input
- The icache module does have reset logic that clears valid bits, but no runtime invalidation input

**Suggested Fix:**
1. Add `output wire fence_i_signal` to riscv_cpu.v
2. Add `assign fence_i_signal = (id_ex_inst0_instr_id_out == INSTR_FENCE_I);`
3. Add `input wire invalidate` to icache module
4. Connect in top.v: `.invalidate(fence_i_signal)`

---

### 5. Store Buffer Limitations

**File:** `rtl/pipeline_stages/store_buffer.v`

**Observations:**

1. **Single Entry:** Buffer only holds one store at a time.
   ```verilog
   reg buffer_valid;
   reg [31:0] buffer_addr;
   reg [31:0] buffer_data;
   reg [3:0] buffer_byte_enable;
   ```

2. **Exact Address Match Only:**
   ```verilog
   wire addr_match = (buffer_addr == load_addr);
   assign forward_valid = buffer_valid && addr_match && load_request;
   ```
   - Does not handle partial overlaps
   - Store word to 0x100, then load byte from 0x102 won't forward

3. **Same-Cycle Write and Capture:**
   ```verilog
   if (capture_store) begin
       if (buffer_valid) begin
           mem_wr_en <= 1'b1;  // Write old entry
           // ...
       end
       // Capture new entry
       buffer_valid <= 1'b1;
       buffer_addr <= store_addr;
       // ...
   end
   ```
   - Old store writes to memory in same cycle new store is captured
   - Could cause timing issues in physical implementation

---

### 6. Pipeline Flush Priority During Cache Stall

**File:** `rtl/riscv_cpu.v`

**Current Logic:**
```verilog
// IF_ID instantiation
.enable(!(cache_stall || load_use_stall)),
.flush(branch_flush),
.valid_in(!cache_stall),
```

**In IF_ID.v:**
```verilog
end else if (flush) begin
    // Flush takes priority over enable
    pc_out <= pc_in;
    instruction_out <= 32'h00000013;  // NOP
    valid_out <= 1'b0;
end else if (enable) begin
    // Normal operation
end
// else: hold values (stalled)
```

**Observation:**  
The logic appears correct - `flush` takes priority over `enable`. When a branch is taken during a cache stall, the IF_ID will correctly flush. However, this should be verified with simulation to ensure the interaction between `branch_flush`, `cache_stall`, and `load_use_stall` works in all edge cases.

**Potential Issue:**
When `flush=1` and `enable=0` (due to cache_stall), the IF_ID flushes but the previous stages might still be stalled. Need to verify the instruction that was in IF_ID doesn't get replayed after the stall ends.

---

## Minor Issues / Observations

### 7. Unused Signals

**File:** `rtl/riscv_cpu.v`

```verilog
wire ex_inst0_valid_out;
assign ex_enable_signal = id_ex_valid_out && !cache_stall;
```

The `ex_inst0_valid_out` from execution_unit is declared but the connection to EX_MEM uses `id_ex_valid_out` directly:
```verilog
.valid_in(id_ex_valid_out),       // Uses ID_EX output, not execution_unit output
```

This is actually correct since the valid should come from the pipeline register, not the combinational execution unit. The `ex_inst0_valid_out` wire appears unused.

---

### 8. Instruction Buffer in Top Module

**File:** `rtl/top.v`

```verilog
reg [31:0] instr_buffered;
always @(*) begin
    instr_buffered = instr_buffered;
end
```

**Issue:** This creates a combinational loop (`instr_buffered = instr_buffered`). This appears to be a typo and should likely be:
```verilog
always @(*) begin
    instr_buffered = instr_to_cpu;
end
```

Or simply use `instr_to_cpu` directly without the intermediate signal.

---

### 9. Cache Statistics

**File:** `rtl/icache_nway_multiword.v`

The cache provides statistics outputs:
```verilog
output reg cache_hit,
output reg cache_miss,
output reg cache_evict
```

These are connected to debug outputs in `top.v` but pulsed only for one cycle. For accurate statistics, these should be connected to counters.

---

### 10. MEM_WB Store-Load Hazard Inputs Unused

**File:** `rtl/pipeline_stages/MEM_WB.v`

The module has inputs for store-load hazard handling:
```verilog
input wire store_load_hazard,
input wire [31:0] store_data,
```

But these are declared and never used in the always block - the `mem_data_out` just passes through `mem_data_in`:
```verilog
mem_data_out <= mem_data_in;
```

The store-load forwarding appears to happen in memory_unit.v instead:
```verilog
assign load_data_out = buffer_forward_valid ? buffer_forward_data : mem_read_data;
```

---

## Architecture Comparison with feature/icache-integration

| Feature | timing_fix | feature/icache-integration |
|---------|------------|---------------------------|
| **Valid bits in pipeline** | ✅ Yes - explicit valid propagation | ❌ No - relies on stall/flush only |
| **Store buffer** | ✅ Yes - 1 entry with forwarding | ❌ No - direct memory writes |
| **Burst controller** | ✅ Yes - separate module | ❌ No - cache handles directly |
| **Cache parameters** | ✅ More configurable (SIZE, ASSOC, BLOCK) | ⚠️ Less configurable |
| **Register file reset** | ❌ Missing | ✅ Proper rst input |
| **ALU SLT bug** | ❌ Has bug | ✅ Fixed |
| **FENCE.I support** | ❌ Incomplete | ✅ Full cache invalidation |
| **Branch flush priority** | ⚠️ Needs verification | ✅ Verified working |
| **Store byte alignment** | ❌ Has bug | ⚠️ Not verified |
| **Pipeline control style** | Enable-based (positive logic) | Stall-based (negative logic) |

---

## What timing_fix Does Better

### 1. Valid Bit Architecture
The timing_fix branch implements explicit valid bits throughout the pipeline. This is a more robust design because:
- Each instruction carries its own validity status
- Invalid instructions (bubbles) are explicitly marked
- Prevents accidental side effects from bubble instructions
- Easier to debug - can trace valid bit through pipeline
- Industry standard practice in production processors

**Example flow:**
```
IF_ID.valid_out → ID_EX.valid_in → ID_EX.valid_out → EX_MEM.valid_in → ...
```

### 2. Store Buffer
The store buffer decouples stores from the memory interface:
- Allows store-to-load forwarding (performance improvement)
- Reduces structural hazards on memory port
- Foundation for more advanced memory optimizations
- Standard feature in modern processors

### 3. Burst Controller Modularity
Separating the burst controller from the cache:
- Better separation of concerns
- Easier to test each component independently
- Can swap burst controller implementations
- Cleaner interfaces between modules

### 4. Parameterized Cache Design
More configuration options:
```verilog
parameter CACHE_SIZE    = 1024,
parameter ASSOCIATIVITY = 4,
parameter BLOCK_SIZE    = 8
```
- Easier design space exploration
- Can tune for different use cases (area vs performance)
- Better for academic/learning purposes

### 5. Enable-Based Pipeline Control
Using `enable` signals instead of `stall`:
- Positive logic is often clearer to reason about
- `enable=1` means "advance", `enable=0` means "hold"
- Consistent with valid bit paradigm
- Common in industry designs

### 6. Load-Use Stall Export
```verilog
output wire load_use_stall_out
```
- Cache can see when pipeline is stalled for hazards
- Prevents unnecessary cache state changes during stalls
- Better power efficiency potential

### 7. Explicit Stall Combination
```verilog
assign pc_stall = cache_stall || load_use_stall;
```
- Clear visibility of all stall sources
- Easier to add new stall conditions
- Better for debugging and verification

### 8. Memory Unit Restructuring
The memory unit now interfaces with the store buffer:
- Cleaner separation between load and store paths
- Store capture logic is explicit
- Load forwarding from buffer is handled properly

---

## Summary

The `timing_fix` branch has a more sophisticated and industry-standard architecture with:
- Valid bits propagating through pipeline stages
- Store buffer for decoupled memory writes
- Burst controller as separate module
- More parameterized and configurable cache

However, it has critical bugs that need to be fixed:
1. ALU SLT/SLTU returns wrong values
2. Store byte/halfword alignment is broken
3. Register file has no hardware reset
4. FENCE.I doesn't invalidate cache

The `feature/icache-integration` branch has fewer architectural features but has the fundamental bugs fixed.

**Recommendation:** Consider merging the architectural improvements from `timing_fix` with the bug fixes from `feature/icache-integration` to get the best of both branches.
