#include "Vadder.h"
#include "verilated.h"

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    Vadder* dut = new Vadder;

    // Test all combinations of a and b = 0..3
    for (int a = 0; a < 4; ++a) {
        for (int b = 0; b < 4; ++b) {
            dut->a = a;
            dut->b = b;
            dut->eval();
            printf("a=%d, b=%d => sum=%d\n", a, b, dut->sum);
        }
    }

    delete dut;
    return 0;
}