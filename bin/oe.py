#######################################################################
#
#  OpenEmbedded Python Library
#
#  Part of this code has been shamelessly stolen from Gentoo's portage.py.
#  In the source code was GPL-2 as License, so the same goes for this file.
#
#  Functions that have comments with lots of ###### have been tested in the
#  OE environment, all other stuff has been taken (more or less) 1:1 from
#  Portage and may or may not apply.
#
#  Please visit http://www.openembedded.org/phpwiki/ for more info.
#

import sys,posixpath,string,types
projectdir = posixpath.dirname(posixpath.dirname(posixpath.abspath(sys.argv[0])))


class VarExpandError(Exception):
	pass



#######################################################################
#
# tokenize()
#
# Put in a string like
#
#	'sys-apps/linux-headers nls? (sys-devel/gettext)'
#
# and get back
#
#	['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']]
#

def tokenize(mystring):
	"""breaks a string like 'foo? (bar) oni? (blah (blah))'
	into embedded lists; returns None on paren mismatch"""
	newtokens = []
	curlist   = newtokens
	prevlists = []
	level     = 0
	accum     = ""
	for x in mystring:
		if x=="(":
			if accum:
				curlist.append(accum)
				accum=""
			prevlists.append(curlist)
			curlist=[]
			level=level+1
		elif x==")":
			if accum:
				curlist.append(accum)
				accum=""
			if level==0:
				print "!!! tokenizer: Unmatched left parenthesis in:\n'"+mystring+"'"
				return None
			newlist=curlist
			curlist=prevlists.pop()
			curlist.append(newlist)
			level=level-1
		elif x in string.whitespace:
			if accum:
				curlist.append(accum)
				accum=""
		else:
			accum=accum+x
	if accum:
		curlist.append(accum)
	if (level!=0):
		print "!!! tokenizer: Exiting with unterminated parenthesis in:\n'"+mystring+"'"
		return None
	return newtokens


#######################################################################
#
# evaluate(tokens, defines)
#
#
# Assume you have this list of dependencies:
#
#	['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']]
#
# and you do a normal build (no defines are set), then you will get:
#
#	['sys-apps/linux-headers']
#
# as dependency. Now, assume you want to have NLS on your OE target, then put
# 'nls' into the defines list. Now you will get
#
#	['sys-apps/linux-headers', ['sys-devel/gettext']]
#
# Just put that throught flatten() and you have a list of dependencies.
#
#
# The tokens can also have negative flags, e.g.
#
#	['gdbm?', ['gdbm'], '!gdbm?', ['flatfile'] ]
#

def evaluate(tokens,mydefines,allon=0):
	"""removes tokens based on whether conditional definitions exist or not.
	Recognizes !"""
	if tokens == None:
		return None
	mytokens = tokens + []		# this copies the list
	pos = 0
	while pos < len(mytokens):
		if type(mytokens[pos]) == types.ListType:
			evaluate(mytokens[pos], mydefines)
			if not len(mytokens[pos]):
				del mytokens[pos]
				continue
		elif mytokens[pos][-1] == "?":
			cur = mytokens[pos][:-1]
			del mytokens[pos]
			if allon:
				if cur[0] == "!":
					del mytokens[pos]
			else:
				if cur[0] == "!":
					if (cur[1:] in mydefines) and (pos < len(mytokens)):
						del mytokens[pos]
						continue
				elif (cur not in mydefines) and (pos < len(mytokens)):
					del mytokens[pos]
					continue
		pos = pos + 1
	return mytokens


#######################################################################
#
#  flatten()
#
#  [1,[2,3]] -> [1,2,3]
#
#  Usually used after tokenize() and evaluate()
#

def flatten(mytokens):
	"""this function now turns a [1,[2,3]] list into
	a [1,2,3] list and returns it."""
	newlist=[]
	for x in mytokens:
		if type(x)==types.ListType:
			newlist.extend(flatten(x))
		else:
			newlist.append(x)
	return newlist


#######################################################################
#
# varexpand()
#
# Expands variables of the form ${VARNAME} via keys
# Expands variables of the form ${@python-code} via eval()
# Expands shell escapes like \n
#

