from pyparsing import *

ParserElement.setDefaultWhitespaceChars(' ')


lparen, rparen, lbracket, rbracket, equals, lbrace, rbrace = map(Suppress, "()[]={}")
parens = Literal("()").suppress()
EOL = OneOrMore(LineEnd()).suppress()
#comment = Suppress("#") + Suppress(White()) + SkipTo(LineEnd())
comment = Suppress("#") + SkipTo(LineEnd())
#commentblock = Combine(OneOrMore((StringStart() | EOL) + Group(comment)), "\n")

quoted = QuotedString("'", multiline=True) | QuotedString('"', multiline=True)
variablename = Word(alphanums + "+-_.${}/")
value = (quoted | SkipTo(LineEnd()))("value")

varassignments = MatchFirst(map(Literal, ("+=", "=+", ".=", "=.", "?=", ":=", "=")))
key = variablename("key")
vardef = (Optional(Keyword("export"), False) + key + varassignments + value)("vardef")
exportvar = Suppress(Keyword("export")) + key

flag = lbracket + variablename + rbracket
flagdef = variablename + flag + equals + value

funcflag = (Keyword("python")|Keyword("fakeroot"))("flag")
funcstart = Optional(funcflag, False) + Optional(key, False) + parens + lbrace + EOL
funcend = LineStart() + rbrace
funclines = ZeroOrMore(NotAny(funcend) + SkipTo(LineEnd(), include=True).leaveWhitespace())
funcdef = funcstart + Combine(funclines("value")).leaveWhitespace() + funcend

include = (Keyword("include") | Keyword("require")) + SkipTo(LineEnd())
inherit = Keyword("inherit").suppress() + OneOrMore(variablename)("classes")
addtaskbefore = Keyword("before").suppress() + Group(OneOrMore(NotAny("after") + variablename))("before")
addtaskafter = Keyword("after").suppress() + Group(OneOrMore(NotAny("before") + variablename))("after")
addtask = Keyword("addtask").suppress() + key + (Optional(addtaskbefore, False) & Optional(addtaskafter, False))
exportfunc = Keyword("EXPORT_FUNCTIONS").suppress() + OneOrMore(variablename)("exports")
addhandler = Keyword("addhandler").suppress() + OneOrMore(variablename)("handlers")

pythondeflines = Group(OneOrMore(EOL + Combine(White() + SkipTo(LineEnd()).leaveWhitespace()).leaveWhitespace()))
pythondeflines.ignore(comment)
#pythondeflines = Group(OneOrMore(EOL + NotAny(LineStart() + NotAny(LineEnd())) + SkipTo(LineEnd()).leaveWhitespace()))
pythondef = Keyword("def").suppress() + key + lparen + SkipTo(')')("signature") + rparen + Suppress(':') + pythondeflines("value")

cfgstatement = (vardef | exportvar | flagdef | include | comment | (LineStart() + LineEnd()).suppress())
statement = (funcdef | pythondef | exportfunc | addtask | addhandler | inherit | cfgstatement)
recipe = ZeroOrMore((LineStart() + LineEnd()).suppress() | (statement + EOL))("statements")
configfile = ZeroOrMore((LineStart() + LineEnd()).suppress() | (cfgstatement + EOL))("statements")
