# -*- coding: utf-8 -*-
# Copyright (C) 2011-2017 Martin Sandve Alnæs
#
# This file is part of FFC (https://www.fenicsproject.org)
#
# SPDX-License-Identifier:    LGPL-3.0-or-later
"""Definitions of 'modified terminals', a core concept in uflacs."""

import logging

from ufl.classes import (Argument, CellAvg, FacetAvg, FixedIndex, FormArgument, Grad, Indexed,
                         Jacobian, ReferenceGrad, ReferenceValue, Restricted, SpatialCoordinate)
from ufl.permutation import build_component_numbering

logger = logging.getLogger(__name__)


class ModifiedTerminal(object):
    """A modified terminal expression is an object of a Terminal subtype, wrapped in terminal modifier types.

    The variables of this class are:

        expr - The original UFL expression
        terminal           - the underlying Terminal object

        global_derivatives - tuple of ints, each meaning derivative in that global direction
        local_derivatives  - tuple of ints, each meaning derivative in that local direction
        reference_value    - bool, whether this is represented in reference frame
        averaged           - None, 'facet' or 'cell'
        restriction        - None, '+' or '-'

        component          - tuple of ints, the global component of the Terminal
        flat_component     - single int, flattened local component of the Terminal, considering symmetry


        Possibly other component model:
        - global_component
        - reference_component
        - flat_component

    """

    def __init__(self, expr, terminal, reference_value, base_shape, base_symmetry, component,
                 flat_component, global_derivatives, local_derivatives, averaged, restriction):
        # The original expression
        self.expr = expr

        # The underlying terminal expression
        self.terminal = terminal

        # Are we seeing the terminal in physical or reference frame
        self.reference_value = reference_value

        # Get the shape of the core terminal or its reference value,
        # this is the shape that component and flat_component refers to
        self.base_shape = base_shape
        self.base_symmetry = base_symmetry

        # Components
        self.component = component
        self.flat_component = flat_component

        # Derivatives
        self.global_derivatives = global_derivatives
        self.local_derivatives = local_derivatives

        # Evaluation method (alternatives: { None, 'facet_midpoint',
        #  'cell_midpoint', 'facet_avg', 'cell_avg' })
        self.averaged = averaged

        # Restriction to one cell or the other for interior facet integrals
        self.restriction = restriction

    def as_tuple(self):
        """Return a tuple with hashable values that uniquely identifies this modified terminal.

        Some of the derived variables can be omitted here as long as
        they are fully determined from the variables that are included here.
        """
        t = self.terminal  # FIXME: Terminal is not sortable...
        rv = self.reference_value
        #bs = self.base_shape
        #bsy = self.base_symmetry
        #c = self.component
        fc = self.flat_component
        gd = self.global_derivatives
        ld = self.local_derivatives
        a = self.averaged
        r = self.restriction
        return (t, rv, fc, gd, ld, a, r)

    def argument_ordering_key(self):
        """Return a key for deterministic sorting of argument vertex
        indices based on the properties of the modified terminal.
        Used in factorization but moved here for closeness with ModifiedTerminal attributes."""
        t = self.terminal
        assert isinstance(t, Argument)
        n = t.number()
        assert n >= 0
        p = t.part()
        rv = self.reference_value
        #bs = self.base_shape
        #bsy = self.base_symmetry
        #c = self.component
        fc = self.flat_component
        gd = self.global_derivatives
        ld = self.local_derivatives
        a = self.averaged
        r = self.restriction
        return (n, p, rv, fc, gd, ld, a, r)

    def __hash__(self):
        return hash(self.as_tuple())

    def __eq__(self, other):
        return isinstance(other, ModifiedTerminal) and self.as_tuple() == other.as_tuple()

    #def __lt__(self, other):
    #    error("Shouldn't use this?")
    #    # FIXME: Terminal is not sortable, so the as_tuple contents
    #    # must be changed for this to work properly
    #    return self.as_tuple() < other.as_tuple()

    def __str__(self):
        s = []
        s += ["terminal:           {0}".format(self.terminal)]
        s += ["global_derivatives: {0}".format(self.global_derivatives)]
        s += ["local_derivatives:  {0}".format(self.local_derivatives)]
        s += ["averaged:           {0}".format(self.averaged)]
        s += ["component:          {0}".format(self.component)]
        s += ["restriction:        {0}".format(self.restriction)]
        return '\n'.join(s)


def is_modified_terminal(v):
    "Check if v is a terminal or a terminal wrapped in terminal modifier types."
    while not v._ufl_is_terminal_:
        if v._ufl_is_terminal_modifier_:
            v = v.ufl_operands[0]
        else:
            return False
    return True