# cache expansions of constant strings
_varexpand_cache_ = {}
def varexpand(mystring,mydict = {}, stripnl=0):
	"""
	Removes quotes, handles \n, etc.
	This code is used by the configfile code, as well as others (parser)
	This would be a good bunch of code to port to C.
	"""

	try:
		return _varexpand_cache_[" "+mystring]
	except KeyError:
		pass

	numvars   = 0
	mystring  = " "+mystring
	insing    = 0	# in single quotes?
	indoub    = 0	# in double quotes?
	pos       = 1
	newstring = " "
	while pos<len(mystring):
		if (mystring[pos] == "'") and (mystring[pos-1] != "\\"):
			if indoub:
				newstring = newstring + "'"
			else:
				insing = not insing
			pos = pos+1
			continue
		elif (mystring[pos] == '"') and (mystring[pos-1] != "\\"):
			if insing:
				newstring = newstring + '"'
			else:
				indoub = not indoub
			pos = pos + 1
			continue
		if not insing: 
			# expansion time
			if stripnl and (mystring[pos] == "\n"):
				#print "stripped: ",newstring
				# convert newlines to spaces
				newstring = newstring + " "
				pos = pos + 1
			elif mystring[pos] == "\\":
				# backslash expansion time
				if pos +1 >= len(mystring):
					newstring = newstring + mystring[pos]
					break
				else:
					a = mystring[pos+1]
					pos = pos + 2
					if a == 'a':
						newstring = newstring + chr(007)
					elif a == 'b':
						newstring = newstring + chr(010)
					elif a == 'e':
						newstring = newstring + chr(033)
					elif (a == 'f') or (a == 'n'):
						newstring = newstring + chr(012)
					elif a == 'r':
						newstring = newstring + chr(015)
					elif a == 't':
						newstring = newstring + chr(011)
					elif a == 'v':
						newstring = newstring + chr(013)
					else:
						# remove backslash only, as bash does: this takes care of \\ and \' and \" as well
						newstring = newstring + mystring[pos-1:pos]
						continue
			elif (mystring[pos] == "$") and (mystring[pos-1] != "\\"):
				pos = pos + 1
				if pos+1 >= len(mystring):
					_varexpand_cache_[mystring] = ""
					return ""
				if mystring[pos] == "{":
					pos = pos + 1
					terminus = "}"
				else:
					terminus = string.whitespace
				myvstart = pos
				while mystring[pos] not in terminus:
					if pos+1 >= len(mystring):
						_varexpand_cache_[mystring] = ""
						return ""
					pos = pos + 1
				myvarname = mystring[myvstart:pos]
				pos = pos + 1
				if len(myvarname) == 0:
					_varexpand_cache_[mystring] = ""
					return ""
				numvars = numvars + 1

				# keep vars that are not all in UPPERCASE
				if myvarname[0] == '@':
					newstring = newstring + eval(myvarname[1:])
				elif myvarname != myvarname.upper():
					newstring = newstring + '${' + myvarname + '}'
				elif mydict.has_key(myvarname):
					newstring = newstring + mydict[myvarname]
				else:
					raise VarExpandError, "'" + myvarname + "' missing"
			else:
				newstring = newstring + mystring[pos]
				pos = pos + 1
		else:
			newstring = newstring + mystring[pos]
			pos = pos + 1
	if numvars == 0:
		_varexpand_cache_[mystring] = newstring[1:]
	return newstring[1:]	


#######################################################################
#
# Reads some text file and returns a dictionary that is mykeys + all found definitions
# Definitions have the form:
#
# VAR=value
# VAR     =    value				whitespace is ok
# VAR = " value"				using double quotes
# VAR = 'value '				using single quotes
# VAR() {					use this for multi-line values
#    value
#    value
# }
#
# When myexpand is true, all lines go throught varexpand(), see above.
#

