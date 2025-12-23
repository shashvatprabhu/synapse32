`default_nettype none
`include "instr_defines.vh"

// Simple detector - just identifies if there's a potential store-load hazard
module store_load_detector (
    // Current load instruction
    input wire [5:0] load_instr_id,
    input wire [31:0] load_addr,

    // Previous store instruction
    input wire [5:0] prev_store_instr_id,
    input wire [31:0] prev_store_addr,

    // Output signals
    output wire store_load_hazard,
    output wire type_match
);

    // Detect if current instruction is a load
    wire is_load = (load_instr_id == INSTR_LB) || (load_instr_id == INSTR_LH) ||
                   (load_instr_id == INSTR_LW) || (load_instr_id == INSTR_LBU) ||
                   (load_instr_id == INSTR_LHU);

    // Detect if previous instruction was a store
    wire is_store = (prev_store_instr_id == INSTR_SB) || (prev_store_instr_id == INSTR_SH) ||
                    (prev_store_instr_id == INSTR_SW);

    // Check if addresses match
    wire addr_match = (load_addr == prev_store_addr);

    // Check if store type matches load type (Option 1)
    // Only forward when types are compatible to avoid complex merging logic
    wire byte_match =
        ((load_instr_id == INSTR_LB || load_instr_id == INSTR_LBU) &&
         prev_store_instr_id == INSTR_SB);

    wire halfword_match =
        ((load_instr_id == INSTR_LH || load_instr_id == INSTR_LHU) &&
         prev_store_instr_id == INSTR_SH);

    wire word_match =
        (load_instr_id == INSTR_LW && prev_store_instr_id == INSTR_SW);

    assign type_match = byte_match || halfword_match || word_match;

    // Signal hazard when: load + store + address match + type compatible
    // Mismatched types (e.g., SB->LW) will NOT signal hazard, forcing read from memory
    assign store_load_hazard = is_load && is_store && addr_match && type_match;

endmodule