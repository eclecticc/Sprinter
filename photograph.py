"""
The Photograph script takes time-lapse pictures using the M240 gcode.

The skeleton of this script is based on Outline by Len Trigg and several of the stock Skeinforge modules by Enrique Perez.

In order to install the Photograph script within the skeinforge tool chain, put photograph.py in the skeinforge_application/skeinforge_plugins/craft_plugins/ folder. Then edit  skeinforge_application/skeinforge_plugins/profile_plugins/extrusion.py and add the Photograph script to the tool chain sequence by inserting 'photograph' into the tool sequence  in getCraftSequence(). The best place is at the end of the sequence, right before 'export'.

==Operation==
The default 'Activate Photograph' checkbox is off, enable it to take photos.

==Settings==
===Photograph Procedure Choice===
Default is 'End of Layer'

====End of Layer====
Takes a photograph once at the start of the first layer and then at the end of each layer

====Corner of Layer====
Takes a photograph at the minimum Y of each layer

====Least Change between Layers====
Minimizes the X and Y distance between photographs on subsequent layers

"""

from __future__ import absolute_import
#Init has to be imported first because it has code to workaround the python bug where relative imports don't work if the module is imported as a main module.
import __init__

from fabmetheus_utilities.fabmetheus_tools import fabmetheus_interpret
from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
from fabmetheus_utilities import settings
from skeinforge_application.skeinforge_utilities import skeinforge_craft
from skeinforge_application.skeinforge_utilities import skeinforge_polyfile
from skeinforge_application.skeinforge_utilities import skeinforge_profile
import os
import sys

__author__ = 'Nirav Patel (nrp@eclecti.cc)'
__date__ = '$Date: 2011/20/08 $'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'


def getCraftedText(fileName, text, repository=None):
	'Photograph text.'
	return getCraftedTextFromText(archive.getTextIfEmpty(fileName, text), repository)

def getCraftedTextFromText(gcodeText, repository=None):
	'Photograph text.'
	if gcodec.isProcedureDoneOrFileIsEmpty(gcodeText, 'photograph'):
		return gcodeText
	if repository == None:
		repository = settings.getReadRepository(PhotographRepository())
	if not repository.activatePhotograph.value:
		return gcodeText
	if repository.endPhotograph.value:
		return PhotographSkein().getCraftedGcode(gcodeText, repository)
	elif repository.cornerPhotograph.value:
		return PhotographCorner().getCraftedGcode(gcodeText, repository)
	elif repository.closestPhotograph.value:
		return PhotographClosest().getCraftedGcode(gcodeText, repository)
	return gcodeText

def getNewRepository():
	'Get new repository.'
	return PhotographRepository()

def writeOutput(fileName, shouldAnalyze=True):
	'Photograph.  Remote trigger photographs at specified times.'
	skeinforge_craft.writeChainTextWithNounMessage(fileName, 'photograph', shouldAnalyze)
	
	
class PhotographRepository:
	'A class to handle the photograph settings.'
	def __init__(self):
		'Set the default settings, execute title & settings fileName.'
		skeinforge_profile.addListsToCraftTypeRepository('skeinforge_application.skeinforge_plugins.craft_plugins.photograph.html', self)
		self.fileNameInput = settings.FileNameInput().getFromFileName(
			fabmetheus_interpret.getGNUTranslatorGcodeFileTypeTuples(), 'Open File for Photograph', self, '')
		self.openWikiManualHelpPage = settings.HelpPage().getOpenFromAbsolute(
			'http://fabmetheus.crsndoo.com/wiki/index.php/Skeinforge_Photograph')
		self.activatePhotograph = settings.BooleanSetting().getFromValue('Activate Photograph:', self, False)
		self.photographProcedureChoiceLabel = settings.LabelDisplay().getFromName('Photograph Procedure Choice: ', self )
		photographLatentStringVar = settings.LatentStringVar()
		self.endPhotograph = settings.Radio().getFromRadio( photographLatentStringVar, 'End of Layer', self, True )
		self.cornerPhotograph = settings.Radio().getFromRadio( photographLatentStringVar, 'Corner of Layer', self, False )
		self.closestPhotograph = settings.Radio().getFromRadio( photographLatentStringVar, 'Least Change between Layers', self, False )
		self.executeTitle = 'Photograph'

	def execute(self):
		'Photograph button has been clicked.'
		fileNames = skeinforge_polyfile.getFileOrDirectoryTypesUnmodifiedGcode(
			self.fileNameInput.value, fabmetheus_interpret.getImportPluginFileNames(), self.fileNameInput.wasCancelled)
		for fileName in fileNames:
			writeOutput(fileName)
			

