// example2.v
module sync_counter (
  input  wire        clk,
  input  wire        rst_n,
  output reg [3:0]   count
);
  // on rising edge or async reset
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      count <= 4'b0000;
    else
      count <= count + 1;
  end
endmodule
