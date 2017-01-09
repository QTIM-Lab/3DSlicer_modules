""" This is Step 5. The user has the opportunity to threshold a segment 
	of the subtraction map for analysis.
"""

from __main__ import qt, ctk, slicer

from BeersSingleStep import *
from Helper import *

import string

""" ThresholdStep inherits from BeersSingleStep, with itself inherits
	from a ctk workflow class. 
"""

class ThresholdStep( BeersSingleStep ) :

	def __init__( self, stepid ):

		""" This method creates a drop-down menu that includes the whole step.
			The description also acts as a tooltip for the button. There may be 
			some way to override this. The initialize method is inherited
			from ctk.
		"""

		self.initialize( stepid )
		self.setName( '5. Threshold' )

		self.__vrDisplayNode = None
		self.__threshold = [ -1, -1 ]
		
		# Initialize volume rendering.
		self.__vrLogic = slicer.modules.volumerendering.logic()
		self.__vrOpacityMap = None

		self.__roiSegmentationNode = None
		self.__roiVolume = None

		self.__parent = super( ThresholdStep, self )

	def createUserInterface( self ):

		""" This UI takes advantage of a pre-built slicer thresholding widget.
		"""

		self.__layout = self.__parent.createUserInterface()

		step_label = qt.QLabel( """Use the slider bar below to set an intensity threshold. Any pixels within your ROI and within the intensity threshold will be segmented.""")
		step_label.setWordWrap(True)
		self.__primaryGroupBox = qt.QGroupBox()
		self.__primaryGroupBox.setTitle('Information')
		self.__primaryGroupBoxLayout = qt.QFormLayout(self.__primaryGroupBox)
		self.__primaryGroupBoxLayout.addRow(step_label)
		self.__layout.addRow(self.__primaryGroupBox)

		self.__thresholdGroupBox = qt.QGroupBox()
		self.__thresholdGroupBox.setTitle('Threshold Range')
		self.__thresholdGroupBoxLayout = qt.QFormLayout(self.__thresholdGroupBox)
		threshLabel = qt.QLabel('Select Intensity Range:')
		threshLabel.alignment = 4
		self.__threshRange = slicer.qMRMLRangeWidget()
		self.__threshRange.decimals = 0
		self.__threshRange.singleStep = 1

		self.__thresholdGroupBoxLayout.addRow(threshLabel)
		self.__thresholdGroupBoxLayout.addRow(self.__threshRange)
		self.__layout.addRow(self.__thresholdGroupBox)

		self.__threshRange.connect('valuesChanged(double,double)', self.onThresholdChanged)
		qt.QTimer.singleShot(0, self.killButton)

	def onThresholdChanged(self):
	
		""" Upon changing the slider (or intializing this step), this method
			updates the volume rendering node and label volume accordingly.
		"""

		# if self.__vrOpacityMap == None:
			# return
		
		range0 = self.__threshRange.minimumValue
		range1 = self.__threshRange.maximumValue

		# self.__vrOpacityMap.RemoveAllPoints()
		# self.__vrOpacityMap.AddPoint(0,0)
		# self.__vrOpacityMap.AddPoint(0,0)
		# self.__vrOpacityMap.AddPoint(range0-1,0)
		# self.__vrOpacityMap.AddPoint(range0,1)
		# self.__vrOpacityMap.AddPoint(range1,1)
		# self.__vrOpacityMap.AddPoint(range1+1,0)

		# Use vtk to update the label volume. TO-DO: Investigate these methods further.

		thresh = vtk.vtkImageThreshold()
		if vtk.VTK_MAJOR_VERSION <= 5:
			thresh.SetInput(self.__roiVolume.GetImageData())
		else:
			thresh.SetInputData(self.__roiVolume.GetImageData())
		thresh.ThresholdBetween(range0, range1)
		thresh.SetInValue(1)
		thresh.SetOutValue(0)
		thresh.ReplaceOutOn()
		thresh.ReplaceInOn()
		thresh.Update()

		self.__roiSegmentationNode.SetAndObserveImageData(thresh.GetOutput())

	def killButton(self):
		# ctk creates a useless final page button. This method gets rid of it.
		bl = slicer.util.findChildren(text='ReviewStep')
		if len(bl):
			bl[0].hide()

	def validate( self, desiredBranchId ):
		# For now, no validation required.
		self.__parent.validationSucceeded(desiredBranchId)

	def onEntry(self, comingFrom, transitionType):

		""" This method removes and adds nodes necessary to for a segementation
			display, intializes color and opacity maps, and calls the main 
			thresholding function for the first time.
		"""

		super(ThresholdStep, self).onEntry(comingFrom, transitionType)
		pNode = self.parameterNode()
		self.updateWidgetFromParameters(pNode)

		if pNode.GetParameter('followupVolumeID') == None or pNode.GetParameter('followupVolumeID') == '':
			Helper.SetBgFgVolumes(pNode.GetParameter('baselineVolumeID'), pNode.GetParameter('croppedVolumeID'))
			self.__visualizedVolume = Helper.getNodeByID(pNode.GetParameter('baselineVolumeID'))
		else:
			self.__visualizedVolume = Helper.getNodeByID(pNode.GetParameter('subtractVolumeID'))
			Helper.SetBgFgVolumes(pNode.GetParameter('subtractVolumeID'),  pNode.GetParameter('croppedVolumeID'))

		# Retrieves necessary nodes.
		roiVolume = Helper.getNodeByID(pNode.GetParameter('croppedVolumeID'))
		self.__roiVolume = roiVolume
		self.__roiSegmentationNode = Helper.getNodeByID(pNode.GetParameter('croppedVolumeSegmentationID'))
		self.__modelSegmentationNode = Helper.getNodeByID(pNode.GetParameter('modelSegmentationID'))
		vrDisplayNodeID = pNode.GetParameter('vrDisplayNodeID')

		self.__roiNodeID = pNode.GetParameter('roiNodeID')
		if self.__roiNodeID == None:
			Helper.Error('Failed to find ROI node -- it should have been defined in the previous step!')
			return

		if self.__vrDisplayNode == None:
			if vrDisplayNodeID != '':
				self.__vrDisplayNode = slicer.mrmlScene.GetNodeByID(vrDisplayNodeID)
			if self.__vrDisplayNode == None:
				self.InitVRDisplayNode()
				self.__vrDisplayNodeID = self.__vrDisplayNode.GetID()
		else:
			Helper.InitVRDisplayNode(self.__vrDisplayNode, roiVolume.GetID(), self.__roiNodeID)	

		# Does work to intialize color and opacity maps
		self.__vrOpacityMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetScalarOpacity()
		vrColorMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetRGBTransferFunction()
		
		# ROIRange = roiVolume.GetImageData().GetScalarRange()

		# vrColorMap.RemoveAllPoints()
		# vrColorMap.AddRGBPoint(0, 0, 0, 0) 
		# vrColorMap.AddRGBPoint(ROIRange[0]-1, 0, 0, 0) 
		# vrColorMap.AddRGBPoint(ROIRange[0], 0.8, 0.8, 0) 
		# vrColorMap.AddRGBPoint(ROIRange[1], 0.8, 0.8, 0) 
		# vrColorMap.AddRGBPoint(ROIRange[1]+1, 0, 0, 0) 

		self.__vrDisplayNode.VisibilityOn()

		threshRange = [self.__threshRange.minimumValue, self.__threshRange.maximumValue]
		# self.__vrOpacityMap.RemoveAllPoints()
		# self.__vrOpacityMap.AddPoint(0,0)
		# self.__vrOpacityMap.AddPoint(0,0)
		# self.__vrOpacityMap.AddPoint(threshRange[0]-1,0)
		# self.__vrOpacityMap.AddPoint(threshRange[0],1)
		# self.__vrOpacityMap.AddPoint(threshRange[1],1)
		# self.__vrOpacityMap.AddPoint(threshRange[1]+1,0)

		# labelsColorNode = slicer.modules.colors.logic().GetColorTableNodeID(10)
		# self.__roiSegmentationNode.GetDisplayNode().SetAndObserveColorNodeID(labelsColorNode)

		# Adds segementation label volume.
		Helper.SetLabelVolume(self.__roiSegmentationNode.GetID())

		range0 = 0
		range1 = self.__threshRange.maximum
		thresh = vtk.vtkImageThreshold()
		if vtk.VTK_MAJOR_VERSION <= 5:
			thresh.SetInput(self.__roiVolume.GetImageData())
		else:
			thresh.SetInputData(self.__roiVolume.GetImageData())
		thresh.ThresholdBetween(range0, range1)
		thresh.SetInValue(1)
		thresh.SetOutValue(0)
		thresh.ReplaceOutOn()
		thresh.ReplaceInOn()
		thresh.Update()

		print self.__modelSegmentationNode
		print 'model printed'
		print thresh.GetOutput()
		print 'thresh printed'
		self.__modelSegmentationNode.SetAndObserveImageData(thresh.GetOutput())

		# Adjusts threshold information.
		self.onThresholdChanged()

		pNode.SetParameter('currentStep', self.stepid)
	
		qt.QTimer.singleShot(0, self.killButton)

	def onExit(self, goingTo, transitionType):   
		pNode = self.parameterNode()
		if self.__vrDisplayNode != None:
			# self.__vrDisplayNode.VisibilityOff()
			pNode.SetParameter('vrDisplayNodeID', self.__vrDisplayNode.GetID())
		super(BeersSingleStep, self).onExit(goingTo, transitionType) 

	def updateWidgetFromParameters(self, pNode):

		""" Intializes the threshold and label volume established in the previous step.
		"""

		ROIVolume = Helper.getNodeByID(pNode.GetParameter('croppedVolumeID'))
		ROIRange = ROIVolume.GetImageData().GetScalarRange()
		self.__threshRange.minimum = ROIRange[0]
		self.__threshRange.maximum = ROIRange[1]

		thresholdRange = pNode.GetParameter('thresholdRange')
		if thresholdRange != '':
			rangeArray = string.split(thresholdRange, ',')
			self.__threshRange.minimumValue = float(rangeArray[0])
			self.__threshRange.maximumValue = float(rangeArray[1])
		else:
			Helper.Error('Unexpected parameter values! Error code CT-S03-TNA. Please report')

		segmentationID = pNode.GetParameter('croppedVolumeSegmentationID')
		self.__roiSegmentationNode = Helper.getNodeByID(segmentationID)

	def InitVRDisplayNode(self):

		"""	This method calls a series of steps necessary to initailizing a volume 
			rendering node with an ROI.
		"""
		if self.__vrDisplayNode == None or self.__vrDisplayNode == '':
			pNode = self.parameterNode()
			self.__vrDisplayNode = self.__vrLogic.CreateVolumeRenderingDisplayNode()
			slicer.mrmlScene.AddNode(self.__vrDisplayNode)
			# Documentation on UnRegister is scant so far.
			self.__vrDisplayNode.UnRegister(self.__vrLogic) 

			v = slicer.mrmlScene.GetNodeByID(self.parameterNode().GetParameter('croppedVolumeID'))
			Helper.InitVRDisplayNode(self.__vrDisplayNode, v.GetID(), '')
			v.AddAndObserveDisplayNodeID(self.__vrDisplayNode.GetID())

		# This is a bit messy.
		viewNode = slicer.util.getNode('vtkMRMLViewNode1')

		self.__vrDisplayNode.AddViewNodeID(viewNode.GetID())
		
		self.__vrLogic.CopyDisplayToVolumeRenderingDisplayNode(self.__vrDisplayNode)

		self.__vrOpacityMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetScalarOpacity()
		self.__vrColorMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetRGBTransferFunction()

		# Renders in yellow, like the label map in the next steps.
		self.__vrColorMap.RemoveAllPoints()
		self.__vrColorMap.AddRGBPoint(0, 0.01, 0.01, 0)
		self.__vrColorMap.AddRGBPoint(500, 0.2, 0.2, 0)