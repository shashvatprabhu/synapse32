`timescale 1ns/1ps
`default_nettype none

module IF_ID(
    input wire clk,
    input wire rst,
    input wire [31:0] pc_in,
    input wire [31:0] instruction_in,
    input wire enable,                 // INDUSTRY STANDARD: Enable signal for stalls
    input wire valid_in,
    output reg [31:0] pc_out,
    output reg [31:0] instruction_out,
    output reg valid_out
);

// TIMING FIX: Sample on negedge to allow PC and cache to settle after posedge
always @(negedge clk or posedge rst) begin
    if (rst) begin
        pc_out <= 32'b0;
        instruction_out <= 32'b0;
        valid_out <= 1'b0;
    end else if (enable) begin
        pc_out <= pc_in;
        instruction_out <= instruction_in;
        valid_out <= valid_in;

        // DEBUG: Track SW x8, 16(x4) - opcode 0x00822823
        if (instruction_in == 32'h00822823) begin
            $display("[IF_ID] @%t: SW x8,16(x4) ENTERED PIPELINE PC=0x%h valid=%b enable=%b",
                     $time, pc_in, valid_in, enable);
        end
        // DEBUG: Track ALL instructions at PC=0xD4
        if (pc_in == 32'h000000D4 || pc_in == 32'h000000d4) begin
            $display("[IF_ID] @%t: PC=0xD4 instruction=0x%h valid=%b enable=%b",
                     $time, instruction_in, valid_in, enable);
        end
    end
    // else hold all values (stalled)
end

endmodule