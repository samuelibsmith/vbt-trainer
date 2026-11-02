#pragma once   
// Tells the compiler: if this file gets included twice, only read it once

// A "class" is a bundle of data + functions that belong together.
// This one is special: it has NO working code in it. It only lists
// the functions any spool sensor must provide. C++ calls this an
// abstract class; other languages call it an interface.
class SpoolSensor {
public:   // Everything below this line can be used by code outside the class

    // A "virtual" function is a placeholder. It says: "every sensor
    // will have a begin(), but each sensor writes its own version."
    // The "= 0" means there is deliberately no default version here,
    // so a class that forgets to write one will not compile.
    virtual void begin() = 0;

    // Returns total cord travel since begin(), in millimetres.
    // Positive = concentric direction (cord paying out under load).
    // "float" is the return type, the value this function hands back.
    virtual float displacementMM() = 0;

    // Returns the sensor's name as text, handy for Serial printouts.
    // "const char*" is how C++ writes "a string of characters".
    virtual const char* name() = 0;

    // Virtual destructor. When you delete an object through a
    // SpoolSensor pointer (see file 3), this makes sure the correct
    // cleanup code for the real sensor runs. Belt and braces for now.
    virtual ~SpoolSensor() {}
};
