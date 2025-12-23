# RISC-V Store-Load Forwarding: Standard Behavior vs Current Implementation

**Date:** 2025-12-22

## RISC-V Standard Behavior

### Load Instructions (from RISC-V Spec)

```
LB  rd, offset(rs1)  - Load Byte (sign-extended)
    - Read 8 bits from memory
    - Sign-extend bit[7] to fill bits[31:8]
    - Result: rd = {{24{mem[7]}}, mem[7:0]}

LBU rd, offset(rs1)  - Load Byte Unsigned (zero-extended)
    - Read 8 bits from memory
    - Zero-extend to 32 bits
    - Result: rd = {24'h0, mem[7:0]}

LH  rd, offset(rs1)  - Load Halfword (sign-extended)
    - Read 16 bits from memory (must be 2-byte aligned)
    - Sign-extend bit[15] to fill bits[31:16]
    - Result: rd = {{16{mem[15]}}, mem[15:0]}

LHU rd, offset(rs1)  - Load Halfword Unsigned (zero-extended)
    - Read 16 bits from memory
    - Zero-extend to 32 bits
    - Result: rd = {16'h0, mem[15:0]}

LW  rd, offset(rs1)  - Load Word
    - Read 32 bits from memory (must be 4-byte aligned)
    - Result: rd = mem[31:0]
```

### Store Instructions

```
SB  rs2, offset(rs1)  - Store Byte
    - Write rs2[7:0] to memory address
    - Upper 24 bits of rs2 are ignored
    - Only modifies 1 byte in memory

SH  rs2, offset(rs1)  - Store Halfword
    - Write rs2[15:0] to memory address (must be 2-byte aligned)
    - Upper 16 bits of rs2 are ignored
    - Only modifies 2 bytes in memory

SW  rs2, offset(rs1)  - Store Word
    - Write rs2[31:0] to memory address (must be 4-byte aligned)
    - Modifies 4 bytes in memory
```

---

## Current Implementation

### Normal Load Path (WITHOUT forwarding)

**File:** `rtl/data_mem.v:57-62`

```verilog
assign rd_data_out = rd_en ? (
    (load_type == 3'b000) ? {{24{byte_data[7]}}, byte_data} :      // LB - sign-extend
    (load_type == 3'b100) ? {24'h0, byte_data} :                  // LBU - zero-extend
    (load_type == 3'b001) ? {{16{halfword_data[15]}}, halfword_data} : // LH - sign-extend
    (load_type == 3'b101) ? {16'h0, halfword_data} :              // LHU - zero-extend
    (load_type == 3'b010) ? word_data :                           // LW - full word
    32'h0
) : 32'h0;
```

**Status:** ✅ CORRECT - Implements proper sign/zero extension

### Store Path

**File:** `rtl/memory_unit.v:42-46`

```verilog
assign wr_data =
    (instr_id == INSTR_SB) ? {24'b0, rs2_value[7:0]} :   // Only write low byte
    (instr_id == INSTR_SH) ? {16'b0, rs2_value[15:0]} :  // Only write low halfword
    (instr_id == INSTR_SW) ? rs2_value :                 // Write full word
    32'b0;
```

**File:** `rtl/data_mem.v:66-79`

```verilog
always @(posedge clk) begin
    if (wr_en && (addr < MEM_SIZE)) begin
        if (write_byte_enable[0]) begin
            data_ram[addr] <= wr_data[7:0];      // Byte 0
        end
        if (write_byte_enable[1]) begin
            data_ram[addr+1] <= wr_data[15:8];   // Byte 1
        end
        if (write_byte_enable[2]) begin
            data_ram[addr+2] <= wr_data[23:16];  // Byte 2
        end
        if (write_byte_enable[3]) begin
            data_ram[addr+3] <= wr_data[31:24];  // Byte 3
        end
    end
end
```

**Status:** ✅ CORRECT - Implements proper partial writes

---

## Bug Analysis