def getconfig(mycfg, mykeys={}, myexpand=0):
	import shlex
	f = open(mycfg,'r')
	lex = shlex.shlex(f)
	lex.wordchars = string.digits + string.letters + "~!@#%*_\:;?,./-+{}"
	lex.quotes = "\"'"
	while 1:
		key = lex.get_token()
		if key == '':
			# Normal end of file
			break;
		equ = lex.get_token()
		val = ''
		if equ == '':
			# Unexpected end of file
			print lex.error_leader(mycfg, lex.lineno), \
				"enexpected end of config file: variable", key
			return None
		elif equ == '(':
			equ = lex.get_token()
			if equ != ')':
				print lex.error_leader(mycfg, lex.lineno), \
					"expected ')', got '"+ equ + "'"
				return None
			equ = lex.get_token()
			if equ != '{':
				print lex.error_leader(mycfg, lex.lineno), \
					"expected '{', got '"+ equ + "'"
				return None
			lex.lineno = lex.lineno - 1
			while 1:
				equ = lex.instream.readline()
				if equ == '':
					break
				equ = equ.rstrip()
				if equ == '}':
					break
				if myexpand:
					try:
						equ = varexpand(equ, mykeys, 0)
					except VarExpandError, detail:
						print lex.error_leader(mycfg, lex.lineno) + detail.args[0]
				lex.lineno = lex.lineno + 1
				val = val + equ + "\n"
			lex.lineno = lex.lineno + 2
		elif equ != '=':
			print lex.error_leader(mycfg, lex.lineno), \
				"expected '=', got '" + equ + "'"
			return None
		if val == '':
			val = lex.get_token()
			#stripnl = 1
			stripnl = 0
		else:
			stripnl = 0
		if val == '':
			print lex.error_leader(mycfg, lex.lineno), \
				"end of file in variable definition"
			return None
		if myexpand:
			try:
				val = varexpand(val,mykeys,stripnl)
			except VarExpandError, detail:
				print lex.error_leader(mycfg, lex.lineno) + detail.args[0]
		mykeys[key] = val
			
	return mykeys


