`default_nettype none
`include "instr_defines.vh"

// Forwarding unit - handles actual data forwarding with sign/zero extension
module store_load_forward (
    // Load instruction type (determines sign/zero extension)
    input wire [5:0] load_instr_id,

    // Store data to forward
    input wire [31:0] store_data,

    // Control signal from detector
    input wire forward_enable,

    // Output
    output wire [31:0] forwarded_data
);

    // Extract byte and halfword data for sign/zero extension
    wire [7:0] byte_data = store_data[7:0];
    wire [15:0] halfword_data = store_data[15:0];

    // Forward data with proper sign/zero extension based on load type
    // This matches the behavior of data_mem.v for consistency
    assign forwarded_data = forward_enable ? (
        (load_instr_id == INSTR_LB)  ? {{24{byte_data[7]}}, byte_data} :      // Sign-extend byte
        (load_instr_id == INSTR_LBU) ? {24'h0, byte_data} :                   // Zero-extend byte
        (load_instr_id == INSTR_LH)  ? {{16{halfword_data[15]}}, halfword_data} : // Sign-extend halfword
        (load_instr_id == INSTR_LHU) ? {16'h0, halfword_data} :              // Zero-extend halfword
        (load_instr_id == INSTR_LW)  ? store_data :                          // Full word
        32'h0
    ) : 32'h0;

endmodule