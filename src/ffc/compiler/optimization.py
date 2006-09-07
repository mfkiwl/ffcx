__author__ = "Anders Logg (logg@simula.no)"
__date__ = "2006-03-22 -- 2006-09-07"
__copyright__ = "Copyright (C) 2006 Anders Logg"
__license__  = "GNU GPL Version 2"

# FFC common modules
from ffc.common.debug import *
from ffc.common.constants import *

# FFC compiler modules
from declaration import *

def optimize(terms, format):
    """Generate optimized abstract code for the tensor contraction from
    a given reference tensor"""

    debug("Computing optimization, this may take some time...")

    # Check if FErari is available
    try:
        from FErari import binary
    except:
        raise RuntimeError, "Cannot find FErari on your system, unable to optimize."

    # Create empty list of declarations
    declarations = []

    # We generate slightly different code if there are more than 1 term
    num_terms = len(terms)

    # Iterate over terms
    num_mult = 0
    for j in range(num_terms):

        # Get current term
        term = terms[j]

        # Compute optimized code
        code = binary.optimize(term.A0.A0)

        # Get primary and secondary indices
        iindices = term.A0.i.indices or [[]]
        aindices = term.A0.a.indices or [[]]

        #print "FErari code with FFC tensor"
        #print "---------------------------"
        #for line in code:
        #    print line
        #print ""

        # Generate code according to format from abstract FErari code
        for (lhs, rhs) in code:
            name  = build_lhs(lhs, j, iindices, aindices, num_terms, format)
            (value, num_mult) = build_rhs(rhs, j, iindices, aindices, num_terms, format, num_mult)
            declarations += [Declaration(name, value)]

    # Add all terms if more than one term
    if num_terms > 1:
        declarations += build_sum(iindices, num_terms, format)

    debug("Number of multiplications in computation of reference tensor: " + str(num_mult), 1)

    #print "Formatted code"
    #print "--------------"
    #for declaration in declarations:
    #    print declaration
    #print ""

    return declarations
            
def build_lhs(lhs, j, iindices, aindices, num_terms, format):
    "Build code for left-hand side from abstract FErari code."

    # Get id and entry of variable
    (id, entry) = lhs

    # Check that id is for the element tensor
    if not id == 0:
        raise RuntimeError, "Expecting entry of element tensor from FErari but got something else."

    # Get variable name
    if num_terms == 1:
        variable = format.format["element tensor"](iindices[entry], entry)
    else:
        variable = format.format["tmp declaration"](j, entry)
    
    return variable
    
def build_rhs(rhs, j, iindices, aindices, num_terms, format, num_mult):
    "Build code for right-hand side from abstract FErari code."
    terms = []
    # Iterate over terms in linear combination
    for (coefficient, id, entry) in rhs:

        # Ignore multiplication with zero
        if abs(coefficient) < FFC_EPSILON:
            continue

        # Get variable name
        if id == 0:
            if num_terms == 1:
                variable = format.format["element tensor"](iindices[entry], entry)
            else:
                variable = format.format["tmp access"](j, entry)
        else:
            variable = format.format["geometry tensor"](j, aindices[entry])
        
        # Treat special cases 1.0, -1.0
        if abs(coefficient - 1.0) < FFC_EPSILON:
            term = variable
        elif abs(coefficient + 1.0) < FFC_EPSILON:
            term = "-" + variable
        else:
            num_mult += 1
            term = format.format["multiplication"]([format.format["floating point"](coefficient), variable])

        # Add term to list
        terms += [term]

    # Special case, no terms
    if len(terms) == 0:
        return ("0.0", 0)

    # Add terms
    return (format.format["sum"](terms), num_mult)

def build_sum(iindices, num_terms, format):
    "Build sum of terms if more than one term."
    declarations = []
    for k in range(len(iindices)):

        # Get name of entry of element tensor
        i = iindices[k]
        name = format.format["element tensor"](i, k)

        # Build sum
        terms = []
        for j in range(num_terms):
            terms += [format.format["tmp access"](j, k)]
        value = format.format["sum"](terms)

        declarations += [Declaration(name, value)]

    return declarations
