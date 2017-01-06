""" This is Step 6, the final step. This merely takes the label volume
	and applies it to the pre- and post-contrast images. It also does
	some volume rendering. There is much left to do on this step, including
	screenshots and manual cleanup of erroneous pixels. A reset button upon
	completion would also be helpful. This step has yet to be fully commented.
"""

from __main__ import qt, ctk, slicer

from BeersSingleStep import *
from Helper import *
from Editor import EditorWidget
from EditorLib import EditorLib

import string

""" ReviewStep inherits from BeersSingleStep, with itself inherits
	from a ctk workflow class. 
"""

class ReviewStep( BeersSingleStep ) :

	def __init__( self, stepid ):

		""" This method creates a drop-down menu that includes the whole step.
			The description also acts as a tooltip for the button. There may be 
			some way to override this. The initialize method is inherited
			from ctk.
		"""
		self.initialize( stepid )
		self.setName( '6. Review' )

		self.__pNode = None
		self.__vrDisplayNode = None
		self.__threshold = [ -1, -1 ]
		
		# initialize VR stuff
		self.__vrLogic = slicer.modules.volumerendering.logic()
		self.__vrOpacityMap = None

		self.__roiSegmentationNode = None
		self.__roiVolume = None

		self.__parent = super( ReviewStep, self )
		self.__RestartActivated = False

	def createUserInterface( self ):

		""" This step is mostly empty. A volume rendering threshold is added to be useful.
		"""

		self.__layout = self.__parent.createUserInterface()

		step_label = qt.QLabel( """Review your segmentation. Use the 3D Visualization slider to see your segmentation in context with your image. Use the Editor panel to apply spot edits to your segmentation. If you would like to start over, see the Restart box below""")
		step_label.setWordWrap(True)
		self.__primaryGroupBox = qt.QGroupBox()
		self.__primaryGroupBox.setTitle('Information')
		self.__primaryGroupBoxLayout = qt.QFormLayout(self.__primaryGroupBox)
		self.__primaryGroupBoxLayout.addRow(step_label)
		self.__layout.addRow(self.__primaryGroupBox)

		self.__threshRange = slicer.qMRMLRangeWidget()
		self.__threshRange.decimals = 0
		self.__threshRange.singleStep = 1
		self.__threshRange.connect('valuesChanged(double,double)', self.onThresholdChanged)
		qt.QTimer.singleShot(0, self.killButton)

		ThreshGroupBox = qt.QGroupBox()
		ThreshGroupBox.setTitle('3D Visualization Intensity Threshold')
		ThreshGroupBoxLayout = qt.QFormLayout(ThreshGroupBox)
		ThreshGroupBoxLayout.addRow(self.__threshRange)
		self.__layout.addRow(ThreshGroupBox)

		editorWidgetParent = slicer.qMRMLWidget()
		editorWidgetParent.setLayout(qt.QVBoxLayout())
		editorWidgetParent.setMRMLScene(slicer.mrmlScene)
		self.__editorWidget = EditorWidget(parent=editorWidgetParent)
		self.__editorWidget.setup()
		self.__layout.addRow(editorWidgetParent)
		self.hideUnwantedEditorUIElements()

		RestartGroupBox = qt.QGroupBox()
		RestartGroupBox.setTitle('Restart')
		RestartGroupBoxLayout = qt.QFormLayout(RestartGroupBox)

		self.__RestartButton = qt.QPushButton('Return to Step 1')
		RestartGroupBoxLayout.addRow(self.__RestartButton)

		self.__RemoveRegisteredImage = qt.QCheckBox()
		self.__RemoveRegisteredImage.checked = True
		self.__RemoveRegisteredImage.setToolTip("Delete new images resulting from registration.")
		RestartGroupBoxLayout.addRow("Delete registered images: ", self.__RemoveRegisteredImage)  

		self.__RemoveCroppedSubtractionMap = qt.QCheckBox()
		self.__RemoveCroppedSubtractionMap.checked = True
		self.__RemoveCroppedSubtractionMap.setToolTip("Delete images produced via normalization.")
		RestartGroupBoxLayout.addRow("Delete normalized images: ", self.__RemoveCroppedSubtractionMap)   

		self.__RemoveFullSubtractionMap = qt.QCheckBox()
		self.__RemoveFullSubtractionMap.checked = True
		self.__RemoveFullSubtractionMap.setToolTip("Delete the full version of your subtraction map.")
		RestartGroupBoxLayout.addRow("Delete full subtraction map: ", self.__RemoveFullSubtractionMap)    

		self.__RemoveCroppedMap = qt.QCheckBox()
		self.__RemoveCroppedMap.checked = True
		self.__RemoveCroppedMap.setToolTip("Delete the cropped version of your segmented volume.")
		RestartGroupBoxLayout.addRow("Delete cropped map: ", self.__RemoveCroppedMap)     

		self.__RemoveROI = qt.QCheckBox()
		self.__RemoveROI.checked = False
		self.__RemoveROI.setToolTip("Delete the ROI resulting from thresholding your original ROI.")
		RestartGroupBoxLayout.addRow("Delete thresholded ROI: ", self.__RemoveROI)    

		self.__RemoveROIModel = qt.QCheckBox()
		self.__RemoveROIModel.checked = False
		self.__RemoveROIModel.setToolTip("Delete the ROI resulting from your 3D Model.")
		RestartGroupBoxLayout.addRow("Delete ROI from model: ", self.__RemoveROIModel) 

		self.__RestartButton.connect('clicked()', self.Restart)
		self.__RestartActivated = True

		self.__layout.addRow(RestartGroupBox)

	def hideUnwantedEditorUIElements(self):
		self.__editorWidget.volumes.hide()
		# for widgetName in slicer.util.findChildren(self.__editorWidget.editBoxFrame):
		for widgetName in slicer.util.findChildren(self.__editorWidget.helper):
			# widget = slicer.util.findChildren(self.__editorWidget.editBoxFrame)
			print widgetName.objectName
			# print widgetName.parent.name
			# widgetName.hide()
		for widget in ['DrawEffectToolButton', 'RectangleEffectToolButton', 'IdentifyIslandsEffectToolButton', 'RemoveIslandsEffectToolButton', 'SaveIslandEffectToolButton', 'RowFrame2']:
			slicer.util.findChildren(self.__editorWidget.editBoxFrame, widget)[0].hide()
		print slicer.util.findChildren('','EditColorFrame')

	def Restart( self ):

		slicer.mrmlScene.RemoveNode(Helper.getNodeByID(self.__pNode.GetParameter('clippingModelNodeID')))
		slicer.mrmlScene.RemoveNode(Helper.getNodeByID(self.__pNode.GetParameter('clippingMarkupNodeID')))
		slicer.mrmlScene.RemoveNode(Helper.getNodeByID(self.__pNode.GetParameter('subtractVolumeID')))
		slicer.mrmlScene.RemoveNode(Helper.getNodeByID(self.__pNode.GetParameter('croppedVolumeID')))
		slicer.mrmlScene.RemoveNode(Helper.getNodeByID(self.__pNode.GetParameter('roiNodeID')))
		slicer.mrmlScene.RemoveNode(Helper.getNodeByID(self.__pNode.GetParameter('roiTransformID')))
		slicer.mrmlScene.RemoveNode(Helper.getNodeByID(self.__pNode.GetParameter('clippingModelNodeID')))
		# slicer.mrmlScene.RemoveNode(Helper.getNodeByID(self.__pNode.GetParameter('vrDisplayNodeID')))

		for node in [self.__pNode.GetParameter('normalizeVolume_0'), self.__pNode.GetParameter('normalizeVolume_1'),self.__pNode.GetParameter('registrationVolumeID')]:
			if node != self.__pNode.GetParameter('baselineVolumeID') and node != self.__pNode.GetParameter('followupVolumeID'):
				slicer.mrmlScene.RemoveNode(Helper.getNodeByID(node))

		self.__pNode.SetParameter('outputList', '')	
		self.__pNode.SetParameter('modelList', '')	
		self.__pNode.SetParameter('baselineVolumeID', '')		
		self.__pNode.SetParameter('clippingMarkupNodeID', '')
		self.__pNode.SetParameter('clippingModelNodeID', '')
		self.__pNode.SetParameter('normalizeVolume_0', '')
		self.__pNode.SetParameter('normalizeVolume_1', '')
		self.__pNode.SetParameter('croppedVolumeID', '')
		self.__pNode.SetParameter('croppedVolumeSegmentationID', '')
		self.__pNode.SetParameter('followupVolumeID', '')
		self.__pNode.SetParameter('roiNodeID', '')
		self.__pNode.SetParameter('roiTransformID', '')
		self.__pNode.SetParameter('subtractVolumeID', '')
		# self.__pNode.SetParameter('vrDisplayNodeID', '')
		self.__pNode.SetParameter('thresholdRange', '')
		self.__pNode.SetParameter('registrationVolumeID', '')
		self.__pNode.SetParameter('modelSegmentationID', '')

		Helper.SetLabelVolume('')

		if self.__RestartActivated:
			self.workflow().goForward()

	def onThresholdChanged(self): 
	
		if self.__vrOpacityMap == None:
			return
		
		range0 = self.__threshRange.minimumValue
		range1 = self.__threshRange.maximumValue

		self.__vrOpacityMap.RemoveAllPoints()
		self.__vrOpacityMap.AddPoint(range0-75,0)
		self.__vrOpacityMap.AddPoint(range0,.02)
		self.__vrOpacityMap.AddPoint(range1,.04)
		self.__vrOpacityMap.AddPoint(range1+75,.1)

	def killButton(self):

		stepButtons = slicer.util.findChildren(className='ctkPushButton')
		
		backButton = ''
		nextButton = ''
		for stepButton in stepButtons:
			if stepButton.text == 'Next':
				nextButton = stepButton
			if stepButton.text == 'Back':
				backButton = stepButton

		nextButton.hide()

		# ctk creates a useless final page button. This method gets rid of it.
		bl = slicer.util.findChildren(text='ReviewStep')
		ex = slicer.util.findChildren('','EditColorFrame')
		if len(bl):
			bl[0].hide()
		if len(ex):
			ex[0].hide()
		else:
			print 'fail'

		self.__editLabelMapsFrame = slicer.util.findChildren('','EditLabelMapsFrame')[0]
		self.__toolsColor = EditorLib.EditColor(self.__editLabelMapsFrame)

	def validate( self, desiredBranchId ):

		# For now, no validation required.
		self.__parent.validationSucceeded(desiredBranchId)

	def onEntry(self, comingFrom, transitionType):
		super(ReviewStep, self).onEntry(comingFrom, transitionType)

		self.__RestartActivated = True

		pNode = self.parameterNode()
		self.__pNode = pNode

		self.__clippingModelNode = Helper.getNodeByID(pNode.GetParameter('clippingModelNodeID'))
		self.__baselineVolumeID = pNode.GetParameter('baselineVolumeID')
		self.__followupVolumeID = pNode.GetParameter('followupVolumeID')
		self.__subtractVolumeID = pNode.GetParameter('subtractVolumeID')
		self.__roiNodeID = pNode.GetParameter('roiNodeID')
		self.__baselineVolumeNode = Helper.getNodeByID(self.__baselineVolumeID)
		self.__followupVolumeNode = Helper.getNodeByID(self.__followupVolumeID)
		self.__subtractVolumeNode = Helper.getNodeByID(self.__subtractVolumeID)
		self.__vrDisplayNodeID = pNode.GetParameter('vrDisplayNodeID') 
		self.__roiSegmentationNode = Helper.getNodeByID(pNode.GetParameter('croppedVolumeSegmentationID'))
		self.__roiVolumeNode = Helper.getNodeByID(pNode.GetParameter('croppedVolumeID'))

		self.__editorWidget.setMergeNode(self.__roiSegmentationNode)
		self.__clippingModelNode.GetDisplayNode().VisibilityOn()


		if self.__followupVolumeID == None or self.__followupVolumeID == '':
			self.__visualizedNode = self.__baselineVolumeNode
			self.__visualizedID = self.__baselineVolumeID
			vrRange = self.__baselineVolumeNode.GetImageData().GetScalarRange()
		else:
			self.__visualizedID = self.__followupVolumeID
			self.__visualizedNode = self.__followupVolumeNode
			vrRange = self.__followupVolumeNode.GetImageData().GetScalarRange()

		ROIRange = self.__roiSegmentationNode.GetImageData().GetScalarRange()

		if self.__vrDisplayNode == None:
			if self.__vrDisplayNodeID != '':
				self.__vrDisplayNode = slicer.mrmlScene.GetNodeByID(self.__vrDisplayNodeID)

		self.__vrDisplayNode.SetCroppingEnabled(1)
		self.__visualizedNode.AddAndObserveDisplayNodeID(self.__vrDisplayNode.GetID())
		Helper.InitVRDisplayNode(self.__vrDisplayNode, self.__visualizedID, self.__roiNodeID)

		self.__threshRange.minimum = vrRange[0]
		self.__threshRange.maximum = vrRange[1]
		self.__threshRange.setValues(vrRange[1]/3, 2*vrRange[1]/3)

		self.__vrOpacityMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetScalarOpacity()
		vrColorMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetRGBTransferFunction()

		vrColorMap.RemoveAllPoints()
		vrColorMap.AddRGBPoint(vrRange[0], 0.8, 0.8, 0) 
		vrColorMap.AddRGBPoint(vrRange[1], 0.8, 0.8, 0) 


		self.__vrDisplayNode.VisibilityOn()

		Helper.SetBgFgVolumes(self.__visualizedID,'')
		Helper.SetLabelVolume(self.__roiSegmentationNode.GetID())

		self.onThresholdChanged()

		pNode.SetParameter('currentStep', self.stepid)
	
		qt.QTimer.singleShot(0, self.killButton)

	def onExit(self, goingTo, transitionType):   
		# extra error checking, in case the user manages to click ReportROI button
		super(BeersSingleStep, self).onExit(goingTo, transitionType) 