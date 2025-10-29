module pc(
   input clk,
   input rst,
   input j_signal,
   input stall,         // Added stall input
   input [31:0] jump,
   output[31:0] out
);
   reg [31:0] next_pc = 32'd0;

    always @ (posedge clk) begin
        if(rst)
            next_pc <= 32'b0;
        else if(j_signal) begin
            next_pc <= jump;
            // DEBUG: Track jumps
            if (next_pc >= 32'hC0 && next_pc <= 32'hE0) begin
                $display("[PC] @%t: JUMP from PC=0x%h to PC=0x%h", $time, next_pc, jump);
            end
        end
        else if(stall) begin
            // If stalling, don't update PC
            next_pc <= next_pc;
        end
        else begin
            next_pc <= next_pc + 32'h4;
            // DEBUG: Track PC progression in our range of interest
            if (next_pc >= 32'hC0 && next_pc <= 32'hE0) begin
                $display("[PC] @%t: PC advancing from 0x%h to 0x%h (stall=%b j_signal=%b)",
                         $time, next_pc, next_pc + 32'h4, stall, j_signal);
            end
        end
    end

    assign out = next_pc;
endmodule
