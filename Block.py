#! /usr/bin/python
#-*- coding: utf-8 -*-

"""
Copyright (c) 2012  University of North Carolina at Chapel Hill
Luke Campagnola    ('luke.campagnola@%s.com' % 'gmail')

The MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""

from pyqtgraph.Qt import QtCore, QtGui

#from ..graphicsItems.GraphicsObject import GraphicsObject
import pyqtgraph.functions as fn
from Terminal import *
from pyqtgraph.pgcollections import OrderedDict

from pyqtgraph.graphicsItems.GraphicsObject import GraphicsObject
#from ..pgcollections import OrderedDict
#from ..debug import *
#import numpy as np
#from .eq import *

from BlockGraph import BlockGraphicsItem


def strDict(d):
    return dict([(str(k), v) for k, v in d.items()])

class Block(QtCore.QObject):
    """
    Node represents the basic processing unit of a flowchart. 
    A Node subclass implements at least:
    
    1) A list of input / ouptut terminals and their properties
    2) a process() function which takes the names of input terminals as keyword arguments and returns a dict with the names of output terminals as keys.

    A flowchart thus consists of multiple instances of Node subclasses, each of which is connected
    to other by wires between their terminals. A flowchart is, itself, also a special subclass of Node.
    This allows Nodes within the flowchart to connect to the input/output nodes of the flowchart itself.

    Optionally, a node class can implement the ctrlWidget() method, which must return a QWidget (usually containing other widgets) that will be displayed in the flowchart control panel. Some nodes implement fairly complex control widgets, but most nodes follow a simple form-like pattern: a list of parameter names and a single value (represented as spin box, check box, etc..) for each parameter. To make this easier, the CtrlNode subclass allows you to instead define a simple data structure that CtrlNode will use to automatically generate the control widget.     """
    
    sigOutputChanged = QtCore.Signal(object)   # self
    sigClosed = QtCore.Signal(object)
    sigRenamed = QtCore.Signal(object, object)
    sigTerminalRenamed = QtCore.Signal(object, object)  # term, oldName
    sigTerminalAdded = QtCore.Signal(object, object)  # self, term
    sigTerminalRemoved = QtCore.Signal(object, object)  # self, term

    
    def __init__(self, name, terminals=None, allowAddInput=False, allowAddOutput=False, allowRemove=True):
        """
        ==============  ============================================================
        **Arguments:**
        name            The name of this specific node instance. It can be any 
                        string, but must be unique within a flowchart. Usually,
                        we simply let the flowchart decide on a name when calling
                        Flowchart.addNode(...)
        terminals       Dict-of-dicts specifying the terminals present on this Node.
                        Terminal specifications look like::
                        
                            'inputTerminalName': {'io': 'in'}
                            'outputTerminalName': {'io': 'out'} 
                            
                        There are a number of optional parameters for terminals:
                        multi, pos, renamable, removable, multiable, bypass. See
                        the Terminal class for more information.
        allowAddInput   bool; whether the user is allowed to add inputs by the
                        context menu.
        allowAddOutput  bool; whether the user is allowed to add outputs by the
                        context menu.
        allowRemove     bool; whether the user is allowed to remove this node by the
                        context menu.
        ==============  ============================================================  
        
        """
        QtCore.QObject.__init__(self)
        self._name = name
        self._bypass = False
        self.bypassButton = None  ## this will be set by the flowchart ctrl widget..
        self._graphicsItem = None
        self.terminals = OrderedDict()
        self._inputs = OrderedDict()
        self._outputs = OrderedDict()
        self._allowAddInput = allowAddInput   ## flags to allow the user to add/remove terminals
        self._allowAddOutput = allowAddOutput
        self._allowRemove = allowRemove
        
        self.exception = None
        if terminals is None:
            return
        for name, opts in terminals.items():
            self.addTerminal(name, **opts)

        
    def nextTerminalName(self, name):
        """Return an unused terminal name"""
        name2 = name
        i = 1
        while name2 in self.terminals:
            name2 = "%s.%d" % (name, i)
            i += 1
        return name2
        
    def addInput(self, name="Input", **args):
        """Add a new input terminal to this Node with the given name. Extra
        keyword arguments are passed to Terminal.__init__.
        
        This is a convenience function that just calls addTerminal(io='in', ...)"""
        #print "Node.addInput called."
        return self.addTerminal(name, io='in', **args)
        
    def addOutput(self, name="Output", **args):
        """Add a new output terminal to this Node with the given name. Extra
        keyword arguments are passed to Terminal.__init__.
        
        This is a convenience function that just calls addTerminal(io='out', ...)"""
        return self.addTerminal(name, io='out', **args)
        
    def removeTerminal(self, term):
        """Remove the specified terminal from this Node. May specify either the 
        terminal's name or the terminal itself.
        
        Causes sigTerminalRemoved to be emitted."""
        if isinstance(term, Terminal):
            name = term.name()
        else:
            name = term
            term = self.terminals[name]
        
        #print "remove", name
        #term.disconnectAll()
        term.close()
        del self.terminals[name]
        if name in self._inputs:
            del self._inputs[name]
        if name in self._outputs:
            del self._outputs[name]
        self.graphicsItem().updateTerminals()
        self.sigTerminalRemoved.emit(self, term)
        
        
    def terminalRenamed(self, term, oldName):
        """Called after a terminal has been renamed        
        
        Causes sigTerminalRenamed to be emitted."""
        newName = term.name()
        for d in [self.terminals, self._inputs, self._outputs]:
            if oldName not in d:
                continue
            d[newName] = d[oldName]
            del d[oldName]
            
        self.graphicsItem().updateTerminals()
        self.sigTerminalRenamed.emit(term, oldName)
        
    def addTerminal(self, name, **opts):
        """Add a new terminal to this Node with the given name. Extra
        keyword arguments are passed to Terminal.__init__.
                
        Causes sigTerminalAdded to be emitted."""
        name = self.nextTerminalName(name)
        term = Terminal(self, name, **opts)
        self.terminals[name] = term
        if term.isInput():
            self._inputs[name] = term
        elif term.isOutput():
            self._outputs[name] = term
        self.graphicsItem().updateTerminals()
        self.sigTerminalAdded.emit(self, term)
        return term

        
    def inputs(self):
        """Return dict of all input terminals.
        Warning: do not modify."""
        return self._inputs
        
    def outputs(self):
        """Return dict of all output terminals.
        Warning: do not modify."""
        return self._outputs
        
    def process(self, **kargs):
        """Process data through this node. This method is called any time the flowchart 
        wants the node to process data. It will be called with one keyword argument
        corresponding to each input terminal, and must return a dict mapping the name
        of each output terminal to its new value.
        
        This method is also called with a 'display' keyword argument, which indicates
        whether the node should update its display (if it implements any) while processing
        this data. This is primarily used to disable expensive display operations
        during batch processing.
        """
        return {}
    
    def graphicsItem(self):
        """Return the GraphicsItem for this node. Subclasses may re-implement
        this method to customize their appearance in the flowchart."""
        if self._graphicsItem is None:
            self._graphicsItem = BlockGraphicsItem(self)
        return self._graphicsItem
    
    ## this is just bad planning. Causes too many bugs.
    def __getattr__(self, attr):
        """Return the terminal with the given name"""
        if attr not in self.terminals:
            raise AttributeError(attr)
        else:
            import traceback
            traceback.print_stack()
            print("Warning: use of node.terminalName is deprecated; use node['terminalName'] instead.")
            return self.terminals[attr]
            
    def __getitem__(self, item):
        #return getattr(self, item)
        """Return the terminal with the given name"""
        if item not in self.terminals:
            raise KeyError(item)
        else:
            return self.terminals[item]
            
    def name(self):
        """Return the name of this node."""
        return self._name

    def rename(self, name):
        """Rename this node. This will cause sigRenamed to be emitted."""
        oldName = self._name
        self._name = name
        #self.emit(QtCore.SIGNAL('renamed'), self, oldName)
        self.sigRenamed.emit(self, oldName)

    def dependentNodes(self):
        """Return the list of nodes which provide direct input to this node"""
        nodes = set()
        for t in self.inputs().values():
            nodes |= set([i.node() for i in t.inputTerminals()])
        return nodes
        #return set([t.inputTerminals().node() for t in self.listInputs().itervalues()])
        
    def __repr__(self):
        return "<Node %s @%x>" % (self.name(), id(self))
        
    def ctrlWidget(self):
        """Return this Node's control widget. 
        
        By default, Nodes have no control widget. Subclasses may reimplement this 
        method to provide a custom widget. This method is called by Flowcharts
        when they are constructing their Node list."""
        return None

    def bypass(self, byp):
        """Set whether this node should be bypassed.
        
        When bypassed, a Node's process() method is never called. In some cases,
        data is automatically copied directly from specific input nodes to 
        output nodes instead (see the bypass argument to Terminal.__init__). 
        This is usually called when the user disables a node from the flowchart 
        control panel.
        """
        self._bypass = byp
        if self.bypassButton is not None:
            self.bypassButton.setChecked(byp)
        self.update()
        
    def isBypassed(self):
        """Return True if this Node is currently bypassed."""
        return self._bypass

    def setInput(self, **args):
        """Set the values on input terminals. For most nodes, this will happen automatically through Terminal.inputChanged.
        This is normally only used for nodes with no connected inputs."""
        changed = False
        for k, v in args.items():
            term = self._inputs[k]
            oldVal = term.value()
            if not eq(oldVal, v):
                changed = True
            term.setValue(v, process=False)
        if changed and '_updatesHandled_' not in args:
            self.update()
        
    def inputValues(self):
        """Return a dict of all input values currently assigned to this node."""
        vals = {}
        for n, t in self.inputs().items():
            vals[n] = t.value()
        return vals
            
    def outputValues(self):
        """Return a dict of all output values currently generated by this node."""
        vals = {}
        for n, t in self.outputs().items():
            vals[n] = t.value()
        return vals
            
    def connected(self, localTerm, remoteTerm):
        """Called whenever one of this node's terminals is connected elsewhere."""
        pass
    
    def disconnected(self, localTerm, remoteTerm):
        """Called whenever one of this node's terminals is disconnected from another."""
        pass 
    
    def update(self, signal=True):
        """Collect all input values, attempt to process new output values, and propagate downstream.
        Subclasses should call update() whenever thir internal state has changed
        (such as when the user interacts with the Node's control widget). Update
        is automatically called when the inputs to the node are changed.
        """
        vals = self.inputValues()
        #print "  inputs:", vals
        try:
            if self.isBypassed():
                out = self.processBypassed(vals)
            else:
                out = self.process(**strDict(vals))
            #print "  output:", out
            if out is not None:
                if signal:
                    self.setOutput(**out)
                else:
                    self.setOutputNoSignal(**out)
            for n,t in self.inputs().items():
                t.setValueAcceptable(True)
            self.clearException()
        except:
            #printExc( "Exception while processing %s:" % self.name())
            for n,t in self.outputs().items():
                t.setValue(None)
            self.setException(sys.exc_info())
            
            if signal:
                #self.emit(QtCore.SIGNAL('outputChanged'), self)  ## triggers flowchart to propagate new data
                self.sigOutputChanged.emit(self)  ## triggers flowchart to propagate new data

    def processBypassed(self, args):
        """Called when the flowchart would normally call Node.process, but this node is currently bypassed.
        The default implementation looks for output terminals with a bypass connection and returns the
        corresponding values. Most Node subclasses will _not_ need to reimplement this method."""
        result = {}
        for term in list(self.outputs().values()):
            byp = term.bypassValue()
            if byp is None:
                result[term.name()] = None
            else:
                result[term.name()] = args.get(byp, None)
        return result

    def setOutput(self, **vals):
        self.setOutputNoSignal(**vals)
        #self.emit(QtCore.SIGNAL('outputChanged'), self)  ## triggers flowchart to propagate new data
        self.sigOutputChanged.emit(self)  ## triggers flowchart to propagate new data

    def setOutputNoSignal(self, **vals):
        for k, v in vals.items():
            term = self.outputs()[k]
            term.setValue(v)
            #targets = term.connections()
            #for t in targets:  ## propagate downstream
                #if t is term:
                    #continue
                #t.inputChanged(term)
            term.setValueAcceptable(True)

    def setException(self, exc):
        self.exception = exc
        self.recolor()
        
    def clearException(self):
        self.setException(None)
        
    def recolor(self):
        if self.exception is None:
            self.graphicsItem().setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        else:
            self.graphicsItem().setPen(QtGui.QPen(QtGui.QColor(150, 0, 0), 3))

    def saveState(self):
        """Return a dictionary representing the current state of this node
        (excluding input / output values). This is used for saving/reloading
        flowcharts. The default implementation returns this Node's position,
        bypass state, and information about each of its terminals. 
        
        Subclasses may want to extend this method, adding extra keys to the returned
        dict."""
        pos = self.graphicsItem().pos()
        state = {'pos': (pos.x(), pos.y()), 'bypass': self.isBypassed()}
        termsEditable = self._allowAddInput | self._allowAddOutput
        for term in self._inputs.values() + self._outputs.values():
            termsEditable |= term._renamable | term._removable | term._multiable
        if termsEditable:
            state['terminals'] = self.saveTerminals()
        return state
        
    def restoreState(self, state):
        """Restore the state of this node from a structure previously generated
        by saveState(). """
        pos = state.get('pos', (0,0))
        self.graphicsItem().setPos(*pos)
        self.bypass(state.get('bypass', False))
        if 'terminals' in state:
            self.restoreTerminals(state['terminals'])

    def saveTerminals(self):
        terms = OrderedDict()
        for n, t in self.terminals.items():
            terms[n] = (t.saveState())
        return terms
        
    def restoreTerminals(self, state):
        for name in list(self.terminals.keys()):
            if name not in state:
                self.removeTerminal(name)
        for name, opts in state.items():
            if name in self.terminals:
                term = self[name]
                term.setOpts(**opts)
                continue
            try:
                opts = strDict(opts)
                self.addTerminal(name, **opts)
            except:
                printExc("Error restoring terminal %s (%s):" % (str(name), str(opts)))
                
        
    def clearTerminals(self):
        for t in self.terminals.values():
            t.close()
        self.terminals = OrderedDict()
        self._inputs = OrderedDict()
        self._outputs = OrderedDict()
        
    def close(self):
        """Cleans up after the node--removes terminals, graphicsItem, widget"""
        self.disconnectAll()
        self.clearTerminals()
        item = self.graphicsItem()
        if item.scene() is not None:
            item.scene().removeItem(item)
        self._graphicsItem = None
        w = self.ctrlWidget()
        if w is not None:
            w.setParent(None)
        #self.emit(QtCore.SIGNAL('closed'), self)
        self.sigClosed.emit(self)
            
    def disconnectAll(self):
        for t in self.terminals.values():
            t.disconnectAll()
