module counter8(
    input  logic clk,
    input  logic rst_n,
    output logic [7:0] out
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) out <= 0;
        else        out <= out + 1;
    end
endmodule
