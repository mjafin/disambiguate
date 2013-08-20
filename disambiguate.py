import sys, getopt, re, time, pysam
from array import array
from os import path, makedirs

# "natural comparison" for strings
def nat_cmp(a, b):
	convert = lambda text: int(text) if text.isdigit() else text # lambda function to convert text to int if number present
	alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ] # split string to piecewise strings and string numbers
	#return cmp(alphanum_key(a), alphanum_key(b)) # use internal cmp to compare piecewise strings and numbers
	return (alphanum_key(a) > alphanum_key(b))-(alphanum_key(a) < alphanum_key(b))

# read reads into a list object for as long as the read qname is constant (sorted file). Return the first read with new qname or None
def read_next_reads(fileobject, listobject):
	qnamediff = False
	while not qnamediff:
		try:
			myRead=fileobject.next()
		except StopIteration:
			#print "5"
			return None # return None as the name of the new reads (i.e. no more new reads)
		if nat_cmp(myRead.qname, listobject[0].qname)==0:
			listobject.append(myRead)
		else:
			qnamediff = True
	return myRead # this is the first read with a new qname

# disambiguate between two lists of reads
def disambiguate(humanlist, mouselist):
	dv = 2**13 # a high quality score to replace missing quality scores (no real quality score should be this high)
	sa = array('i',(dv for i in range(0,4))) # score array, with [human_1_QS, human_2_QS, mouse_1_QS, mouse_2_QS]
	for read in humanlist:
		if 0x4&read.flag: # flag 0x4 means unaligned
			continue
		QScore = read.opt('XO') + read.opt('NM') + read.opt('NH')
      # directionality (_1 or _2)
		d12 = 0 if 0x40&read.flag else 1
		if sa[d12]>QScore:
			sa[d12]=QScore # update to lowest (i.e. 'best') quality score
	for read in mouselist:
		if 0x4&read.flag: # flag 0x4 means unaligned
			continue
		QScore = read.opt('XO') + read.opt('NM') + read.opt('NH')
      # directionality (_1 or _2)
		d12 = 2 if 0x40&read.flag else 3
		if sa[d12]>QScore:
			sa[d12]=QScore # update to lowest (i.e. 'best') quality score
	if min(sa[0:2])==min(sa[2:4]) and max(sa[0:2])==max(sa[2:4]): # ambiguous
		return 0
	elif min(sa[0:2]) < min(sa[2:4]) or min(sa[0:2]) == min(sa[2:4]) and max(sa[0:2]) < max(sa[2:4]):
		# assign to human
		return 1
	else:
		# assign to mouse
		return -1

