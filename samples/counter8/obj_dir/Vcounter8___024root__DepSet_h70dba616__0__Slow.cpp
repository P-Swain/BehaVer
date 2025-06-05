// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vcounter8.h for the primary calling header

#include "Vcounter8__pch.h"
#include "Vcounter8___024root.h"

VL_ATTR_COLD void Vcounter8___024root___eval_static(Vcounter8___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vcounter8___024root___eval_static\n"); );
    Vcounter8__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

VL_ATTR_COLD void Vcounter8___024root___eval_initial(Vcounter8___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vcounter8___024root___eval_initial\n"); );
    Vcounter8__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__Vtrigprevexpr___TOP__clk__0 = vlSelfRef.clk;
    vlSelfRef.__Vtrigprevexpr___TOP__rst_n__0 = vlSelfRef.rst_n;
}

VL_ATTR_COLD void Vcounter8___024root___eval_final(Vcounter8___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vcounter8___024root___eval_final\n"); );
    Vcounter8__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

VL_ATTR_COLD void Vcounter8___024root___eval_settle(Vcounter8___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vcounter8___024root___eval_settle\n"); );
    Vcounter8__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vcounter8___024root___dump_triggers__act(Vcounter8___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vcounter8___024root___dump_triggers__act\n"); );
    Vcounter8__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VactTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 0 is active: @(posedge clk)\n");
    }
    if ((2ULL & vlSelfRef.__VactTriggered.word(0U))) {
        VL_DBG_MSGF("         'act' region trigger index 1 is active: @(negedge rst_n)\n");
    }
}
#endif  // VL_DEBUG

#ifdef VL_DEBUG
VL_ATTR_COLD void Vcounter8___024root___dump_triggers__nba(Vcounter8___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vcounter8___024root___dump_triggers__nba\n"); );
    Vcounter8__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1U & (~ vlSelfRef.__VnbaTriggered.any()))) {
        VL_DBG_MSGF("         No triggers active\n");
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 0 is active: @(posedge clk)\n");
    }
    if ((2ULL & vlSelfRef.__VnbaTriggered.word(0U))) {
        VL_DBG_MSGF("         'nba' region trigger index 1 is active: @(negedge rst_n)\n");
    }
}
#endif  // VL_DEBUG

VL_ATTR_COLD void Vcounter8___024root___ctor_var_reset(Vcounter8___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vcounter8___024root___ctor_var_reset\n"); );
    Vcounter8__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelf->clk = VL_RAND_RESET_I(1);
    vlSelf->rst_n = VL_RAND_RESET_I(1);
    vlSelf->out = VL_RAND_RESET_I(8);
    vlSelf->__Vtrigprevexpr___TOP__clk__0 = VL_RAND_RESET_I(1);
    vlSelf->__Vtrigprevexpr___TOP__rst_n__0 = VL_RAND_RESET_I(1);
}
