# Synapse-32 CPU Verification TODO List

This document tracks verification gaps and improvement tasks for the Synapse-32 RISC-V CPU.

**Created:** December 21, 2025
**Status:** Work in Progress
**Priority:** High → Medium → Low

---

## 🔴 HIGH PRIORITY - Test Suite Fixes

### 1. Fix Unit Test Expectations (SLT/SLTU Bug)
**File:** `tests/unit_tests/test_alu.py`
**Issue:** Tests expect SLT/SLTU to return `0xFFFFFFFF` when true, but ALU correctly returns `1` per RISC-V spec
**Lines:** 96, 102, 104, 137, 142, 144, 185-187, 206, 208

**Fix Required:**
```python
# WRONG (current):
await verify_alu_operation(dut, 10, 20, 0, 0x9, 0, 0xFFFFFFFF, "SLT true")

# CORRECT (should be):
await verify_alu_operation(dut, 10, 20, 0, 0x9, 0, 0x00000001, "SLT true")
```

**Impact:** 3 unit tests failing (test_comparisons, test_immediate_operations, test_random_inputs)

**Effort:** 30 minutes

---

### 2. Fix Fibonacci C Compilation Test
**File:** `tests/system_tests/test_fibonacci.py`
**Issue:** Test tries to compile C code but fails with "stdlib.h: No such file or directory"
**Root Cause:** Missing RISC-V GCC sysroot or incorrect compiler flags

**Options:**
- A) Remove `#include <stdlib.h>` if not needed
- B) Use `-nostdlib -ffreestanding` flags properly
- C) Provide minimal libc stubs

**Effort:** 1-2 hours (depends on approach)

---

### 3. Verify All Integration Tests Actually Pass
**Task:** Run full integration test suite and capture actual results

**Command:**
```bash
cd tests
source .venv/bin/activate
pytest system_tests/test_full_integration.py -v --tb=short > integration_results.txt 2>&1
```

**Need to verify:**
- All 29 tests in test_full_integration.py
- CSR tests
- ICache tests
- Basic CPU tests

**Effort:** 30 minutes

---

## 🟡 MEDIUM PRIORITY - Error Condition Tests

### 4. Test Invalid/Illegal Instructions
**What to test:**
```verilog
- Undefined opcodes (e.g., 0xFFFFFFFF)
- Valid opcode with invalid funct3/funct7 combination
- Reserved instruction encodings
```

**Expected behavior:**
- CPU should trap to exception handler
- `mcause` CSR should indicate illegal instruction
- PC should jump to `mtvec`

**Current behavior:** Unknown (no tests exist)

**Test to create:** `tests/system_tests/test_exceptions.py`

**Effort:** 3-4 hours

---

### 5. Test Misaligned Memory Access
**What to test:**
```verilog
LW x1, x10, 1    // Load word from misaligned address (should be 4-byte aligned)
LH x2, x10, 1    // Load halfword from odd address (should be 2-byte aligned)
SW x10, x1, 2    // Store word to misaligned address
```

**Expected behavior (per RISC-V spec):**
- Option A: Raise misaligned address exception
- Option B: Support misaligned access (slower but allowed)

**Current behavior:** Unknown

**Need to check:** Does the memory unit detect misalignment?

**Effort:** 2-3 hours

---

### 6. Test Access to Unmapped Memory Regions
**What to test:**
```verilog
LW x1, x10, 0    // where x10 = 0x50000000 (unmapped region)
SW x10, x1, 0    // Write to unmapped region
```

**Memory map:**
- Instruction: 0x00000000 - 0x0007FFFF
- Data: 0x10000000 - 0x100FFFFF
- Timer: 0x02004000 - 0x02004007
- UART: 0x20000000 - 0x20000003

**Expected:** Access to 0x50000000 should trap or return bus error

**Effort:** 2 hours

---

### 7. Test CSR Permission Violations
**What to test:**
```verilog
// Try to write to read-only CSR
CSRRW x1, x2, cycle    // cycle (0xC00) is read-only

// Try to access privileged CSR from user mode (if modes implemented)
```

