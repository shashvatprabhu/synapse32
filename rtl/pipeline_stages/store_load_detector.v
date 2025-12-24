`default_nettype none
`include "instr_defines.vh"

// Store-load hazard detector and forwarding unit
//
// This module detects when a load immediately follows a store to the same
// address and, when safe, forwards the store data to the load result.
//
// Design goals:
// - RISC-V compliant: a load must see the most recent store to that address.
// - Correct sign/zero extension for LB/LBU/LH/LHU/LW.
// - Scalable and simple: avoid complex partial-store merging by only
//   forwarding when store/load widths are compatible (Option 1 in docs).
module store_load_detector (
    // Current load instruction (in MEM stage)
    input  wire [5:0] load_instr_id,
    input  wire [31:0] load_addr,

    // Previous store instruction (in WB stage)
    input  wire [5:0] prev_store_instr_id,
    input  wire [31:0] prev_store_addr,
    input  wire [31:0] rs2_value, // Source data of the store (rs2)

    // Output signals
    output wire        store_load_hazard,
    output wire [31:0] forwarded_data
);

    // Detect if current instruction is a load
    wire is_load = (load_instr_id == INSTR_LB)  ||
                   (load_instr_id == INSTR_LH)  ||
                   (load_instr_id == INSTR_LW)  ||
                   (load_instr_id == INSTR_LBU) ||
                   (load_instr_id == INSTR_LHU);

    // Detect if previous instruction was a store
    wire is_store = (prev_store_instr_id == INSTR_SB) ||
                    (prev_store_instr_id == INSTR_SH) ||
                    (prev_store_instr_id == INSTR_SW);

    // Check if addresses match (byte-addressed)
    wire addr_match = (load_addr == prev_store_addr);

    // Only forward when store and load types are width-compatible.
    // This avoids having to merge partial stores with existing memory data
    // (e.g., SB -> LW), which would require reading and combining bytes.
    wire byte_match =
        ((load_instr_id == INSTR_LB)  || (load_instr_id == INSTR_LBU)) &&
        (prev_store_instr_id == INSTR_SB);

    wire halfword_match =
        ((load_instr_id == INSTR_LH)  || (load_instr_id == INSTR_LHU)) &&
        (prev_store_instr_id == INSTR_SH);

    wire word_match =
        (load_instr_id == INSTR_LW) &&
        (prev_store_instr_id == INSTR_SW);

    wire type_match = byte_match || halfword_match || word_match;

    // Signal hazard ONLY when:
    // - current instr is a load
    // - previous instr was a store
    // - addresses match
    // - types are width-compatible (so forwarding is semantically safe)
    assign store_load_hazard = is_load && is_store && addr_match && type_match;

    // Extract byte and halfword views of the store data
    wire [7:0]  byte_data     = rs2_value[7:0];
    wire [15:0] halfword_data = rs2_value[15:0];

    // Forward data with the same sign/zero extension behavior as data_mem.v
    assign forwarded_data = store_load_hazard ? (
        (load_instr_id == INSTR_LB)  ? {{24{byte_data[7]}},     byte_data}      : // Sign-extend byte
        (load_instr_id == INSTR_LBU) ? {24'h0,                 byte_data}      : // Zero-extend byte
        (load_instr_id == INSTR_LH)  ? {{16{halfword_data[15]}}, halfword_data} : // Sign-extend halfword
        (load_instr_id == INSTR_LHU) ? {16'h0,                 halfword_data}  : // Zero-extend halfword
        (load_instr_id == INSTR_LW)  ? rs2_value                                   // Full word
                                     : 32'h0
    ) : 32'h0;

endmodule
