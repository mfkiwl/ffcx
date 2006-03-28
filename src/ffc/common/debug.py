__author__ = "Anders Logg (logg@tti-c.org)"
__date__ = "2005-02-04 -- 2006-03-28"
__copyright__ = "Copyright (C) 2005-2006 Anders Logg"
__license__  = "GNU GPL Version 2"

__level = -1
__indent = 0

"""Diagnostic messages are passed through a common interface to make
it possible to turn debugging on or off. Only messages with debug
level lower than or equal to the current debug level will be
printed. To see more messages, raise the debug level."""

def debug(string, debuglevel = 0):
    global __level
    if debuglevel <= __level:
        indentation = "".join(["    " for i in range(__indent)])
        print indentation + string

def setlevel(newlevel):
    global __level
    __level = newlevel

def getlevel():
    return __level

#def indent(increment = 1):
#    global __indent
#    __indent += increment