def fetch(myuris, listonly=0):
	"fetch files.  Will use digest file if available."
	if ("mirror" in features) and ("nomirror" in settings["RESTRICT"].split()):
		print ">>> \"mirror\" mode and \"nomirror\" restriction enabled; skipping fetch."
		return 1
	global thirdpartymirrors
	mymirrors=settings["GENTOO_MIRRORS"].split()
	fetchcommand=settings["FETCHCOMMAND"]
	resumecommand=settings["RESUMECOMMAND"]
	fetchcommand=string.replace(fetchcommand,"${DISTDIR}",settings["DISTDIR"])
	resumecommand=string.replace(resumecommand,"${DISTDIR}",settings["DISTDIR"])
	mydigests=None
	digestfn=settings["FILESDIR"]+"/digest-"+settings["PF"]
	if os.path.exists(digestfn):
		myfile=open(digestfn,"r")
		mylines=myfile.readlines()
		mydigests={}
		for x in mylines:
			myline=string.split(x)
			if len(myline)<4:
				#invalid line
				print "!!! The digest",digestfn,"appears to be corrupt.  Aborting."
				return 0
			try:
				mydigests[myline[2]]={"md5":myline[1],"size":string.atol(myline[3])}
			except ValueError:
				print "!!! The digest",digestfn,"appears to be corrupt.  Aborting."
	if "fetch" in settings["RESTRICT"].split():
		# fetch is restricted.	Ensure all files have already been downloaded; otherwise,
		# print message and exit.
		gotit=1
		for myuri in myuris:
			myfile=os.path.basename(myuri)
			try:
				mystat=os.stat(settings["DISTDIR"]+"/"+myfile)
			except (OSError,IOError),e:
				# file does not exist
				print "!!!",myfile,"not found in",settings["DISTDIR"]+"."
				gotit=0
		if not gotit:
			print
			print "!!!",settings["CATEGORY"]+"/"+settings["PF"],"has fetch restriction turned on."
			print "!!! This probably means that this ebuild's files must be downloaded"
			print "!!! manually.  See the comments in the ebuild for more information."
			print
			spawn("/usr/sbin/ebuild.sh nofetch")
			return 0
		return 1
	locations=mymirrors[:]
	filedict={}
	for myuri in myuris:
		myfile=os.path.basename(myuri)
		if not filedict.has_key(myfile):
			filedict[myfile]=[]
			for y in range(0,len(locations)):
				filedict[myfile].append(locations[y]+"/distfiles/"+myfile)
		if myuri[:9]=="mirror://":
			eidx = myuri.find("/", 9)
			if eidx != -1:
				mirrorname = myuri[9:eidx]
				if thirdpartymirrors.has_key(mirrorname):
					for locmirr in thirdpartymirrors[mirrorname]:
						filedict[myfile].append(locmirr+"/"+myuri[eidx+1:])		
		else:
				filedict[myfile].append(myuri)
	for myfile in filedict.keys():
		if listonly:
			fetched=0
			print ""
		for loc in filedict[myfile]:
			if listonly:
				print loc+" ",
				continue
			try:
				mystat=os.stat(settings["DISTDIR"]+"/"+myfile)
				if mydigests!=None and mydigests.has_key(myfile):
					#if we have the digest file, we know the final size and can resume the download.
					if mystat[ST_SIZE]<mydigests[myfile]["size"]:
						fetched=1
					else:
						#we already have it downloaded, skip.
						#if our file is bigger than the recorded size, digestcheck should catch it.
						fetched=2
				else:
					#we don't have the digest file, but the file exists.  Assume it is fully downloaded.
					fetched=2
			except (OSError,IOError),e:
				fetched=0
			if fetched!=2:
				#we either need to resume or start the download
				#you can't use "continue" when you're inside a "try" block
				if fetched==1:
					#resume mode:
					print ">>> Resuming download..."
					locfetch=resumecommand
				else:
					#normal mode:
					locfetch=fetchcommand
				print ">>> Downloading",loc
				myfetch=string.replace(locfetch,"${URI}",loc)
				myfetch=string.replace(myfetch,"${FILE}",myfile)
				myret=spawn(myfetch,free=1)
				if mydigests!=None and mydigests.has_key(myfile):
					try:
						mystat=os.stat(settings["DISTDIR"]+"/"+myfile)
						# no exception?  file exists. let digestcheck() report
						# an appropriately for size or md5 errors
						if myret and (mystat[ST_SIZE]<mydigests[myfile]["size"]):
							# Fetch failed... Try the next one... Kill 404 files though.
							if (mystat[ST_SIZE]<100000) and (len(myfile)>4) and not ((myfile[-5:]==".html") or (myfile[-4:]==".htm")):
								html404=re.compile("<title>.*(not found|404).*</title>",re.I|re.M)
								try:
									if html404.search(open(settings["DISTDIR"]+"/"+myfile).read()):
										try:
											os.unlink(settings["DISTDIR"]+"/"+myfile)
											print ">>> Deleting invalid distfile. (Improper 404 redirect from server.)"
										except:
											pass
								except:
									pass
							continue
						fetched=2
						break
					except (OSError,IOError),e:
						fetched=0
				else:
					if not myret:
						fetched=2
						break
		if (fetched!=2) and not listonly:
			print '!!! Couldn\'t download',myfile+". Aborting."
			return 0
	return 1