**Expected:** Should trap to exception handler

**Effort:** 1-2 hours

---

## 🟡 MEDIUM PRIORITY - Edge Case Tests

### 8. Test Maximum Cache Thrashing
**Scenario:** Access addresses that all map to the same cache set

**Example:**
```c
// Cache has 64 sets, 4 ways
// Access 5+ addresses that map to set 0 (every 64*16 bytes = 1024 bytes)
addr[0] = 0x00000000
addr[1] = 0x00000400  // +1024 bytes
addr[2] = 0x00000800  // +2048 bytes
addr[3] = 0x00000C00  // +3072 bytes
addr[4] = 0x00001000  // +4096 bytes (5th way, forces eviction)
```

**Expected:** Should still work correctly, just with more misses

**Test:** `tests/system_tests/test_cache_stress.py`

**Effort:** 2-3 hours

---

### 9. Test Simultaneous Hazards
**Scenario:** Cache miss + load-use hazard + branch taken all at once

**Example:**
```verilog
// Assume cache is cold
LW x1, x10, 0        // Cache miss (long stall) + loads data
ADD x2, x1, x1       // Load-use hazard (needs stall)
BEQ x2, x3, target   // Branch taken (pipeline flush)
```

**Expected:** All hazards handled correctly in combination

**Effort:** 2-3 hours

---

### 10. Test Back-to-Back Interrupts
**Scenario:** Interrupt arrives while handling previous interrupt

**Test file exists:** `tests/system_tests/test_interrupts.py`

**Need to verify:**
- Nested interrupt handling
- Interrupt masking (mstatus.MIE)
- Priority handling (timer vs external vs software)

**Effort:** 2 hours

---

### 11. Test All 32 Registers Simultaneously
**Scenario:** Use all registers (x0-x31) in a program

**Example:**
```verilog
ADDI x1, x0, 1
ADDI x2, x0, 2
ADDI x3, x0, 3
...
ADDI x31, x0, 31
ADD x1, x1, x2
ADD x3, x3, x4
...
// Verify all registers hold correct values
```

**Expected:** All 32 registers work independently

**Effort:** 1 hour

---

## 🟢 LOW PRIORITY - Stress & Advanced Tests

### 12. Long-Running Program Test
**Goal:** Run a program with 1000+ instructions

**Example program:**
```c
int sum = 0;
for (int i = 0; i < 100; i++) {
    for (int j = 0; j < 10; j++) {
        sum += i * j;
    }
}
// Should execute ~1000+ instructions
```

**Verifies:**
- CPU doesn't hang
- No state corruption over time
- Pipeline remains functional

**Effort:** 2-3 hours

---

### 13. Random Instruction Generator
**Goal:** Generate random valid RISC-V instruction sequences

**Approach:**
```python
def generate_random_instruction():
    opcode = random.choice([0x33, 0x13, 0x03, 0x23, 0x63, 0x6F, 0x67])
    rd = random.randint(1, 31)
    rs1 = random.randint(0, 31)
    rs2 = random.randint(0, 31)
    # Encode based on opcode...
    return instruction

# Generate 100 random instructions
# Run on CPU
# Check: no hangs, no crashes, registers have some values
```

**This is NOT golden model comparison**, just "doesn't break" testing

**Effort:** 4-6 hours

---

### 14. Memory-Intensive Workload Test
**Goal:** Heavy load/store traffic

**Example:**
```c
int array[256];
for (int i = 0; i < 256; i++) {
    array[i] = i;
}
for (int i = 0; i < 256; i++) {
    array[i] = array[i] * 2;
}
int sum = 0;
for (int i = 0; i < 256; i++) {
    sum += array[i];
}
```

**Verifies:**
- Data memory works with many accesses
- No corruption over time
- Load-use hazards handled repeatedly

**Effort:** 2-3 hours

---