### Bug #2: Sign Extension in Forwarding Path

**File:** `rtl/pipeline_stages/store_load_detector.v:34`

**Current Code:**
```verilog
assign forwarded_data = store_load_hazard ? rs2_value : 32'b0;
```

**Problem:** Forwards raw `rs2_value` without considering the **load instruction type**.

**Example Scenario:**
```assembly
ADDI x1, x0, 0x80       # x1 = 0x00000080
SB x1, 0(x10)           # Store: rs2_value = 0x00000080, writes byte 0x80
LB x2, 0(x10)           # Load with sign extension
```

**What happens:**
1. Store path: `rs2_value = 0x00000080`, writes `0x80` to memory ✅
2. Load path (forwarding): Gets `rs2_value = 0x00000080` directly ❌
3. **Expected:** `x2 = 0xFFFFFF80` (sign-extended)
4. **Actual:** `x2 = 0x00000080` (no sign extension)

**RISC-V Standard:** Load instruction determines sign extension, NOT the store!

**Solution:** The `store_load_detector` needs to know:
1. What type of LOAD is being executed (LB/LBU/LH/LHU/LW)
2. What type of STORE was executed (SB/SH/SW)
3. Apply the same sign/zero extension logic as `data_mem.v`

**Correct Implementation:**
```verilog
wire [7:0] byte_data = rs2_value[7:0];
wire [15:0] halfword_data = rs2_value[15:0];

assign forwarded_data = store_load_hazard ? (
    (load_instr_id == INSTR_LB)  ? {{24{byte_data[7]}}, byte_data} :
    (load_instr_id == INSTR_LBU) ? {24'h0, byte_data} :
    (load_instr_id == INSTR_LH)  ? {{16{halfword_data[15]}}, halfword_data} :
    (load_instr_id == INSTR_LHU) ? {16'h0, halfword_data} :
    (load_instr_id == INSTR_LW)  ? rs2_value :
    32'h0
) : 32'h0;
```

---

### Bug #3: Partial Store Followed by Full Load

**Problem:** When a partial store (SB/SH) is followed by a full load (LW), the forwarding path doesn't merge with existing memory data.

**Example Scenario:**
```assembly
# Memory initially: MEM[0x10000000] = 0xDEADBEEF
ADDI x1, x0, 0x42       # x1 = 0x42
SB x1, 0(x10)           # Store byte: modifies only byte 0
LW x2, 0(x10)           # Load word: should read all 4 bytes
```

**RISC-V Standard:**
- SB only modifies 1 byte: `MEM[addr] = 0x42`, rest unchanged
- LW reads all 4 bytes: should get `0xDEADBE42`

