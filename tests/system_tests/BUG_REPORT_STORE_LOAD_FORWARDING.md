# Bug Report: Store-to-Load Forwarding Issues

**Date:** 2025-12-22
**Status:** Partially Fixed (3/8 tests passing)

## Summary

The Synapse-32 RISC-V CPU has critical bugs in its store-to-load forwarding implementation that cause memory operations to return incorrect values when a load immediately follows a store to the same address.

## Discovered By

Comprehensive memory forwarding test suite (`test_memory_forwarding.py`) created to test:
- Back-to-back SW→LW, SB→LB, SH→LH operations
- Byte/halfword enables
- Memory addressing
- Store-load chains

## Bug #1: Wrong Data Source for Forwarding (FIXED ✅)

**File:** `rtl/riscv_cpu.v:417`

**Symptom:** All back-to-back store→load operations returned 0 instead of the stored value.

**Root Cause:** The `store_load_detector` was using the LOAD instruction's rs2 value instead of the STORE instruction's rs2 value for forwarding.

**Fix Applied:**
```verilog
// BEFORE (WRONG):
.rs2_value(ex_mem_inst0_rs2_value_out)  // This is the LOAD's rs2

// AFTER (FIXED):
.rs2_value(mem_wb_inst0_rs2_value_out)  // This is the STORE's rs2 from WB stage
```

**Result:** Basic SW→LW forwarding now works (test_store_load_forwarding_word PASSING ✅)

---

## Bug #2: Missing Sign Extension in Forwarding (OPEN ❌)

**File:** `rtl/pipeline_stages/store_load_detector.v`

**Symptom:**
- `SB x1, 0(x10)` where x1=0x80 (negative byte)
- `LB x2, 0(x10)` immediately after
- Expected: x2=0xFFFFFF80 (sign-extended)
- Actual: x2=0x80 (not sign-extended)

**Root Cause:** The `store_load_detector` forwards raw rs2_value without considering load instruction type:
```verilog
assign forwarded_data = store_load_hazard ? rs2_value : 32'b0;
```

**Required Fix:** Implement sign extension logic based on load instruction type:
- LB: Sign-extend bits [7:0]
- LH: Sign-extend bits [15:0]
- LBU: Zero-extend bits [7:0]
- LHU: Zero-extend bits [15:0]
- LW: Use full 32 bits

**Impact:**
- `test_store_load_forwarding_byte` - FAILING (x4=128 instead of 0xFFFFFF80)
- `test_store_load_forwarding_halfword` - FAILING (x4=32768 instead of 0xFFFF8000)

---

## Bug #3: Partial Store Followed by Full Load (OPEN ❌)

**File:** `rtl/pipeline_stages/store_load_detector.v`

**Symptom:**
- Memory initialized to 0xDEADBEEF
- `SB x1, 0(x10)` where x1=0x42 (store byte 0 only)
- `LW x2, 0(x10)` immediately after
- Expected: x2=0xDEADBE42 (only byte 0 modified)
- Actual: x2=0x42 (entire word replaced)

**Root Cause:** When forwarding, the detector doesn't merge partial stores with existing memory data. It just forwards the full rs2 value.

**Required Fix:**
- Detect partial store (SB/SH) followed by full load (LW)
- Read existing memory value
- Merge stored bytes with existing bytes
- Forward merged result

**Impact:**
- `test_byte_enables` - FAILING (x2=66 instead of 0xDEADBE42)
- `test_halfword_enables` - FAILING (x2=291 instead of 0xDEAD0123)

---

## Bug #4: Store-Load Chain Incorrect Sum (OPEN ❌)

**File:** Unknown (possibly memory read timing or additional forwarding issues)

**Symptom:**
```
Store: MEM[0]=1, MEM[4]=2, MEM[8]=3, MEM[12]=4
Load and sum:
  LW x1, 0(x10)   → x1=1 ✓
  ADD x5, x5, x1  → sum=1
  LW x2, 4(x10)   → x2=2 ✓
  ADD x5, x5, x2  → sum=3
  LW x3, 8(x10)   → x3=3 ✓
  ADD x5, x5, x3  → sum=6
  LW x4, 12(x10)  → x4=4 ✓
  ADD x5, x5, x4  → sum=10 (expected)

Actual result: x5=6 instead of 10
```

**Root Cause:** Unknown. Possible causes:
1. Data memory read timing issue
2. ADD forwarding issue with load results
3. Pipeline stall not handled correctly during load-use
4. Store values not actually written to memory correctly

**Investigation Needed:**
- Check if stores actually write to data_mem
- Verify load-use hazard detection
- Check data forwarding from loads to ALU

**Impact:**
- `test_store_load_chain` - FAILING (critical test showing sum=6 instead of 10)

---

## Test Results Summary

### Before Fix: 1/8 PASSING
- Only `test_memory_addressing` passed (stores/loads with delays between them)
- All forwarding tests failed (values returned 0)

### After Bug #1 Fix: 3/8 PASSING ✅
- ✅ `test_store_load_forwarding_word` - Basic SW→LW works
- ✅ `test_multiple_stores_same_address` - Multiple SW→LW works
- ✅ `test_memory_addressing` - Basic memory operations work
- ❌ `test_store_load_forwarding_byte` - Sign extension broken
- ❌ `test_store_load_forwarding_halfword` - Sign extension broken
- ❌ `test_byte_enables` - Partial store merging broken
- ❌ `test_halfword_enables` - Partial store merging broken
- ❌ `test_store_load_chain` - **Critical: Sum calculation wrong**

---

## Recommended Next Steps

1. **Immediate Priority:** Fix Bug #4 (store-load chain sum issue)
   - This is blocking correct program execution
   - May indicate a more fundamental issue

2. **High Priority:** Fix Bug #2 (sign extension)
   - Required for correct LB/LH/LBU/LHU operation
   - Relatively straightforward fix

3. **Medium Priority:** Fix Bug #3 (partial store merging)
   - Less common use case
   - More complex implementation

---

## Files Involved

- `rtl/riscv_cpu.v` - Main CPU, instantiates store_load_detector
- `rtl/pipeline_stages/store_load_detector.v` - Forwarding logic (needs sign extension)
- `rtl/pipeline_stages/MEM_WB.v` - Forwards data when hazard detected
- `rtl/data_mem.v` - Data memory (may need investigation for Bug #4)
- `tests/system_tests/test_memory_forwarding.py` - Comprehensive test suite

---

## Test Command

```bash
cd /home/shashvat/cursor/synapse32/tests/system_tests
source ../.venv/bin/activate
pytest test_memory_forwarding.py::runCocotbTests -v
```

---

## Impact on Previously Passing Tests

**Question:** Do the existing 44/44 tests still pass?

The previous tests likely didn't catch this because they may have had delays between stores and loads (allowing memory to settle), or didn't test immediate back-to-back store→load sequences. The memory-intensive test in `test_full_integration.py` might also be affected.

**Action Required:** Re-run all integration tests to verify no regressions.
