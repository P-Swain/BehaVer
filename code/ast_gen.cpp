#include <cstdlib>
#include <iostream>
#include "tinyxml2.h" // TinyXML-2 library for XML parsing

bool runVerilatorAST(const std::string &verilogFile, const std::string
                                                         &astXmlFile)
{
    // Build Verilator command
    2 std::string cmd = "verilator --xml-only --xml-output ";
    cmd += astXmlFile + " " + verilogFile;
    // Add options to suppress certain warnings and ensure single-thread
execution for simplicity
cmd += " -Wno-fatal";
// Execute the command
int ret = std::system(cmd.c_str());
if (ret != 0)
{
    std::cerr << "Verilator failed with exit code " << ret << std::endl;
    return false;
}
return true;
}
tinyxml2::XMLDocument astDoc;
if (runVerilatorAST("design.v", "ast.xml"))
{
    tinyxml2::XMLError xmlErr = astDoc.LoadFile("ast.xml");
    if (xmlErr != tinyxml2::XML_SUCCESS)
    {
        std::cerr << "Error: could not load AST XML (error " << xmlErr << ")
\n ";
            return 1;
    }
}
else
{
    return 1; // Verilator failed
}