#include "Vcounter8.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    Vcounter8* dut = new Vcounter8;
    VerilatedVcdC* tfp = nullptr;

    // Enable waveform tracing
    Verilated::traceEverOn(true);
    tfp = new VerilatedVcdC;
    dut->trace(tfp, 99);
    tfp->open("counter8.vcd");

    // initialize
    dut->rst_n = 0;
    dut->clk   = 0;
    dut->eval(); tfp->dump(0);

    // release reset
    dut->rst_n = 1;

    for (int tick = 1; tick <= 20; ++tick) {
        // toggle clock
        dut->clk = !dut->clk;
        dut->eval();
        tfp->dump(tick);
    }

    tfp->close();
    delete dut;
    delete tfp;
    return 0;
}