def movefile(src,dest,newmtime=None,sstat=None):
	"""moves a file from src to dest, preserving all permissions and attributes; mtime will
	be preserved even when moving across filesystems.  Returns true on success and false on
	failure.  Move is atomic."""
	#print "movefile("+src+","+dest+","+str(newmtime)+","+str(sstat)+")"
	try:
		if not sstat:
			sstat=os.lstat(src)
	except Exception, e:
		print "!!! Stating source file failed... movefile()"
		print "!!!",e
		return None

	destexists=1
	try:
		dstat=os.lstat(dest)
	except:
		dstat=os.lstat(os.path.dirname(dest))
		destexists=0

	if destexists:
		if S_ISLNK(dstat[ST_MODE]):
			try:
				os.unlink(dest)
				destexists=0
			except Exception, e:
				pass

	if S_ISLNK(sstat[ST_MODE]):
		try:
			target=os.readlink(src)
			if destexists and not S_ISDIR(dstat[ST_MODE]):
				os.unlink(dest)
			os.symlink(target,dest)
			missingos.lchown(dest,sstat[ST_UID],sstat[ST_GID])
			return os.lstat(dest)
		except Exception, e:
			print "!!! failed to properly create symlink:"
			print "!!!",dest,"->",target
			print "!!!",e
			return None

	renamefailed=1
	if sstat[ST_DEV]==dstat[ST_DEV]:
		try:
			ret=os.rename(src,dest)
			renamefailed=0
		except Exception, e:
			import errno
			if e[0]!=errno.EXDEV:
				# Some random error.
				print "!!! Failed to move",src,"to",dest
				print "!!!",e
				return None
			# Invalid cross-device-link 'bind' mounted or actually Cross-Device

	if renamefailed:
		didcopy=0
		if S_ISREG(sstat[ST_MODE]):
			try: # For safety copy then move it over.
				shutil.copyfile(src,dest+"#new")
				os.rename(dest+"#new",dest)
				didcopy=1
			except Exception, e:
				print '!!! copy',src,'->',dest,'failed.'
				print "!!!",e
				return None
		else:
			#we don't yet handle special, so we need to fall back to /bin/mv
			a=getstatusoutput("/bin/mv -f "+"'"+src+"' '"+dest+"'")
			if a[0]!=0:
				print "!!! Failed to move special file:"
				print "!!! '"+src+"' to '"+dest+"'"
				print "!!!",a
				return None # failure
		try:
			if didcopy:
				missingos.lchown(dest,sstat[ST_UID],sstat[ST_GID])
				os.chmod(dest, S_IMODE(sstat[ST_MODE])) # Sticky is reset on chown
				os.unlink(src)
		except Exception, e:
			print "!!! Failed to chown/chmod/unlink in movefile()"
			print "!!!",dest
			print "!!!",e
			return None

	if newmtime:
		os.utime(dest,(newmtime,newmtime))
	else:
		os.utime(dest, (sstat[ST_ATIME], sstat[ST_MTIME]))
		newmtime=sstat[ST_MTIME]
	return newmtime


#######################################################################
#
# relparse()
#
# Parses the last elements of a version number into a triplet, that can
# later be compared:
#
#	'1.2_pre3'	-> [1.2, -2, 3.0]
#	'1.2b'		-> [1.2, 98, 0]
#	'1.2'		-> [1.2, 0, 0]
#

_package_weights_ = {"pre":-2,"p":0,"alpha":-4,"beta":-3,"rc":-1}	# dicts are unordered
_package_ends_    = ["pre", "p", "alpha", "beta", "rc"]			# so we need ordered list

def relparse(myver):
	"converts last version part into three components"
	number   = 0
	p1       = 0
	p2       = 0
	mynewver = string.split(myver,"_")
	if len(mynewver)==2:
		# an _package_weights_
		number = string.atof(mynewver[0])
		match = 0
		for x in _package_ends_:
			elen = len(x)
			if mynewver[1][:elen] == x:
				match = 1
				p1 = _package_weights_[x]
				try:
					p2 = string.atof(mynewver[1][elen:])
				except:
					p2 = 0
				break
		if not match:	
			# normal number or number with letter at end
			divider = len(myver)-1
			if myver[divider:] not in "1234567890":
				# letter at end
				p1 = ord(myver[divider:])
				number = string.atof(myver[0:divider])
			else:
				number = string.atof(myver)		
	else:
		# normal number or number with letter at end
		divider = len(myver)-1
		if myver[divider:] not in "1234567890":
			#letter at end
			p1     = ord(myver[divider:])
			number = string.atof(myver[0:divider])
		else:
			number = string.atof(myver)  
	return [number,p1,p2]


#######################################################################
#
# ververify()
#
# Returns 1 if given a valid version string, else 0. Valid versions are in the format
#
#	<v1>.<v2>...<vx>[a-z,_{_package_weights_}[vy]]
#

_ververify_cache_={}