#code
def main(argv):
	"""
	This is the main function to call for disambiguating between a human and mouse BAM files that have alignments from the same source of fastq files.
	It is part of the explant RNA/DNA-Seq workflow where an informatics approach is used to distinguish between human and mouse RNA/DNA reads.
	
	For reads that have aligned to both organisms, the functionality is based on comparing quality scores from either Tophat of BWA (under development).
	For Tophat, the sum of the flags XO, NM and NH is evaluated and the lowest sum wins the paired end reads. For equal scores, the reads are assigned as ambiguous.
	
	Usage: disambiguate.py -h <human.bam> -m <mouse.bam> -o <outputdir> (-d -i <intermediatedir> -s <samplenameprefix>)
	If <samplenameprefix> is provided it will be used in the output filenames, otherwise the output filenames will be named after <mouse.bam> and <human.bam>
	Note well that Tophat2 always renames its output as accepted_hits.bam regardless of the fastq filenames and therefore it is a very good idea to provide a <samplenameprefix>
	
	For usage help call disambiguate(.main) with flag --help
	
	Code by Miika Ahdesmaki July-August 2013.
	"""
	humanfile = ''
	mousefile = ''
	samplenameprefix = ''
	outputdir = 'disambres/'
	intermdir = 'intermfiles/'
	disablesort = False
	starttime = time.clock()
	# parse input arguments
	try:
		opts, args = getopt.getopt(argv,"h:m:o:di:s:",["help"])
		if len(opts) < 2:
			print 'Usage: disambiguate.py -h <human.bam> -m <mouse.bam> -o <outputdir> (-d -i <intermediatedir> -s <samplenameprefix>)'
			print 'This script orders the BAM files according to read name unless disabled using -d'
			sys.exit()
	except getopt.GetoptError:
		print 'Usage: disambiguate.py -h <human.bam> -m <mouse.bam> -o <outputdir> (-d -i <intermediatedir> -s <samplenameprefix>)'
		print 'This script orders the BAM files according to read name unless disabled using -d'
		sys.exit(2)
	for opt, arg in opts:
		if opt == '--help':
			print 'disambiguate.py -h <human.bam> -m <mouse.bam> -o <outputdir> (-d -i <intermediatedir> -s <samplenameprefix>)'
			print 'This script orders the BAM files according to read name unless disabled using -d'
			sys.exit(2)
		elif opt in ("-h"):
			humanfile = arg
		elif opt in ("-m"):
			mousefile = arg
		elif opt in ("-o"):
			outputdir = arg
		elif opt in ("-d"):
			disablesort = True
		elif opt in ("-i"):
			intermdir = arg
		elif opt in ("-i"):
			samplenameprefix = arg
	if len(humanfile) < 1 or len(mousefile) < 1:
		print "Two input BAM files must be specified using options -h and -m"
		sys.exit(2)
	if len(samplenameprefix) < 1
		humanprefix = path.basename(humanfile.replace(".bam",""))
		mouseprefix = path.basename(mousefile.replace(".bam",""))
	else:
		humanprefix = samplenameprefix
		mouseprefix = samplenameprefix
	samplenameprefix = None
	
	if disablesort:
		humanfilesorted = humanfile # assumed to be sorted externally...
		mousefilesorted = mousefile # assumed to be sorted externally...
	else:
		if not path.isdir(intermdir):
			makedirs(intermdir)
		humanfilesorted = path.join(intermdir,humanprefix+".human.namesorted.bam")
		mousefilesorted = path.join(intermdir,mouseprefix+".mouse.namesorted.bam")
		print "Name sorting human and mouse BAM files using samtools"
		pysam.sort("-n","-m","2000000000",humanfile,humanfilesorted.replace(".bam",""))
		pysam.sort("-n","-m","2000000000",mousefile,mousefilesorted.replace(".bam",""))
		print "Intermediate name sorted BAM files stored under " + intermdir
	
	print "Processing human and mouse files for ambiguous reads"
   # read in human reads and form a dictionary
	myHumanFile = pysam.Samfile(humanfilesorted, "rb" )
	myMouseFile = pysam.Samfile(mousefilesorted, "rb" )
	if not path.isdir(outputdir):
		makedirs(outputdir)
	myHumanUniqueFile = pysam.Samfile(path.join(outputdir, humanprefix+".human.bam"), "wb", template=myHumanFile) 
	myHumanAmbiguousFile = pysam.Samfile(path.join(outputdir, humanprefix+".ambiguousHuman.bam"), "wb", template=myHumanFile)
	myMouseUniqueFile = pysam.Samfile(path.join(outputdir, mouseprefix+".mouse.bam"), "wb", template=myMouseFile)
	myMouseAmbiguousFile = pysam.Samfile(path.join(outputdir, mouseprefix+".ambiguousMouse.bam"), "wb", template=myMouseFile)
	
	#initialise
	try: 
		nexthumread=myHumanFile.next()
		nextmouread=myMouseFile.next()
	except StopIteration:
		print "No reads in one or either of the input files"
		sys.exit(2)
	
	EOFmouse = EOFhuman = False
	while not EOFmouse&EOFhuman:
		while not (nat_cmp(nexthumread.qname,nextmouread.qname) == 0):
			# check order between current human and mouse qname (find a point where they're identical, i.e. in sync)
			while nat_cmp(nexthumread.qname,nextmouread.qname) > 0 and not EOFmouse: # mouse is "behind" human, output to mouse disambiguous
				myMouseUniqueFile.write(nextmouread)
				try:
					nextmouread=myMouseFile.next()
				except StopIteration:
					#print "1"
					EOFmouse=True
			while nat_cmp(nexthumread.qname,nextmouread.qname) < 0 and not EOFhuman: # human is "behind" mouse, output to human disambiguous
				myHumanUniqueFile.write(nexthumread)
				try:
					nexthumread=myHumanFile.next()
				except StopIteration:
					#print "2"
					EOFhuman=True
			if EOFhuman or EOFmouse:	
				break
		# at this point the read qnames are identical and/or we've reached EOF
		humlist = list()
		moulist = list()
		#print nexthumread.qname + " " + nextmouread.qname + " " + str(nat_cmp(nexthumread.qname,nextmouread.qname))
		if nat_cmp(nexthumread.qname,nextmouread.qname) == 0:
			humlist.append(nexthumread)
			nexthumread = read_next_reads(myHumanFile, humlist) # read more reads with same qname (the function modifies humlist directly)
			if nexthumread == None:
				EOFhuman = True
			moulist.append(nextmouread)
			nextmouread = read_next_reads(myMouseFile, moulist) # read more reads with same qname (the function modifies moulist directly)
			if nextmouread == None:
				EOFmouse = True
		
		# perform comparison to check mouse, human or ambiguous
		if len(moulist) > 0 and len(humlist) > 0:
			myAmbiguousness = disambiguate(humlist, moulist)
			#print myAmbiguousness
			if myAmbiguousness < 0: # mouse
				for myRead in moulist:
					myMouseUniqueFile.write(myRead)
			elif myAmbiguousness > 0: # human
				for myRead in humlist:
					myHumanUniqueFile.write(myRead)
			else: # ambiguous
				for myRead in moulist:
					myMouseAmbiguousFile.write(myRead)
				for myRead in humlist:
					myHumanAmbiguousFile.write(myRead)
		if EOFhuman:
			#flush the rest of the mouse reads
			while not EOFmouse:
				myMouseUniqueFile.write(nextmouread)
				try:
					nextmouread=myMouseFile.next()
				except StopIteration:
					#print "3"
					EOFmouse=True
		if EOFmouse:
			#flush the rest of the human reads
			while not EOFhuman:
				myHumanUniqueFile.write(nexthumread)
				try:
					nexthumread=myHumanFile.next()
				except StopIteration:
					#print "4"
					EOFhuman=True

		#end while not
	
	myHumanFile.close()
	myMouseFile.close()
	myHumanUniqueFile.close()
	myHumanAmbiguousFile.close()
	myMouseUniqueFile.close()
	myMouseAmbiguousFile.close()
   
	print "Time taken in minutes " + str((time.clock() - starttime)/60)

if __name__ == "__main__":
	main(sys.argv[1:])
