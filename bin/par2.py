#!/usr/bin/python

# Import the os module, for the os.walk function
import os
import sys
import re

exitStatus = 0
RE_FILES = re.compile("Target: \"(.*?)\" - found.")

# Set the directory you want to start from
if len(sys.argv) < 2:
    print "Usage: par2.py <directory>"
    sys.exit(2)

rootDir = sys.argv[1]
for dirName, subdirList, fileList in os.walk(rootDir, topdown=False):
    if len(fileList) > 32000:
        print "WARNING! Too many files in directory {0}. par2 handles max. 32000, skipping".format(dirName)
        if exitStatus < 2:
            exitStatus = 1
        continue

    if '.dir.par2' not in fileList:
        if not fileList:
            print "Empty directory {0}, skipping".format(dirName)
            continue
        parOutput = os.popen('par2create {0}/.dir.par2 {0}/*'.format(dirName)).read()
    else:
        parOutput = os.popen('par2verify {0}/.dir.par2 {0}/*'.format(dirName)).read()
        if "Repair is not possible." in parOutput:
            print "CRITICAL! Unrecoverable error in directory {0}".format(dirName)
            exitStatus = 2
        elif "Repair is required." in parOutput:
            print "WARNING! Recoverable error in directory {0}".format(dirName)
            if exitStatus < 2:
                exitStatus = 1
        elif "All files are correct, repair is not required." in parOutput:
            #print parOutput
            parFiles = RE_FILES.findall(parOutput)
            diffFiles = [f for f in list(set(fileList).difference(parFiles)) if not f.endswith('.par2')]
            if diffFiles:
                print "WARNING! Unprotected files in directory {0}: {1}".format(dirName, ','.join(diffFiles))
                if exitStatus < 2:
                    exitStatus = 1

sys.exit(exitStatus)
