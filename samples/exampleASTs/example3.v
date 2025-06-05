// example4.v
module arithmetic (
  input  wire [7:0] a,
  input  wire [7:0] b,
  output wire [7:0] sum,
  output wire [7:0] diff
);
  // use functions for combinational logic
  assign sum  = add(a, b);
  assign diff = sub(a, b);

  // function to add two bytes
  function [7:0] add;
    input [7:0] x, y;
    begin
      add = x + y;
    end
  endfunction

  // function to subtract two bytes
  function [7:0] sub;
    input [7:0] x, y;
    begin
      sub = x - y;
    end
  endfunction

  // task to display a value
  task display_val;
    input [7:0] val;
    begin
      $display("Value = %0d", val);
    end
  endtask
endmodule
