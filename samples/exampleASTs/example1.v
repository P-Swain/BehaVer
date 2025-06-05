// example1.v
module and_gate (
  input  wire a,
  input  wire b,
  output wire y
);
  // simple continuous assignment
  assign y = a & b;
endmodule