def ververify(myorigval,silent=1):
	# Lookup the cache first
	try:
		return _ververify_cache_[myorigval]
	except KeyError:
		pass

	if len(myorigval) == 0:
		if not silent:
			print "ERROR: package version is empty"
		_ververify_cache_[myorigval] = 0
		return 0
	myval = string.split(myorigval,'.')
	if len(myval)==0:
		if not silent:
			print "ERROR: package name has empty version string"
		_ververify_cache_[myorigval] = 0
		return 0
	# all but the last version must be a numeric
	for x in myval[:-1]:
		if not len(x):
			if not silent:
				print "ERROR: package version has two points in a row"
			_ververify_cache_[myorigval] = 0
			return 0
		try:
			foo = string.atoi(x)
		except:
			if not silent:
				print "ERROR: package version contains non-numeric '"+x+"'"
			_ververify_cache_[myorigval] = 0
			return 0
	if not len(myval[-1]):
			if not silent:
				print "ERROR: package version has trailing dot"
			_ververify_cache_[myorigval] = 0
			return 0
	try:
		foo = string.atoi(myval[-1])
		_ververify_cache_[myorigval] = 1
		return 1
	except:
		pass

	# ok, our last component is not a plain number or blank, let's continue
	if myval[-1][-1] in string.lowercase:
		try:
			foo = string.atoi(myval[-1][:-1])
			return 1
			_ververify_cache_[myorigval] = 1
			# 1a, 2.0b, etc.
		except:
			pass
	# ok, maybe we have a 1_alpha or 1_beta2; let's see
	ep=string.split(myval[-1],"_")
	if len(ep)!= 2:
		if not silent:
			print "ERROR: package version has more than one letter at then end"
		_ververify_cache_[myorigval] = 0
		return 0
	try:
		foo = string.atoi(ep[0])
	except:
		# this needs to be numeric, i.e. the "1" in "1_alpha"
		if not silent:
			print "ERROR: package version must have numeric part before the '_'"
		_ververify_cache_[myorigval] = 0
		return 0

	for mye in _package_ends_:
		if ep[1][0:len(mye)] == mye:
			if len(mye) == len(ep[1]):
				# no trailing numeric is ok
				_ververify_cache_[myorigval] = 1
				return 1
			else:
				try:
					foo = string.atoi(ep[1][len(mye):])
					_ververify_cache_[myorigval] = 1
					return 1
				except:
					# if no _package_weights_ work, *then* we return 0
					pass	
	if not silent:
		print "ERROR: package version extension after '_' is invalid"
	_ververify_cache_[myorigval] = 0
	return 0


def isjustname(mypkg):
	myparts = string.split(mypkg,'-')
	for x in myparts:
		if ververify(x):
			return 0
	return 1


_isspecific_cache_={}

def isspecific(mypkg):
	"now supports packages with no category"
	try:
		return _isspecific_cache_[mypkg]
	except:
		pass

	mysplit = string.split(mypkg,"/")
	if not isjustname(mysplit[-1]):
			_isspecific_cache_[mypkg] = 1
			return 1
	_isspecific_cache_[mypkg] = 0
	return 0


#######################################################################
#
# pkgsplit()
#
#	''			-> ERROR: package name without name or version part
#	'x'			-> ERROR: package name without name or version part
#	'x-'			-> ERROR: package name with empty name or version part
#	'-1'			-> ERROR: package name with empty name or version part
#	'glibc-1.2-8.9-r7'	-> None	
#	'glibc-2.2.5-r7'	-> ['glibc', '2.2.5', 'r7']
#	'foo-1.2-1'		->
#	'Mesa-3.0'		-> ['Mesa', '3.0', 'r0']
#
# This function can be used as a package verification function. If it is a
# valid name, pkgsplit will return a list containing: [ pkgname,
# pkgversion(norev), pkgrev ].
#

_pkgsplit_cache_={}

