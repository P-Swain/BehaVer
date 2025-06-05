// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vcounter8.h for the primary calling header

#include "Vcounter8__pch.h"
#include "Vcounter8__Syms.h"
#include "Vcounter8___024root.h"

void Vcounter8___024root___ctor_var_reset(Vcounter8___024root* vlSelf);

Vcounter8___024root::Vcounter8___024root(Vcounter8__Syms* symsp, const char* v__name)
    : VerilatedModule{v__name}
    , vlSymsp{symsp}
 {
    // Reset structure values
    Vcounter8___024root___ctor_var_reset(this);
}

void Vcounter8___024root::__Vconfigure(bool first) {
    (void)first;  // Prevent unused variable warning
}

Vcounter8___024root::~Vcounter8___024root() {
}