**Current Forwarding Behavior:**
- Forwards `rs2_value = 0x00000042` (the store's source value)
- Result: `x2 = 0x00000042` ❌

**What SHOULD happen:**
```
Before SB: MEM = [EF BE AD DE] (little-endian)
After SB:  MEM = [42 BE AD DE] (only byte 0 changed)
LW reads:  0xDEADBE42 ✅
```

**Solution Options:**

**Option 1: Don't Forward (Simple but causes stall)**
- Only forward when store type matches load type
- SB→LB: forward ✅
- SB→LW: don't forward, read from memory (requires stall)
- Trade-off: Simpler but slower

**Option 2: Merge with Memory (Complex but faster)**
- Read existing memory value
- Merge forwarded bytes with existing bytes
- Forward merged result
- Trade-off: Faster but more complex

**Option 3: Write-through + Delay (Medium)**
- Ensure store writes to memory immediately
- Add 1-cycle delay before load can read
- Load gets correct merged value from memory
- Trade-off: Simple, 1-cycle penalty

**RISC-V Standard:** Doesn't specify - forwarding is a microarchitectural optimization. All three options are valid as long as the **architectural state is correct**.

**Recommended:** Option 1 (don't forward mismatched types) for simplicity.

---

### Bug #4: Store-Load Chain Sum Incorrect

**Symptom:**
```assembly
# Store values
SW x1, 0(x10)   # MEM[0] = 1
SW x2, 4(x10)   # MEM[4] = 2
SW x3, 8(x10)   # MEM[8] = 3
SW x4, 12(x10)  # MEM[12] = 4

# Load and sum
LW x1, 0(x10)   # x1 = 1 ✓
ADD x5, x5, x1  # x5 = 1 ✓
LW x2, 4(x10)   # x2 = 2 ✓
ADD x5, x5, x2  # x5 = 3 ✓
LW x3, 8(x10)   # x3 = 3 ✓
ADD x5, x5, x3  # x5 = 6 ✓
LW x4, 12(x10)  # x4 = 4 ✓
ADD x5, x5, x4  # x5 = 10 (EXPECTED)

ACTUAL: x5 = 6 ❌
```

**Analysis:** The loads are reading correct values (x1=1, x2=2, x3=3, x4=4), but the sum is wrong.

**Hypothesis 1: ADD forwarding issue**
- Maybe the ADD result isn't being forwarded properly?
- Let me check: sum=1, sum=3, sum=6 suggests only first 3 ADDs work
- The 4th ADD (x5 + x4) doesn't seem to execute or gets overwritten

**Hypothesis 2: Pipeline flush during loads**
- Load-use hazards cause pipeline stalls
- Maybe a flush is happening incorrectly?

**Hypothesis 3: Writeback conflict**
- Multiple writes to x5?
- Timing issue with register writes?

**Investigation Needed:**
1. Check if all 4 ADDs actually execute
2. Verify data forwarding from MEM/WB to EX stage
3. Check register file write timing
4. Verify no spurious pipeline flushes

**This is the MOST CRITICAL bug** - it prevents correct program execution even for simple cases!

---

## Summary Table

| Bug | Location | RISC-V Standard | Current Behavior | Fix Complexity |
|-----|----------|-----------------|------------------|----------------|
| #2: Sign Extension | `store_load_detector.v` | Load type determines extension | No extension applied | Medium |
| #3: Partial Store→Full Load | `store_load_detector.v` | Load sees merged memory | Forwards only stored bytes | Medium-High |
| #4: Sum Chain Wrong | Unknown | Sum should be 10 | Sum is 6 | High (needs investigation) |

---

## RISC-V Compliance

According to the RISC-V specification:

**Memory Model:** RISC-V uses a weakly-ordered memory model (RVWMO), but for a single-threaded implementation:
- Loads and stores to the same address must appear to execute in program order
- A load must return the value of the most recent store to that address
- **Forwarding is allowed** as long as it maintains sequential consistency

**Key Point:** Store-to-load forwarding is a **performance optimization**, not a requirement. The implementation can choose to:
1. Always forward when safe (fastest)
2. Never forward, always read memory (simplest)
3. Sometimes forward (hybrid)

As long as the **architectural state is correct**, all approaches are valid.

---

## Recommendations

### Immediate Priority (Critical)

**Fix Bug #4 first** - Sum chain must work for basic programs to execute correctly.

### Fix Bug #2 (Sign Extension)

**Approach:** Reuse the same sign extension logic from `data_mem.v`

**Changes to `store_load_detector.v`:**
1. Add `load_instr_id` input
2. Implement sign/zero extension based on load type
3. Use `rs2_value` from store, but format it like a load would

### Fix Bug #3 (Partial Store Merging)

**Recommended Approach:** Don't forward when store/load types mismatch

**Changes to `store_load_detector.v`:**
1. Only assert `store_load_hazard` when:
   - Addresses match AND
   - Store type matches load type:
     - SB→LB/LBU: OK
     - SH→LH/LHU: OK
     - SW→LW: OK
     - SB→LW: NO (don't forward)
     - SH→LW: NO (don't forward)

This is RISC-V compliant - we just skip the optimization for mismatched types.