def pkgsplit(mypkg, silent=1):
	try:
		return _pkgsplit_cache_[mypkg]
	except KeyError:
		pass

	myparts = string.split(mypkg,'-')
	if len(myparts) < 2:
		if not silent:
			print "ERROR: package name without name or version part" 
		_pkgsplit_cache_[mypkg] = None
		return None
	for x in myparts:
		if len(x) == 0:
			if not silent:
				print "ERROR: package name with empty name or version part"
			_pkgsplit_cache_[mypkg] = None
			return None
	# verify rev
	revok = 0
	myrev = myparts[-1]
	if len(myrev) and myrev[0] == "r":
		try:
			string.atoi(myrev[1:])
			revok = 1
		except: 
			pass
	if revok:
		if ververify(myparts[-2]):
			if len(myparts) == 2:
				_pkgsplit_cache_[mypkg] = None
				return None
			else:
				for x in myparts[:-2]:
					if ververify(x):
						_pkgsplit_cache_[mypkg]=None
						return None
						# names can't have versiony looking parts
				myval=[string.join(myparts[:-2],"-"),myparts[-2],myparts[-1]]
				_pkgsplit_cache_[mypkg]=myval
				return myval
		else:
			_pkgsplit_cache_[mypkg] = None
			return None

	elif ververify(myparts[-1],silent):
		if len(myparts)==1:
			if not silent:
				print "!!! Name error in",mypkg+": missing name part."
			_pkgsplit_cache_[mypkg]=None
			return None
		else:
			for x in myparts[:-1]:
				if ververify(x):
					if not silent: print "ERROR: package name has multiple version parts"
					_pkgsplit_cache_[mypkg] = None
					return None
			myval = [string.join(myparts[:-1],"-"), myparts[-1],"r0"]
			_pkgsplit_cache_[mypkg] = myval
			return myval
	else:
		_pkgsplit_cache_[mypkg] = None
		return None


#######################################################################
#
# catpkgsplit()
#
#	sys-libs/glibc-1.2-r7	-> ['sys-libs', 'glibc', '1.2', 'r7']
#	glibc-1.2-r7		-> ['null', 'glibc', '1.2', 'r7']
#

_catpkgsplit_cache_ = {}

def catpkgsplit(mydata,silent=1):
	"returns [cat, pkgname, version, rev ]"
	try:
		return _catpkgsplit_cache_[mydata]
	except KeyError:
		pass

	mysplit = mydata.split("/")
	p_split = None
	if len(mysplit) == 1:
		retval = ["null"]
		p_split = pkgsplit(mydata,silent)
	elif len(mysplit)==2:
		retval = [mysplit[0]]
		p_split = pkgsplit(mysplit[1],silent)
	if not p_split:
		_catpkgsplit_cache_[mydata] = None
		return None
	retval.extend(p_split)
	_catpkgsplit_cache_[mydata] = retval
	return retval


#######################################################################
#
# vercmp()
#
# This takes two version strings and returns an integer to tell you whether
# the versions are the same, val1>val2 or val2>val1.
#
#	1   <> 2 = -1.0
#	2   <> 1 = 1.0
#	1   <> 1.0 = 0
#	1   <> 1.1 = -1.0
#	1.1 <> 1_p2 = 1.0
#

_vercmp_cache_ = {}