### 15. Worst-Case Cache Behavior
**Scenarios:**
```verilog
A) Every instruction is a cache miss (sequential through large program)
B) Alternating between two cache sets (ping-pong)
C) FENCE.I on every 10th instruction (constant invalidation)
```

**Expected:** Slow but correct execution

**Effort:** 2-3 hours

---

## 🔵 ADVANCED - Formal Verification & Compliance

### 16. RISC-V Compliance Test Suite
**Goal:** Run official RISC-V compliance tests

**Repository:** https://github.com/riscv-non-isa/riscv-arch-test

**Tests cover:**
- All RV32I instructions
- Edge cases per spec
- Official golden signatures

**Effort:** 8-12 hours (setup + debug)

---

### 17. Assertion-Based Verification
**Goal:** Add SystemVerilog assertions to RTL

**Examples:**
```systemverilog
// Check: x0 always reads as 0
assert property (@(posedge clk) (rf_rs1_addr == 0) |-> (rf_rs1_data == 0));

// Check: PC increment by 4 when no branch
assert property (@(posedge clk) (!branch_taken) |-> (pc_next == pc + 4));

// Check: No writes during stall
assert property (@(posedge clk) (stall) |-> (!reg_write_en));
```

**Tools needed:** Verilator with assertions, or Questa/VCS

**Effort:** 12-16 hours

---

### 18. Coverage-Driven Verification
**Goal:** Measure what % of design is tested

**Metrics:**
- Line coverage (which lines of Verilog executed)
- Branch coverage (which if/else paths taken)
- Toggle coverage (which signals toggled)
- FSM coverage (which states visited)

**Tools:** Verilator `--coverage`, or commercial tools

**Effort:** 6-8 hours

---

## 📊 Summary

| Priority | Category | Tasks | Est. Effort |
|----------|----------|-------|-------------|
| 🔴 High | Test Fixes | 3 | 2-3 hours |
| 🟡 Medium | Error Conditions | 4 | 10-12 hours |
| 🟡 Medium | Edge Cases | 4 | 8-10 hours |
| 🟢 Low | Stress Tests | 4 | 12-15 hours |
| 🔵 Advanced | Formal/Compliance | 3 | 26-36 hours |
| **TOTAL** | | **18 tasks** | **58-76 hours** |

---

## Recommended Order

**Week 1: Quick Wins (4-6 hours)**
1. Fix SLT/SLTU unit tests (30 min)
2. Verify integration tests pass (30 min)
3. Fix Fibonacci test (1-2 hours)
4. Test all 32 registers (1 hour)

**Week 2: Error Handling (10-12 hours)**
5. Illegal instruction test
6. Misaligned access test
7. Unmapped memory test
8. CSR permission test

**Week 3: Edge Cases (8-10 hours)**
9. Cache thrashing test
10. Simultaneous hazards test
11. Back-to-back interrupts
12. Long-running program

**Week 4: Stress Testing (12-15 hours)**
13. Random instruction generator
14. Memory-intensive workload
15. Worst-case cache behavior

**Future: Advanced (26-36 hours)**
16. RISC-V compliance suite
17. Assertion-based verification
18. Coverage measurement

---

## Current Status

- ✅ Integration tests: Likely passing (need verification)
- ❌ Unit tests: 3/8 failing (wrong expectations)
- ❌ Error condition tests: 0 tests exist
- ❌ Edge case tests: Minimal coverage
- ❌ Stress tests: None exist
- ❌ Formal verification: Not started

**Overall Test Maturity: ~40%**

---

## Notes

- Start with HIGH priority items - these are test suite bugs, not CPU bugs
- MEDIUM priority items may reveal actual CPU bugs
- LOW priority items are for robustness and confidence
- ADVANCED items are for production-level verification

**Question for you:** Which category do you want to tackle first?

1. Fix existing test bugs (quickest, high confidence boost)
2. Add error condition tests (find potential CPU bugs)
3. Add stress tests (ensure long-term reliability)
4. Run RISC-V compliance suite (gold standard validation)