def strip_modified_terminal(v):
    "Extract core Terminal from a modified terminal or return None."
    while not v._ufl_is_terminal_:
        if v._ufl_is_terminal_modifier_:
            v = v.ufl_operands[0]
        else:
            return None
    return v


def analyse_modified_terminal(expr):
    """Analyse a so-called 'modified terminal' expression.

    Return its properties in more compact form as a ModifiedTerminal object.

    A modified terminal expression is an object of a Terminal subtype,
    wrapped in terminal modifier types.

    The wrapper types can include 0-* Grad or ReferenceGrad objects,
    and 0-1 ReferenceValue, 0-1 Restricted, 0-1 Indexed,
    and 0-1 FacetAvg or CellAvg objects.
    """
    # Data to determine
    component = None
    global_derivatives = []
    local_derivatives = []
    reference_value = None
    restriction = None
    averaged = None

    # Start with expr and strip away layers of modifiers
    t = expr
    while not t._ufl_is_terminal_:
        if isinstance(t, Indexed):
            if component is not None:
                logger.error("Got twice indexed terminal.")

            t, i = t.ufl_operands
            component = [int(j) for j in i]

            if not all(isinstance(j, FixedIndex) for j in i):
                logger.error("Expected only fixed indices.")

        elif isinstance(t, ReferenceValue):
            if reference_value is not None:
                logger.error("Got twice pulled back terminal!")

            t, = t.ufl_operands
            reference_value = True

        elif isinstance(t, ReferenceGrad):
            if not component:  # covers None or ()
                logger.error("Got local gradient of terminal without prior indexing.")

            t, = t.ufl_operands
            local_derivatives.append(component[-1])
            component = component[:-1]

        elif isinstance(t, Grad):
            if not component:  # covers None or ()
                logger.error("Got local gradient of terminal without prior indexing.")

            t, = t.ufl_operands
            global_derivatives.append(component[-1])
            component = component[:-1]

        elif isinstance(t, Restricted):
            if restriction is not None:
                logger.error("Got twice restricted terminal!")

            restriction = t._side
            t, = t.ufl_operands

        elif isinstance(t, CellAvg):
            if averaged is not None:
                logger.error("Got twice averaged terminal!")

            t, = t.ufl_operands
            averaged = "cell"

        elif isinstance(t, FacetAvg):
            if averaged is not None:
                logger.error("Got twice averaged terminal!")

            t, = t.ufl_operands
            averaged = "facet"

        elif t._ufl_terminal_modifiers_:
            logger.error("Missing handler for terminal modifier type {}, object is {}.".format(
                type(t), repr(t)))

        else:
            logger.error("Unexpected type %s object %s." % (type(t), repr(t)))

    # Make canonical representation of derivatives
    global_derivatives = tuple(sorted(global_derivatives))
    local_derivatives = tuple(sorted(local_derivatives))

    # TODO: Temporarily letting local_derivatives imply reference_value,
    #       but this was not intended to be the case
    #if local_derivatives:
    #    reference_value = True

    # Make reference_value true or false
    reference_value = reference_value or False

    # Consistency check
    if isinstance(t, (SpatialCoordinate, Jacobian)):
        pass
    else:
        if local_derivatives and not reference_value:
            logger.error("Local derivatives of non-local value is not legal.")
        if global_derivatives and reference_value:
            logger.error("Global derivatives of local value is not legal.")

    # Make sure component is an integer tuple
    if component is None:
        component = ()
    else:
        component = tuple(component)

    # Get the shape of the core terminal or its reference value,
    # this is the shape that component refers to
    if isinstance(t, FormArgument):
        element = t.ufl_element()
        if reference_value:
            # Ignoring symmetry, assuming already applied in conversion to reference frame
            base_symmetry = {}
            base_shape = element.reference_value_shape()
        else:
            base_symmetry = element.symmetry()
            base_shape = t.ufl_shape
    else:
        base_symmetry = {}
        base_shape = t.ufl_shape

    # Assert that component is within the shape of the (reference) terminal
    if len(component) != len(base_shape):
        logger.error("Length of component does not match rank of (reference) terminal.")
    if not all(c >= 0 and c < d for c, d in zip(component, base_shape)):
        logger.error("Component indices %s are outside value shape %s" % (component, base_shape))

    # Flatten component
    vi2si, si2vi = build_component_numbering(base_shape, base_symmetry)
    flat_component = vi2si[component]
    # num_flat_components = len(si2vi)

    return ModifiedTerminal(expr, t, reference_value, base_shape, base_symmetry, component,
                            flat_component, global_derivatives, local_derivatives, averaged,
                            restriction)