def vercmp(val1,val2):
	# quick short-circuit
	if val1 == val2:
		return 0
	valkey = val1+" "+val2

	# cache lookup
	try:
		return _vercmp_cache_[valkey]
		try:
			return - _vercmp_cache_[val2+" "+val1]
		except KeyError:
			pass
	except KeyError:
		pass
	
	# consider 1_p2 vc 1.1
	# after expansion will become (1_p2,0) vc (1,1)
	# then 1_p2 is compared with 1 before 0 is compared with 1
	# to solve the bug we need to convert it to (1,0_p2)
	# by splitting _prepart part and adding it back _after_expansion

	val1_prepart = val2_prepart = ''
	if val1.count('_'):
		val1, val1_prepart = val1.split('_', 1)
	if val2.count('_'):
		val2, val2_prepart = val2.split('_', 1)

	# replace '-' by '.'
	# FIXME: Is it needed? can val1/2 contain '-'?

	val1 = string.split(val1,'-')
	if len(val1) == 2:
		val1[0] = val1[0] +"."+ val1[1]
	val2 = string.split(val2,'-')
	if len(val2) == 2:
		val2[0] = val2[0] +"."+ val2[1]

	val1 = string.split(val1[0],'.')
	val2 = string.split(val2[0],'.')

	# add back decimal point so that .03 does not become "3" !
	for x in range(1,len(val1)):
		if val1[x][0] == '0' :
			val1[x] = '.' + val1[x]
	for x in range(1,len(val2)):
		if val2[x][0] == '0' :
			val2[x] = '.' + val2[x]

	# extend varion numbers
	if len(val2) < len(val1):
		val2.extend(["0"]*(len(val1)-len(val2)))
	elif len(val1) < len(val2):
		val1.extend(["0"]*(len(val2)-len(val1)))

	# add back _prepart tails
	if val1_prepart:
		val1[-1] += '_' + val1_prepart
	if val2_prepart:
		val2[-1] += '_' + val2_prepart
	# The above code will extend version numbers out so they
	# have the same number of digits.
	for x in range(0,len(val1)):
		cmp1 = relparse(val1[x])
		cmp2 = relparse(val2[x])
		for y in range(0,3):
			myret = cmp1[y] - cmp2[y]
			if myret != 0:
				_vercmp_cache_[valkey] = myret
				return myret
	_vercmp_cache_[valkey] = 0
	return 0


#######################################################################
#
# pkgcomp()
#
# Compares two packages, which should have been split via pkgsplit()
#

def pkgcmp(pkg1,pkg2):
	"""if returnval is less than zero, then pkg2 is newer than pkg1, zero if equal and positive if older."""
	
	print pkg1[1],pkg2[1]

	mycmp = vercmp(pkg1[1],pkg2[1])
	if mycmp > 0:
		return 1
	if mycmp < 0:
		return -1
	r1=string.atoi(pkg1[2][1:])
	r2=string.atoi(pkg2[2][1:])
	if r1 > r2:
		return 1
	if r2 > r1:
		return -1
	return 0


#beautiful directed graph object
class digraph:
	def __init__(self):
		self.dict={}
		#okeys = keys, in order they were added (to optimize firstzero() ordering)
		self.okeys=[]
	
	def addnode(self,mykey,myparent):
		if not self.dict.has_key(mykey):
			self.okeys.append(mykey)
			if myparent==None:
				self.dict[mykey]=[0,[]]
			else:
				self.dict[mykey]=[0,[myparent]]
				self.dict[myparent][0]=self.dict[myparent][0]+1
			return
		if myparent and (not myparent in self.dict[mykey][1]):
			self.dict[mykey][1].append(myparent)
			self.dict[myparent][0]=self.dict[myparent][0]+1
	
	def delnode(self,mykey):
		if not self.dict.has_key(mykey):
			return
		for x in self.dict[mykey][1]:
			self.dict[x][0]=self.dict[x][0]-1
		del self.dict[mykey]
		while 1:
			try:
				self.okeys.remove(mykey)	
			except ValueError:
				break
	
	def allnodes(self):
		"returns all nodes in the dictionary"
		return self.dict.keys()
	
	def firstzero(self):
		"returns first node with zero references, or NULL if no such node exists"
		for x in self.okeys:
			if self.dict[x][0]==0:
				return x
		return None 

	def allzeros(self):
		"returns all nodes with zero references, or NULL if no such node exists"
		zerolist = []
		for x in self.dict.keys():
			if self.dict[x][0]==0:
				zerolist.append(x)
		return zerolist

	def hasallzeros(self):
		"returns 0/1, Are all nodes zeros? 1 : 0"
		zerolist = []
		for x in self.dict.keys():
			if self.dict[x][0]!=0:
				return 0
		return 1

	def empty(self):
		if len(self.dict)==0:
			return 1
		return 0

	def hasnode(self,mynode):
		return self.dict.has_key(mynode)

	def copy(self):
		mygraph=digraph()
		for x in self.dict.keys():
			mygraph.dict[x]=self.dict[x][:]
			mygraph.okeys=self.okeys[:]
		return mygraph

