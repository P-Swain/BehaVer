// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vcounter8.h for the primary calling header

#include "Vcounter8__pch.h"
#include "Vcounter8__Syms.h"
#include "Vcounter8___024root.h"

#ifdef VL_DEBUG
VL_ATTR_COLD void Vcounter8___024root___dump_triggers__act(Vcounter8___024root* vlSelf);
#endif  // VL_DEBUG

void Vcounter8___024root___eval_triggers__act(Vcounter8___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vcounter8___024root___eval_triggers__act\n"); );
    Vcounter8__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VactTriggered.set(0U, ((IData)(vlSelfRef.clk) 
                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__clk__0))));
    vlSelfRef.__VactTriggered.set(1U, ((~ (IData)(vlSelfRef.rst_n)) 
                                       & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__rst_n__0)));
    vlSelfRef.__Vtrigprevexpr___TOP__clk__0 = vlSelfRef.clk;
    vlSelfRef.__Vtrigprevexpr___TOP__rst_n__0 = vlSelfRef.rst_n;
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vcounter8___024root___dump_triggers__act(vlSelf);
    }
#endif
}