class PhotographSkein:
	'A class to photograph at the end of each layer.'
	def __init__(self):
		self.distanceFeedRate = gcodec.DistanceFeedRate()
		self.lineIndex = 0
		self.lines = None
		self.firstLayer = True
		self.lastY = 0
		self.lastX = 0
		
	def addPhotographLine(self):
		self.distanceFeedRate.addLine('M240')
		
	def getCraftedGcode( self, gcodeText, photographRepository ):
		"Parse gcode text and store the photograph gcode."
		self.photographRepository = photographRepository
		self.lines = archive.getTextLines(gcodeText)
		for line in self.lines[self.lineIndex :]:
			self.parseLine(line)
		return self.distanceFeedRate.output.getvalue()
		
	def parseLine(self, line):
		"Parse a gcode line and add it to the photograph skein."
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if self.firstLayer and firstWord == '(<layer>':
			self.firstLayer = False
			self.addPhotographLine()
		elif firstWord == '(</layer>)':
			self.addPhotographLine()
		self.distanceFeedRate.addLine(line)

class PhotographCorner( PhotographSkein ):
	'A class to photograph at the minimum y/x corner of each layer'
	def findBestOfLayer( self, lineIndex ):
		cornerIndex = None
		minY = sys.maxint
		minX = sys.maxint
		for i in range(lineIndex,len(self.lines)):
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(self.lines[i])
			if len(splitLine) < 1:
				continue
			firstWord = splitLine[0]
			if firstWord == '(</layer>)':
				return cornerIndex
			elif firstWord == 'G1':
				location = gcodec.getLocationFromSplitLine(None, splitLine);
				if location.y != 0:
					if location.y <= minY:
						if location.y < minY or (location.x != 0 and location.x < minX):
							minY = location.y
							minX = location.x
							cornerIndex = i
						
		return cornerIndex

	def getCraftedGcode( self, gcodeText, photographRepository ):
		"Parse gcode text and store the photograph gcode."
		self.photographRepository = photographRepository
		self.lines = archive.getTextLines(gcodeText)
		bestIndex = None
		for i in range(0,len(self.lines)):
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(self.lines[i])
			if len(splitLine) < 1:
				continue
			firstWord = splitLine[0]
			if firstWord == '(<layer>':
				bestIndex = self.findBestOfLayer(i)
			self.distanceFeedRate.addLine(self.lines[i])
			# take the photograph after the move
			if i == bestIndex:
				self.addPhotographLine()
		return self.distanceFeedRate.output.getvalue()

class PhotographClosest( PhotographCorner ):
	'A class to minimize the distance between photographs on each layer'
	def findBestOfLayer( self, lineIndex ):
		closestIndex = None
		bestDistance = float('inf')
		savedY = 0
		savedX = 0
		for i in range(lineIndex,len(self.lines)):
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(self.lines[i])
			if len(splitLine) < 1:
				continue
			firstWord = splitLine[0]
			if firstWord == '(</layer>)':
				return closestIndex
			elif firstWord == 'G1':
				location = gcodec.getLocationFromSplitLine(None, splitLine)
				if location.y != 0 and location.x != 0:
					distance = (location.y-self.lastY)**2+(location.x-self.lastX)**2
					if distance < bestDistance:
						closestIndex = i
						savedY = location.y
						savedX = location.x
						bestDistance = distance
		if closestIndex != None:
			self.lastY = savedY
			self.lastX = savedX
		return closestIndex

def main():
	'Display the photograph dialog.'
	if len(sys.argv) > 1:
		writeOutput(' '.join(sys.argv[1 :]))
	else:
		settings.startMainLoopFromConstructor(getNewRepository())

if __name__ == '__main__':
	main()
