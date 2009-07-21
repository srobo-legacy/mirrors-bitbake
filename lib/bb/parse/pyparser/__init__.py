import os
import sys
import bb
from collections import deque
from pyparsing import ParseBaseException

from bb.parse import ParseError, resolve_file, ast
from bb.parse.pyparser import bnf
from bb.parse.ast import AstNode, AddTaskNode, BBHandlerNode, PythonMethodNode

class SetVarNode(AstNode):
    def __init__(self, export, key, eq, value):
        self._key = key
        self._value = value.replace("\\\n", "")
        self._eq = eq
        self._export = export
    def eval(self, data):
        value = self._value
        existing = data.getVar(self._key, False)
        if self._eq == ".=":
            value = "%s%s" % (existing or "", self._value)
        elif self._eq == "=.":
            value = "%s%s" % (self._value, existing or "")
        elif self._eq == "+=":
            value = "%s %s" % (existing or "", self._value)
        elif self._eq == "=+":
            value = "%s %s" % (self._value, existing or "")
        elif self._eq == "?=":
            if existing is not None:
                value = None
        elif self._eq == ":=":
            value = bb.data.expand(self._value, data)

        if value is not None:
            data.setVar(self._key, value)
        if self._export:
            data.setVarFlag(self._key, "export", True)
bnf.vardef.addParseAction(lambda s, loc, toks: SetVarNode(*toks))

class ExportVarNode(AstNode):
    def __init__(self, key):
        self._key = key
    def eval(self, data):
        data.setVarFlag(self._key, "export", True)
bnf.exportvar.addParseAction(lambda s, loc, toks: ExportVarNode(*toks))

class SetFlagNode(AstNode):
    def __init__(self, key, flag, value):
        self._key = key
        self._flag = flag
        self._value = value
    def eval(self, data):
        data.setVarFlag(self._key, self._flag, self._value)
bnf.flagdef.addParseAction(lambda s, loc, result: SetFlagNode(*result))

class SetFuncNode(AstNode):
    def __init__(self, key, value, flag):
        self._key = key
        self._value = "".join(value)
        self._flag = flag
    def eval(self, data):
        if not self._key:
            anonqueue = bb.data.getVar("__anonqueue", data) or []
            anonqueue.append({"content": self._value})
            bb.data.setVar("__anonqueue", anonqueue, data)
        else:
            data.setVar(self._key, self._value)
            data.setVarFlag(self._key, "func", True)
            if self._flag:
                data.setVarFlag(self._key, self._flag, True)
bnf.funcdef.setParseAction(lambda s, loc, result: SetFuncNode(result[1], result[2], result[0]))

class InheritNode(AstNode):
    def __init__(self, classes):
        self._classes = classes
    def eval(self, d):
        for class_ in self._classes:
            handle(os.path.join("classes", "%s.bbclass" % bb.data.expand(class_, d)), d, True)
bnf.inherit.addParseAction(lambda s, loc, result: InheritNode(result))

class IncludeNode(AstNode):
    def __init__(self, fn, optional):
        self._fn = fn.strip()
        self._optional = optional
    def eval(self, d):
        fn = bb.data.expand(self._fn, d)
        try:
            abs_fn = resolve_file(fn, d)
        except IOError:
            if self._optional:
                return
            else:
                raise
        else:
            bb.parse.handle(abs_fn, d, True)
bnf.include.addParseAction(lambda s, loc, result: IncludeNode(result[1], result[0] == "include"))

def _addtask(s, loc, results):
    taskname = results[0]
    before = None
    after = None

    for result in results[1:]:
        if result:
            if result.getName() == "before":
                before = " ".join(result)
            elif result.getName() == "after":
                after = " ".join(result)
    return AddTaskNode(taskname, before, after)
bnf.addtask.addParseAction(_addtask)

class ExportFuncsNode(AstNode):
    def __init__(self, funcs):
        self._funcs = funcs
    def eval(self, data):
        classes = data.getVar("__class_stack", False)
        if not classes:
            raise ParseError("Can't EXPORT_FUNCTIONS(%s), classes is empty" % self._funcs)
        for f in self._funcs:
            allvars = []
            allvars.append(f)
            allvars.append(classes[-1] + "_" + f)

            vars = [[ allvars[0], allvars[1] ]]
            if len(classes) > 1 and classes[-2] is not None:
                allvars.append(classes[-2] + "_" + f)
                vars = []
                vars.append([allvars[2], allvars[1]])
                vars.append([allvars[0], allvars[2]])

            for (var, calledvar) in vars:
                if bb.data.getVar(var, data) and not bb.data.getVarFlag(var, 'export_func', data):
                    continue

                if bb.data.getVar(var, data):
                    bb.data.setVarFlag(var, 'python', None, data)
                    bb.data.setVarFlag(var, 'func', None, data)

                for flag in [ "func", "python" ]:
                    if bb.data.getVarFlag(calledvar, flag, data):
                        bb.data.setVarFlag(var, flag, bb.data.getVarFlag(calledvar, flag, data), data)
                for flag in [ "dirs" ]:
                    if bb.data.getVarFlag(var, flag, data):
                        bb.data.setVarFlag(calledvar, flag, bb.data.getVarFlag(var, flag, data), data)

                if bb.data.getVarFlag(calledvar, "python", data):
                    bb.data.setVar(var, "\tbb.build.exec_func('" + calledvar + "', d)\n", data)
                else:
                    bb.data.setVar(var, "\t" + calledvar + "\n", data)
                bb.data.setVarFlag(var, 'export_func', '1', data)
bnf.exportfunc.addParseAction(lambda s, loc, result: ExportFuncsNode(result))

class AddHandlerNode(BBHandlerNode):
    def __init__(self, handlers):
        self.hs = handlers
    def eval(self, data):
        BBHandlerNode.eval(self, data)
bnf.addhandler.addParseAction(lambda s, loc, result: AddHandlerNode(result))

def supports(fn, d):
    return os.path.splitext(fn)[-1] in (".conf", ".bb", ".inc", ".bbclass")

def init(d):
    if not d.getVar("TOPDIR", True):
        d.setVar("TOPDIR", os.path.normpath(os.getcwd()))
    if not d.getVar("BBPATH", True):
        d.setVar("BBPATH", os.path.join(sys.prefix, "share", "bitbake"))

def handle(fn, d, include = False):
    init(d)

    oldfile = None
    if include:
        oldfile = d.getVar("FILE", True)

    abs_fn = resolve_file(fn, d)
    f = open(abs_fn, 'r')

    if include:
        bb.parse.mark_dependency(d, abs_fn)

    root = '.'.join(os.path.splitext(os.path.basename(fn))[:-1])
    if fn.endswith(".bbclass"):
        classes = d.getVar("__class_stack", False) or deque()
        d.setVar("__class_stack", classes)
        classes.append(root)

    if fn.endswith(".conf"):
        parser = bnf.configfile
    else:
        parser = bnf.recipe

    if not fn.endswith(".bbclass"):
        d.setVar("FILE", fn)

    bnf.pythondef.setParseAction(lambda s, loc, result: PythonMethodNode(root, ["def %s(%s):" % (result[0], result[1])] + list(result[2]), fn))

    try:
        contents = f.read()
    except IOError, e:
        raise ParseError("Error reading %s: %s" % (fn, str(e)))

    try:
        results = parser.parseString(contents, True)
    except ParseBaseException, e:
        msg = "Parsing error in %s: %s\nFailing line: %s" % (fn, str(e), e.markInputline())
        raise ParseError(msg)

    for statement in results:
        if getattr(statement, "eval", False):
            statement.eval(d)

    if fn.endswith(".bbclass"):
        classes.pop()
    elif not fn.endswith(".conf"):
        if not include:
            ast.finalise(fn, d)

    if oldfile:
        d.setVar("FILE", oldfile)

    if root.endswith(".inc") or root.endswith(".bbclass"):
        bb.methodpool.get_parsed_dict()[root] = 1

    return d

from bb.parse import handlers
handlers.insert(0, {'supports': supports, 'handle': handle, 'init': init})
