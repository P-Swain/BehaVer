// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vcounter8.h for the primary calling header

#ifndef VERILATED_VCOUNTER8___024ROOT_H_
#define VERILATED_VCOUNTER8___024ROOT_H_  // guard

#include "verilated.h"


class Vcounter8__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vcounter8___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    VL_IN8(clk,0,0);
    VL_IN8(rst_n,0,0);
    VL_OUT8(out,7,0);
    CData/*0:0*/ __Vtrigprevexpr___TOP__clk__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__rst_n__0;
    CData/*0:0*/ __VactContinue;
    IData/*31:0*/ __VactIterCount;
    VlTriggerVec<2> __VactTriggered;
    VlTriggerVec<2> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vcounter8__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vcounter8___024root(Vcounter8__Syms* symsp, const char* v__name);
    ~Vcounter8___024root();
    VL_UNCOPYABLE(Vcounter8___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard
