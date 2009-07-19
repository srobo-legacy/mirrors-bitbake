# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
    AbstractSyntaxTree classes for the Bitbake language
"""

# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2003, 2004  Phil Blundell
# Copyright (C) 2009 Holger Hans Peter Freyther
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import bb, re

__word__ = re.compile(r"\S+")
__parsed_methods__ = bb.methodpool.get_parsed_dict()

class StatementGroup:
    def __init__(self):
        self.statements = []

    def append(self, statement):
        self.statements.append(statement)

    def eval(self, data):
        """
        Apply each statement on the data... in order
        """
        map(lambda x: x.eval(data), self.statements)

    def __getitem__(self, item):
        return self.statements.__getitem__(item)

class IncludeNode:
    def __init__(self, what_file, fn, lineno):
        self.what_file = what_file
        self.from_fn = fn
        self.from_lineno = lineno

    def eval(self, data):
        """
        Include the file and evaluate the statements
        """
        s = bb.data.expand(self.what_file, data)
        bb.msg.debug(3, bb.msg.domain.Parsing, "CONF %s:%d: including %s" % (self.from_fn, self.from_lineno, s))

        # TODO: Cache those includes... maybe not here though
        bb.parse.ConfHandler.include(self.from_fn, s, data, False)

class ExportNode:
    def __init__(self, var):
        self.var = var

    def eval(self, data):
        bb.data.setVarFlag(self.var, "export", 1, data)

class DataNode:
    """
    Various data related updates. For the sake of sanity
    we have one class doing all this. This means that all
    this need to be re-evaluated... we might be able to do
    that faster with multiple classes.
    """
    def __init__(self, groupd):
        self.groupd = groupd

    def getFunc(self, key, data):
        if 'flag' in self.groupd and self.groupd['flag'] != None:
            return bb.data.getVarFlag(key, self.groupd['flag'], data)
        else:
            return bb.data.getVar(key, data)

    def eval(self, data):
        groupd = self.groupd
        key = groupd["var"]
        if "exp" in groupd and groupd["exp"] != None:
            bb.data.setVarFlag(key, "export", 1, data)
        if "ques" in groupd and groupd["ques"] != None:
            val = self.getFunc(key, data)
            if val == None:
                val = groupd["value"]
        elif "colon" in groupd and groupd["colon"] != None:
            e = data.createCopy()
            bb.data.update_data(e)
            val = bb.data.expand(groupd["value"], e)
        elif "append" in groupd and groupd["append"] != None:
            val = "%s %s" % ((self.getFunc(key, data) or ""), groupd["value"])
        elif "prepend" in groupd and groupd["prepend"] != None:
            val = "%s %s" % (groupd["value"], (self.getFunc(key, data) or ""))
        elif "postdot" in groupd and groupd["postdot"] != None:
            val = "%s%s" % ((self.getFunc(key, data) or ""), groupd["value"])
        elif "predot" in groupd and groupd["predot"] != None:
            val = "%s%s" % (groupd["value"], (self.getFunc(key, data) or ""))
        else:
            val = groupd["value"]
        if 'flag' in groupd and groupd['flag'] != None:
            bb.msg.debug(3, bb.msg.domain.Parsing, "setVarFlag(%s, %s, %s, data)" % (key, groupd['flag'], val))
            bb.data.setVarFlag(key, groupd['flag'], val, data)
        else:
            bb.data.setVar(key, val, data)

class MethodNode:
    def __init__(self, func_name, body):
        self.func_name = func_name
        self.body = body

    def eval(self, data):
        bb.data.setVar(self.func_name, '\n'.join(self.body), data)
        bb.data.setVarFlag(self.func_name, "func", 1, data)
        if self.func_name == "__anonymous":
            anonqueue = bb.data.getVar("__anonqueue", data) or []
            anonitem = {}
            anonitem["content"] = bb.data.getVar("__anonymous", data)
            anonitem["flags"] = bb.data.getVarFlags("__anonymous", data)
            anonqueue.append(anonitem)
            bb.data.setVar("__anonqueue", anonqueue, data)
            bb.data.delVarFlags("__anonymous", data)
            bb.data.delVar("__anonymous", data)

class PythonMethodNode:
    def __init__(self, root, body, fn):
        self.root = root
        self.body = body
        self.fn = fn

    def eval(self, data):
        # Note we will add root to parsedmethods after having parse
        # 'this' file. This means we will not parse methods from
        # bb classes twice
        if not self.root  in __parsed_methods__:
            text = '\n'.join(self.body)
            bb.methodpool.insert_method(self.root, text, self.fn)

class MethodFlagsNode:
    def __init__(self, key, m):
        self.key = key
        self.m = m

    def eval(self, data):
        if bb.data.getVar(self.key, data):
            # clean up old version of this piece of metadata, as its
            # flags could cause problems
            bb.data.setVarFlag(self.key, 'python', None, data)
            bb.data.setVarFlag(self.key, 'fakeroot', None, data)
        if self.m.group("py") is not None:
            bb.data.setVarFlag(self.key, "python", "1", data)
        else:
            bb.data.delVarFlag(self.key, "python", data)
        if self.m.group("fr") is not None:
            bb.data.setVarFlag(self.key, "fakeroot", "1", data)
        else:
            bb.data.delVarFlag(self.key, "fakeroot", data)

class ExportFuncsNode:
    def __init__(self, fns, classes):
        self.n = __word__.findall(fns)
        self.classes = classes

    def eval(self, data):
        for f in self.n:
            allvars = []
            allvars.append(f)
            allvars.append(self.classes[-1] + "_" + f)

            vars = [[ allvars[0], allvars[1] ]]
            if len(self.classes) > 1 and self.classes[-2] is not None:
                allvars.append(self.classes[-2] + "_" + f)
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

class AddTaskNode:
    def __init__(self, func, before, after):
        self.func = func
        self.before = before
        self.after = after

    def eval(self, data):
        var = "do_" + self.func

        bb.data.setVarFlag(var, "task", 1, data)
        bbtasks = bb.data.getVar('__BBTASKS', data) or []
        if not var in bbtasks:
            bbtasks.append(var)
        bb.data.setVar('__BBTASKS', bbtasks, data)

        existing = bb.data.getVarFlag(var, "deps", data) or []
        if self.after is not None:
            # set up deps for function
            for entry in self.after.split():
                if entry not in existing:
                    existing.append(entry)
        bb.data.setVarFlag(var, "deps", existing, data)
        if self.before is not None:
            # set up things that depend on this func
            for entry in self.before.split():
                existing = bb.data.getVarFlag(entry, "deps", data) or []
                if var not in existing:
                    bb.data.setVarFlag(entry, "deps", [var] + existing, data)

class BBHandlerNode:
    def __init__(self, fns):
        self.hs = __word__.findall(fns)

    def eval(self, data):
        bbhands = bb.data.getVar('__BBHANDLERS', data) or []
        for h in self.hs:
            bbhands.append(h)
            bb.data.setVarFlag(h, "handler", 1, data)
        bb.data.setVar('__BBHANDLERS', bbhands, data)

class InheritNode:
    def __init__(self, files):
        self.n = __word__.findall(files)

    def eval(self, data):
        bb.parse.BBHandler.inherit(self.n, data)
 
def handleInclude(statements, m, fn, lineno, force):
    statements.append(IncludeNode(m.group(1), fn, lineno))

def handleExport(statements, m):
    statements.append(ExportNode(m.group(1)))

def handleData(statements, groupd):
    statements.append(DataNode(groupd))

def handleMethod(statements, func_name, body):
    statements.append(MethodNode(func_name, body))

def handlePythonMethod(statements, root, body, fn):
    statements.append(PythonMethodNode(root, body, fn))

def handleMethodFlags(statements, key, m):
    statements.append(MethodFlagsNode(key, m))

def handleExportFuncs(statements, m, classes):
    statements.append(ExportFuncsNode(m.group(1), classes))

def handleAddTask(statements, m):
    func = m.group("func")
    before = m.group("before")
    after = m.group("after")
    if func is None:
        return
    statements.append(AddTaskNode(func, before, after))

def handleBBHandlers(statements, m):
    statements.append(BBHandlerNode(m.group(1)))

def handleInherit(statements, m):
    files = m.group(1)
    n = __word__.findall(files)
    statements.append(InheritNode(m.group(1)))

def finalise(fn, d):
    bb.data.expandKeys(d)
    bb.data.update_data(d)
    anonqueue = bb.data.getVar("__anonqueue", d, 1) or []
    body = [x['content'] for x in anonqueue]
    flag = { 'python' : 1, 'func' : 1 }
    bb.data.setVar("__anonfunc", "\n".join(body), d)
    bb.data.setVarFlags("__anonfunc", flag, d)
    from bb import build
    try:
        t = bb.data.getVar('T', d)
        bb.data.setVar('T', '${TMPDIR}/', d)
        build.exec_func("__anonfunc", d)
        bb.data.delVar('T', d)
        if t:
            bb.data.setVar('T', t, d)
    except Exception, e:
        bb.msg.debug(1, bb.msg.domain.Parsing, "Exception when executing anonymous function: %s" % e)
        raise
    bb.data.delVar("__anonqueue", d)
    bb.data.delVar("__anonfunc", d)
    bb.data.update_data(d)

    all_handlers = {} 
    for var in bb.data.getVar('__BBHANDLERS', d) or []:
        # try to add the handler
        handler = bb.data.getVar(var,d)
        bb.event.register(var, handler)

    tasklist = bb.data.getVar('__BBTASKS', d) or []
    bb.build.add_tasks(tasklist, d)

