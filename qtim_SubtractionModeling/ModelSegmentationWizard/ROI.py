""" This is Step 4. The user selects a ROI and subtracts the two images.
	Much of this step is copied from ChangeTracker, located at 
	https://github.com/fedorov/ChangeTrackerPy. Previously, I had been
	using the cubic ROI tool. This tool, although built in to Slicer,
	could cause painful slowdowns, and sometimes crashed. I also was
	having trouble applying transformations to the ROI. I now instead
	use the VolumeClip with Model module created by Andras Lasso.
	Its logic is copied wholesale into this code, although I understand
	that this is unnessecary, and that one can call such logic via the
	Slicer interface. This is done partly out of laziness, and partly
	for protection against version changes unbeknownst to me.
"""

from __main__ import qt, ctk, slicer

from ModelSegmentationStep import *
from Helper import *
import PythonQt

""" ROIStep inherits from ModelSegmentationStep, with itself inherits
	from a ctk workflow class. PythonQT is required for this step
	in order to get the ROI selector widget.
"""

class ROIStep( ModelSegmentationStep ) :

	def __init__( self, stepid ):

		""" This method creates a drop-down menu that includes the whole step.
		The description also acts as a tooltip for the button. There may be 
		some way to override this. The initialize method is inherited
		from ctk.
		"""

		self.initialize( stepid )
		self.setName( '4. Define Region(s) of Interest' )
		self.__logic = VolumeClipWithModelLogic()
		self.__parameterNode = None
		self.__parameterNodeObserver = None
		self.__clippingModelNode = None
		self.__clippingMarkupNode = None
		self.__clippingMarkupNodeObserver = None
		self.__ModelList = []
		self.__ROIList = []
		self.__OutputList = []

		self.__parent = super( ROIStep, self )

		self.__vrDisplayNode = None
		self.__vrDisplayNodeID = ''
		self.__vrOpacityMap = None
		self.__threshold = [ -1, -1 ]

		self.__roiTransformNode = None
		self.__baselineVolume = None

		self.__roi = None
		self.__roiObserverTag = None

		self.__CubicROI = False
		self.__ConvexROI = True
		self.__fillValue = 0

	def createUserInterface( self ):

		""" This UI allows you to either select a predefined ROI via the 
			vtkMRMLAnnotationROINode feature, or to specify your own using
			PythonQt's qMRMLAnnotationROIWidget. That creates a fairly large
			box with 3 sliders to adjust your ROI in three dimensions. There is
			also a ROI drop-down selector for those who have a pre-loaded ROI.
		"""

		self.__layout = self.__parent.createUserInterface()

		step_label = qt.QLabel( """Create either a convex ROI or a box ROI around the area you wish to threshold. Only voxels inside these ROIs will be thresholded in the next step. Click to add points to the convex ROI, or click and drag existing points to move them. A curved ROI will be filled in around these points. Similarly, click and drag the points on the box ROI to change its location and size.""")
		step_label.setWordWrap(True)
		self.__primaryGroupBox = qt.QGroupBox()
		self.__primaryGroupBox.setTitle('Information')
		self.__primaryGroupBoxLayout = qt.QFormLayout(self.__primaryGroupBox)
		self.__primaryGroupBoxLayout.addRow(step_label)
		self.__layout.addRow(self.__primaryGroupBox)

		self.__convexGroupBox = qt.QGroupBox()
		self.__convexGroupBox.setTitle('Convex ROI')
		self.__convexGroupBoxLayout = qt.QFormLayout(self.__convexGroupBox)

		self.__clippingModelSelector = slicer.qMRMLNodeComboBox()
		self.__clippingModelSelector.nodeTypes = (("vtkMRMLModelNode"), "")
		self.__clippingModelSelector.addEnabled = True
		self.__clippingModelSelector.removeEnabled = False
		self.__clippingModelSelector.noneEnabled = True
		self.__clippingModelSelector.showHidden = False
		self.__clippingModelSelector.renameEnabled = True
		self.__clippingModelSelector.selectNodeUponCreation = True
		self.__clippingModelSelector.showChildNodeTypes = False
		self.__clippingModelSelector.setMRMLScene(slicer.mrmlScene)
		self.__clippingModelSelector.setToolTip("Choose the clipping surface model.")
		self.__convexGroupBoxLayout.addRow("Current Convex ROI Model: ", self.__clippingModelSelector)

		self.__layout.addRow(self.__convexGroupBox)

		# self.__addConvexGroupBox = qt.QGroupBox()
		# self.__addConvexGroupBox.setTitle('Add Labelmap as Convex ROI')
		# self.__addConvexGroupBoxLayout = qt.QFormLayout(self.__addConvexGroupBox)

		# self.__convexLabelMapSelector = slicer.qMRMLNodeComboBox()
		# self.__convexLabelMapSelector.nodeTypes = (("vtkMRMLLabelMapVolumeNode"), "")
		# self.__convexLabelMapSelector.addEnabled = True
		# self.__convexLabelMapSelector.removeEnabled = False
		# self.__convexLabelMapSelector.noneEnabled = True
		# self.__convexLabelMapSelector.showHidden = False
		# self.__convexLabelMapSelector.renameEnabled = True
		# self.__convexLabelMapSelector.selectNodeUponCreation = True
		# self.__convexLabelMapSelector.showChildNodeTypes = False
		# self.__convexLabelMapSelector.setMRMLScene(slicer.mrmlScene)
		# self.__convexLabelMapSelector.setToolTip("Choose a labelmap to turn into a convex ROI.")
		# self.__addConvexGroupBoxLayout.addRow("Labelmap: ", self.__convexLabelMapSelector)

		# self.__addConvexButton = qt.QPushButton('Add Labelmap')
		# self.__addConvexGroupBoxLayout.addRow(self.__addConvexButton)
		# self.__addConvexGroupBox.setEnabled(0)

		# self.__layout.addRow(self.__addConvexGroupBox)

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

		# self.__clippingMarkupSelector = slicer.qMRMLNodeComboBox()
		# self.__clippingMarkupSelector.nodeTypes = (("vtkMRMLMarkupsFiducialNode"), "")
		# self.__clippingMarkupSelector.addEnabled = True
		# self.__clippingMarkupSelector.removeEnabled = False
		# self.__clippingMarkupSelector.noneEnabled = True
		# self.__clippingMarkupSelector.showHidden = False
		# self.__clippingMarkupSelector.renameEnabled = True
		# self.__clippingMarkupSelector.baseName = "Markup"
		# self.__clippingMarkupSelector.setMRMLScene(slicer.mrmlScene)
		# self.__clippingMarkupSelector.setToolTip("Use markup points to determine a convex ROI.")
		# ModelFormLayout.addRow("Convex ROI Markups: ", self.__clippingMarkupSelector)

		# ROICollapisbleButton = ctk.ctkCollapsibleButton()
		# ROICollapisbleButton.text = "Cubic ROI:"
		# # ROICollapisbleButton.collapse()
		# # print dir(ROICollapisbleButton)
		# self.__layout.addWidget(ROICollapisbleButton)
		# ROIFormLayout = qt.QFormLayout(ROICollapisbleButton)

		# self.valueEditWidgets = {"ClipOutsideSurface": True, "FillValue": 0}
		# # self.nodeSelectorWidgets = {"InputVolume": self.inputVolumeSelector, "ClippingModel": self.clippingModelSelector, "ClippingMarkup": self.clippingMarkupSelector, "OutputVolume": self.outputVolumeSelector}

		# roiLabel = qt.QLabel( 'Select ROI:' )
		# self.__roiSelector = slicer.qMRMLNodeComboBox()
		# self.__roiSelector.nodeTypes = ['vtkMRMLAnnotationROINode']
		# self.__roiSelector.toolTip = "ROI defining the structure of interest"
		# self.__roiSelector.setMRMLScene(slicer.mrmlScene)
		# self.__roiSelector.addEnabled = 1
		# self.__roiSelector.setEnabled(0)

		# ROIFormLayout.addRow( roiLabel, self.__roiSelector )

		# self.__roiSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onROIChanged)

		# voiGroupBox = qt.QGroupBox()
		# voiGroupBox.setTitle( 'Define ROI' )
		# ROIFormLayout.addRow( voiGroupBox )

		# voiGroupBoxLayout = qt.QFormLayout( voiGroupBox )

		# # PythonQt has a pre-configured ROI widget. Useful!
		# self.__roiWidget = PythonQt.qSlicerAnnotationsModuleWidgets.qMRMLAnnotationROIWidget()
		# voiGroupBoxLayout.addRow( self.__roiWidget )
		# self.__roiWidget.setEnabled(0)

		# Intialize Volume Rendering...
		self.__vrLogic = slicer.modules.volumerendering.logic()

		qt.QTimer.singleShot(0, self.killButton)

		# self.__clippingModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onClippingModelSelect)
		self.__clippingModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onClippingModelSelect)

	def onClippingModelSelect(self, node):

		if node != None and node != '':
			if node.GetID() not in self.__ModelList:
				self.__ModelList.append(node.GetID())
				new_clippingMarkupNode = slicer.vtkMRMLMarkupsFiducialNode()
				new_clippingMarkupNode.SetScene(slicer.mrmlScene)
				slicer.mrmlScene.AddNode(new_clippingMarkupNode)
				self.__ROIList.append([node.GetID(), new_clippingMarkupNode.GetID(), 'Convex'])
			
			self.__clippingModelNode = node
			self.setAndObserveClippingMarkupNode(Helper.getNodeByID(self.__ROIList[self.__ModelList.index(node.GetID())][1]))

	def setAndObserveClippingMarkupNode(self, clippingMarkupNode):

		# Remove observer to old parameter node
		if self.__clippingMarkupNode and self.__clippingMarkupNodeObserver:
			self.__clippingMarkupNode.RemoveObserver(self.__clippingMarkupNodeObserver)
			self.__clippingMarkupNodeObserver = None
		# Set and observe new parameter node
		self.__clippingMarkupNode = clippingMarkupNode
		if self.__clippingMarkupNode:
			self.__clippingMarkupNodeObserver = self.__clippingMarkupNode.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onClippingMarkupNodeModified)

		print self.__clippingMarkupNodeObserver
		# Update GUI
		self.updateModelFromClippingMarkupNode()

	def onClippingMarkupNodeModified(self, observer, eventid):
		print self.__ROIList
		self.updateModelFromClippingMarkupNode()

	def updateModelFromClippingMarkupNode(self):
		if not self.__clippingMarkupNode or not self.__clippingModelSelector.currentNode():
			return
		self.__logic.updateModelFromMarkup(self.__clippingMarkupNode, self.__clippingModelSelector.currentNode())

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

		# ctk creates a useless final page button. This method gets rid of it.
		bl = slicer.util.findChildren(text='ReviewStep')
		if len(bl):
			bl[0].hide()

	def validate( self, desiredBranchId ):

		# Makes sure there actually is a ROI...
		# roi = self.__roiSelector.currentNode()

		if self.__ModelList == []:
			self.__parent.validationFailed(desiredBranchId, 'Error', 'You must choose at least one ROI to continue.')
			
		self.__parent.validationSucceeded(desiredBranchId)

	def onEntry(self,comingFrom,transitionType):

		""" This method calls most other methods in this function to initialize the ROI
			wizard. This step in particular applies the ROI IJK/RAS coordinate transform
			calculated in the previous step and checks for any pre-existing ROIs. Also
			intializes the volume-rendering node.
		"""

		super(ROIStep, self).onEntry(comingFrom, transitionType)

		pNode = self.parameterNode()

		if pNode.GetParameter('followupVolumeID') == None or pNode.GetParameter('followupVolumeID') == '':
			Helper.SetBgFgVolumes(pNode.GetParameter('baselineVolumeID'), '')
			self.__visualizedVolume = Helper.getNodeByID(pNode.GetParameter('baselineVolumeID'))
		else:
			self.__visualizedVolume = Helper.getNodeByID(pNode.GetParameter('subtractVolumeID'))
			Helper.SetBgFgVolumes(pNode.GetParameter('subtractVolumeID'), '')

		if pNode.GetParameter('modelList') == '' or pNode.GetParameter('modelList') == None:
			self.__ROIList = []
			self.__ModelList = []
			self.__OutputList = []

		self.__baselineVolumeID = pNode.GetParameter('baselineVolumeID')
		self.__followupVolumeID = pNode.GetParameter('followupVolumeID')
		self.__subtractVolumeID = pNode.GetParameter('subtractVolumeID')
		self.__baselineVolumeNode = Helper.getNodeByID(self.__baselineVolumeID)
		self.__followupVolumeNode = Helper.getNodeByID(self.__followupVolumeID)
		self.__subtractVolumeNode = Helper.getNodeByID(self.__subtractVolumeID)
		self.__vrDisplayNodeID = pNode.GetParameter('vrDisplayNodeID') 

		if self.__vrDisplayNode == None:
			if self.__vrDisplayNodeID != '':
				self.__vrDisplayNode = slicer.mrmlScene.GetNodeByID(self.__vrDisplayNodeID)
			if self.__vrDisplayNode == None:
				self.InitVRDisplayNode()
				self.__vrDisplayNodeID = self.__vrDisplayNode.GetID()
		else:
			if self.__followupVolumeID == None or self.__followupVolumeID == '':
				Helper.InitVRDisplayNode(self.__vrDisplayNode, self.__baselineVolumeID, '')	
			else:
				Helper.InitVRDisplayNode(self.__vrDisplayNode, self.__followupVolumeID, '')	

		roiTransformID = pNode.GetParameter('roiTransformID')
		roiTransformNode = None

		if roiTransformID != '':
			roiTransformNode = Helper.getNodeByID(roiTransformID)
		else:
			roiTransformNode = slicer.vtkMRMLLinearTransformNode()
			slicer.mrmlScene.AddNode(roiTransformNode)
			pNode.SetParameter('roiTransformID', roiTransformNode.GetID())


		""" vtk, the image analysis library, and Slicer use different coordinate
			systems: IJK and RAS, respectively. This prep calculates a simple matrix 
			transformation on a ROI transform node to be used in the next step.
		"""

		# TO-DO: Understand the precise math behind this section of code..
		dm = vtk.vtkMatrix4x4()
		self.__visualizedVolume.GetIJKToRASDirectionMatrix(dm)
		dm.SetElement(0,3,0)
		dm.SetElement(1,3,0)
		dm.SetElement(2,3,0)
		dm.SetElement(0,0,abs(dm.GetElement(0,0)))
		dm.SetElement(1,1,abs(dm.GetElement(1,1)))
		dm.SetElement(2,2,abs(dm.GetElement(2,2)))
		roiTransformNode.SetAndObserveMatrixTransformToParent(dm)

		# I believe this changes the layout to four-up; will check.
		lm = slicer.app.layoutManager()
		lm.setLayout(3)
		pNode = self.parameterNode()
		Helper.SetLabelVolume(None)

		slices = [lm.sliceWidget('Red'),lm.sliceWidget('Yellow'),lm.sliceWidget('Green')]
		for s in slices:
			s.sliceLogic().GetSliceNode().SetSliceVisible(0)

		# Apply the transform node created in the previous step.
		roiTfmNodeID = pNode.GetParameter('roiTransformID')
		if roiTfmNodeID != '':
			self.__roiTransformNode = Helper.getNodeByID(roiTfmNodeID)
		else:
			Helper.Error('Internal error! Error code CT-S2-NRT, please report!')

		# If a ROI exists, grab it. Note that this function calls onROIChanged()
		# self.updateWidgetFromParameterNode(pNode)

		# Note that this clause initializes volume rendering.
		if self.__roi != None:
			self.__roi.SetDisplayVisibility(1)
			# self.InitVRDisplayNode()

		pNode.SetParameter('currentStep', self.stepid)
		
		qt.QTimer.singleShot(0, self.killButton)

	def onExit(self, goingTo, transitionType):

		if goingTo.id() == 'ThresholdStep':
			# Does a great deal of work to prepare for the segmentation step.
			self.ThresholdPrep()

			pNode = self.parameterNode()

			# lm = slicer.app.layoutManager()
			# slices = [lm.sliceWidget('Red'),lm.sliceWidget('Yellow'),lm.sliceWidget('Green')]
			# for s in slices:
			# 	s.sliceLogic().GetSliceNode().SetSliceVisible(0)

			pNode.SetParameter('clippingModelNodeID', self.__clippingModelSelector.currentNode().GetID())
			# pNode.SetParameter('clippingMarkupNodesID', self.__clippingMarkupSelector.currentNode().GetID())
			for ROI in self.__ROIList:
				# Helper.getNodeByID(ROI[0]).GetDisplayNode().VisibilityOff()
				Helper.getNodeByID(ROI[1]).GetDisplayNode().VisibilityOff()

			# if self.__roi != None:
			# 	self.__roi.RemoveObserver(self.__roiObserverTag)
			# 	self.__roi.SetDisplayVisibility(0)

			if self.__vrDisplayNode != None and self.__vrDisplayNode != '':
				# self.__vrDisplayNode.VisibilityOff()
				pNode.SetParameter('vrDisplayNodeID', self.__vrDisplayNode.GetID())

			if self.__CubicROI:
				pNode.SetParameter('roiNodeID', self.__roiSelector.currentNode().GetID())

		super(ROIStep, self).onExit(goingTo, transitionType)

	def ThresholdPrep(self):

		""" This method prepares for the following segmentation/thresholding
			step. It accomplishes a few things. It uses the cropvolume Slicer
			module to create a new, ROI-only node. It then creates a label volume
			and initializes threholds variables for the next step.
		"""

		pNode = self.parameterNode()
		baselineVolumeID = pNode.GetParameter('baselineVolumeID')
		followupVolumeID = pNode.GetParameter('followupVolumeID')

		followupVolume = Helper.getNodeByID(followupVolumeID)
		baselineVolume = Helper.getNodeByID(baselineVolumeID)

		for ROI_idx, ROI in enumerate(self.__ROIList):
			if ROI[2] == 'Convex' and ROI_idx == 0:

				if pNode.GetParameter('croppedVolumeID') == '' or pNode.GetParameter('croppedVolumeID') == None:
					outputVolume = slicer.vtkMRMLScalarVolumeNode()
					slicer.mrmlScene.AddNode(outputVolume)
				else:
					outputVolume = Helper.getNodeByID(pNode.GetParameter('croppedVolumeID'))

				Helper.SetLabelVolume(None)

				# Crop volume to Convex ROI
				inputVolume = self.__visualizedVolume
				clippingModel = Helper.getNodeByID(ROI[0])
				clipOutsideSurface = True
				self.__fillValue = inputVolume.GetImageData().GetScalarRange()[0] - 1

				print self.__fillValue

				self.__logic.clipVolumeWithModel(inputVolume, clippingModel, clipOutsideSurface, self.__fillValue, outputVolume)

				# self.__logic.showInSliceViewers(outputVolume, ["Red", "Yellow", "Green"])

				self.__OutputList.append(outputVolume.GetID())

				outputVolume.SetName(baselineVolume.GetName() + '_roi')

		pNode.SetParameter('outputList', '__'.join(self.__OutputList))
		pNode.SetParameter('modelList', '__'.join(self.__ModelList))

		# volumesLogic = slicer.modules.volumes.logic()
		# combinedOutputVolume = volumesLogic.CloneVolume(slicer.mrmlScene, baselineVolume, baselineVolume.GetName() + '_roi')
		# volumesLogic.ClearVolumeImageData(combinedOutputVolume)
		# combinedOutputImageData = combinedOutputVolume.GetImageData()
		# shape = list(combinedOutputVolume.GetImageData().GetDimensions())
		# shape.reverse()
		# combinedOutputArray = vtk.util.numpy_support.vtk_to_numpy(combinedOutputImageData.GetPointData().GetScalars()).reshape(shape)

		# for output_idx, output in enumerate(self.__OutputList):

		# 	outputNode = Helper.getNodeByID(output)
		# 	# outputImageData = outputNode.GetImageData()
		# 	# shape = list(outputNode.GetImageData().GetDimensions())
		# 	# shape.reverse()
		# 	# outputArray = vtk.util.numpy_support.vtk_to_numpy(outputImageData.GetPointData().GetScalars()).reshape(shape)

		# 	parameters = {}
		# 	parameters["inputVolume1"] = outputNode
		# 	parameters["inputVolume2"] = combinedOutputVolume
		# 	parameters['outputVolume'] = combinedOutputVolume
		# 	parameters['order'] = '1'

		# 	self.__cliNode = None
		# 	self.__cliNode = slicer.cli.run(slicer.modules.addscalarvolumes, self.__cliNode, parameters)



		pNode.SetParameter('croppedVolumeID',outputVolume.GetID())
		pNode.SetParameter('ROIType', 'convex')

			# if self.__CubicROI:
			# 	# Crop volume to Cubic ROI.
			# 	cropVolumeNode = slicer.vtkMRMLCropVolumeParametersNode()
			# 	cropVolumeNode.SetScene(slicer.mrmlScene)
			# 	cropVolumeNode.SetName('T1_Contrast_CropVolume_node')
			# 	cropVolumeNode.SetIsotropicResampling(True)
			# 	cropVolumeNode.SetSpacingScalingConst(0.5)
			# 	slicer.mrmlScene.AddNode(cropVolumeNode)

			# 	cropVolumeNode.SetInputVolumeNodeID(pNode.GetParameter('subtractVolumeID'))
			# 	cropVolumeNode.SetROINodeID(pNode.GetParameter('roiNodeID'))

			# 	cropVolumeLogic = slicer.modules.cropvolume.logic()
			# 	cropVolumeLogic.Apply(cropVolumeNode)

			# 	outputVolume = slicer.mrmlScene.GetNodeByID(cropVolumeNode.GetOutputVolumeNodeID())
			# 	outputVolume.SetName(baselineVolume.GetName() + '_subtraction_roi')
			# 	pNode.SetParameter('croppedSubtractVolumeID',cropVolumeNode.GetOutputVolumeNodeID())

			# 	pNode.SetParameter('ROIType', 'cubic')

		# Get starting threshold parameters.
		roiSegmentationID = pNode.GetParameter('croppedVolumeSegmentationID') 
		if roiSegmentationID == '':
			roiRange = outputVolume.GetImageData().GetScalarRange()

			thresholdParameter = str(0.5*(roiRange[0]+roiRange[1]))+','+str(roiRange[1])
			pNode.SetParameter('thresholdRange', thresholdParameter)

		# Create a label node for segmentation.
		vl = slicer.modules.volumes.logic()
		roiSegmentation = vl.CreateLabelVolume(slicer.mrmlScene, outputVolume, baselineVolume.GetName() + '_roi_annotation')
		pNode.SetParameter('croppedVolumeSegmentationID', roiSegmentation.GetID())

		modelSegmentation = vl.CreateLabelVolume(slicer.mrmlScene, outputVolume, baselineVolume.GetName() + '_roi_model')
		pNode.SetParameter('modelSegmentationID', modelSegmentation.GetID())

		self.__clippingMarkupNode.RemoveObserver(self.__clippingMarkupNodeObserver)
		self.__clippingMarkupNodeObserver = None

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

			v = self.__visualizedVolume
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

		if self.__followupVolumeID == None or self.__followupVolumeID == '':
			self.__visualizedNode = self.__baselineVolumeNode
			self.__visualizedID = self.__baselineVolumeID
			vrRange = self.__baselineVolumeNode.GetImageData().GetScalarRange()
		else:
			self.__visualizedID = self.__followupVolumeID
			self.__visualizedNode = self.__followupVolumeNode
			vrRange = self.__followupVolumeNode.GetImageData().GetScalarRange()

		self.__threshRange.minimum = vrRange[0]
		self.__threshRange.maximum = vrRange[1]
		self.__threshRange.setValues(vrRange[1]/3, 2*vrRange[1]/3)

		self.__vrOpacityMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetScalarOpacity()
		vrColorMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetRGBTransferFunction()

		vrColorMap.RemoveAllPoints()
		vrColorMap.AddRGBPoint(vrRange[0], 0.8, 0.8, 0) 
		vrColorMap.AddRGBPoint(vrRange[1], 0.8, 0.8, 0) 


	# def cleanup(self):
	# 	self.removeGUIObservers()
	# 	self.setAndObserveParameterNode(None)
	# 	self.setAndObserveClippingMarkupNode(None)
	# 	pass

	# def setAndObserveParameterNode(self, parameterNode):
	# 	if parameterNode == self.__parameterNode and self.__parameterNodeObserver:
	# 		# no change and node is already observed
	# 		return
	# 	# Remove observer to old parameter node
	# 	if self.__parameterNode and self.__parameterNodeObserver:
	# 		self.__parameterNode.RemoveObserver(self.__parameterNodeObserver)
	# 		self.__parameterNodeObserver = None
	# 	# Set and observe new parameter node
	# 	self.__parameterNode = parameterNode
	# 	if self.__parameterNode:
	# 		self.__parameterNodeObserver = self.__parameterNode.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onParameterNodeModified)
	# 	# Update GUI
	# 	self.updateGUIFromParameterNode()

	# def onParameterNodeModified(self, observer, eventid):
	# 	self.updateGUIFromParameterNode()

	# def getParameterNode(self):
		# return self.__parameterNode

	# def onROIChanged(self):

	# 	""" This method accounts for changing ROI nodes entirely, rather than the
	# 		parameters of individual nodes.
	# 	"""

	# 	roi = self.__roiSelector.currentNode()

	# 	if roi != None:
	# 		self.__roi = roi
	
	# 		pNode = self.parameterNode()

	# 		self.__vrDisplayNode.SetAndObserveROINodeID(roi.GetID())
	# 		self.__vrDisplayNode.SetCroppingEnabled(1)
	# 		self.__vrDisplayNode.VisibilityOn()

	# 		roi.SetAndObserveTransformNodeID(self.__roiTransformNode.GetID())

	# 		# Removes unneeded observers, freeing running time.
	# 		if self.__roiObserverTag != None:
	# 			self.__roi.RemoveObserver(self.__roiObserverTag)

	# 		self.__roiObserverTag = self.__roi.AddObserver('ModifiedEvent', self.processROIEvents)

	# 		roi.SetInteractiveMode(1)

	# 		self.__roiWidget.setMRMLAnnotationROINode(roi)
	# 		self.__roi.SetDisplayVisibility(1)
	 
	# def processROIEvents(self,node,event):
	# 	""" A rather repetitive step that does the hard work of computing
	# 		IJK boundaries in vtk and RAS boundaries in Slicer. Also adjusts
	# 		the opacity of the volume rendering node.
	# 	"""

	# 	# Get the IJK bounding box of the voxels inside ROI.
	# 	roiCenter = [0,0,0]
	# 	roiRadius = [0,0,0]

	# 	# Note that these methods modify roiCenter and roiRadius.
	# 	self.__roi.GetXYZ(roiCenter)
	# 	self.__roi.GetRadiusXYZ(roiRadius)

	# 	# TO-DO: Understand coordinate changes being performed.
	# 	roiCorner1 = [roiCenter[0]+roiRadius[0],roiCenter[1]+roiRadius[1],roiCenter[2]+roiRadius[2],1]
	# 	roiCorner2 = [roiCenter[0]+roiRadius[0],roiCenter[1]+roiRadius[1],roiCenter[2]-roiRadius[2],1]
	# 	roiCorner3 = [roiCenter[0]+roiRadius[0],roiCenter[1]-roiRadius[1],roiCenter[2]+roiRadius[2],1]
	# 	roiCorner4 = [roiCenter[0]+roiRadius[0],roiCenter[1]-roiRadius[1],roiCenter[2]-roiRadius[2],1]
	# 	roiCorner5 = [roiCenter[0]-roiRadius[0],roiCenter[1]+roiRadius[1],roiCenter[2]+roiRadius[2],1]
	# 	roiCorner6 = [roiCenter[0]-roiRadius[0],roiCenter[1]+roiRadius[1],roiCenter[2]-roiRadius[2],1]
	# 	roiCorner7 = [roiCenter[0]-roiRadius[0],roiCenter[1]-roiRadius[1],roiCenter[2]+roiRadius[2],1]
	# 	roiCorner8 = [roiCenter[0]-roiRadius[0],roiCenter[1]-roiRadius[1],roiCenter[2]-roiRadius[2],1]

	# 	ras2ijk = vtk.vtkMatrix4x4()
	# 	self.__subtractVolume.GetRASToIJKMatrix(ras2ijk)

	# 	roiCorner1ijk = ras2ijk.MultiplyPoint(roiCorner1)
	# 	roiCorner2ijk = ras2ijk.MultiplyPoint(roiCorner2)
	# 	roiCorner3ijk = ras2ijk.MultiplyPoint(roiCorner3)
	# 	roiCorner4ijk = ras2ijk.MultiplyPoint(roiCorner4)
	# 	roiCorner5ijk = ras2ijk.MultiplyPoint(roiCorner5)
	# 	roiCorner6ijk = ras2ijk.MultiplyPoint(roiCorner6)
	# 	roiCorner7ijk = ras2ijk.MultiplyPoint(roiCorner7)
	# 	roiCorner8ijk = ras2ijk.MultiplyPoint(roiCorner8)

	# 	lowerIJK = [0, 0, 0]
	# 	upperIJK = [0, 0, 0]

	# 	lowerIJK[0] = min(roiCorner1ijk[0],roiCorner2ijk[0],roiCorner3ijk[0],roiCorner4ijk[0],roiCorner5ijk[0],roiCorner6ijk[0],roiCorner7ijk[0],roiCorner8ijk[0])
	# 	lowerIJK[1] = min(roiCorner1ijk[1],roiCorner2ijk[1],roiCorner3ijk[1],roiCorner4ijk[1],roiCorner5ijk[1],roiCorner6ijk[1],roiCorner7ijk[1],roiCorner8ijk[1])
	# 	lowerIJK[2] = min(roiCorner1ijk[2],roiCorner2ijk[2],roiCorner3ijk[2],roiCorner4ijk[2],roiCorner5ijk[2],roiCorner6ijk[2],roiCorner7ijk[2],roiCorner8ijk[2])

	# 	upperIJK[0] = max(roiCorner1ijk[0],roiCorner2ijk[0],roiCorner3ijk[0],roiCorner4ijk[0],roiCorner5ijk[0],roiCorner6ijk[0],roiCorner7ijk[0],roiCorner8ijk[0])
	# 	upperIJK[1] = max(roiCorner1ijk[1],roiCorner2ijk[1],roiCorner3ijk[1],roiCorner4ijk[1],roiCorner5ijk[1],roiCorner6ijk[1],roiCorner7ijk[1],roiCorner8ijk[1])
	# 	upperIJK[2] = max(roiCorner1ijk[2],roiCorner2ijk[2],roiCorner3ijk[2],roiCorner4ijk[2],roiCorner5ijk[2],roiCorner6ijk[2],roiCorner7ijk[2],roiCorner8ijk[2])

	# 	# All of this ijk work is needed for using vtk to compute a sub-region.
	# 	image = self.__subtractVolume.GetImageData()
	# 	clipper = vtk.vtkImageClip()
	# 	clipper.ClipDataOn()
	# 	clipper.SetOutputWholeExtent(int(lowerIJK[0]),int(upperIJK[0]),int(lowerIJK[1]),int(upperIJK[1]),int(lowerIJK[2]),int(upperIJK[2]))
	# 	if vtk.VTK_MAJOR_VERSION <= 5:
	# 		clipper.SetInput(image)
	# 	else:
	# 		clipper.SetInputData(image)
	# 	clipper.Update()
	# 	roiImageRegion = clipper.GetOutput()

	# 	# Opacity thresholds are constantly adjusted to the range of pixels within the ROI.
	# 	intRange = roiImageRegion.GetScalarRange()
	# 	lThresh = 0.4*(intRange[0]+intRange[1])
	# 	uThresh = intRange[1]

	# 	self.__vrOpacityMap.RemoveAllPoints()
	# 	self.__vrOpacityMap.AddPoint(0,0)
	# 	self.__vrOpacityMap.AddPoint(lThresh-1,0)
	# 	self.__vrOpacityMap.AddPoint(lThresh,1)
	# 	self.__vrOpacityMap.AddPoint(uThresh,1)
	# 	self.__vrOpacityMap.AddPoint(uThresh+1,0)

	# 	# Center the camera on the new ROI. Author of ChangeTracker suggested errors in this method.
	# 	camera = slicer.mrmlScene.GetNodeByID('vtkMRMLCameraNode1')
	# 	camera.SetFocalPoint(roiCenter)

	# def updateWidgetFromParameterNode(self, parameterNode):

	# 	""" Effectively creates the ROI node upon entry, and then uses onROIChanged
	# 		to calculate its intial position.
	# 	"""

	# 	roiNodeID = parameterNode.GetParameter('roiNodeID')

	# 	if roiNodeID != '':
	# 		self.__roi = slicer.mrmlScene.GetNodeByID(roiNodeID)
	# 		self.__roiSelector.setCurrentNode(Helper.getNodeByID(self.__roi.GetID()))
	# 	else:
	# 		roi = slicer.vtkMRMLAnnotationROINode()
	# 		roi.Initialize(slicer.mrmlScene)
	# 		parameterNode.SetParameter('roiNodeID', roi.GetID())
	# 		self.__roiSelector.setCurrentNode(roi)
		
	# 	self.onROIChanged()
		

class VolumeClipWithModelLogic(ScriptedLoadableModuleLogic):
	"""This class should implement all the actual
	computation done by your module.  The interface
	should be such that other python code can import
	this class and make use of the functionality without
	requiring an instance of the Widget
	"""

	def createParameterNode(self):
		# Set default parameters
		node = ScriptedLoadableModuleLogic.createParameterNode(self)
		node.SetName(slicer.mrmlScene.GetUniqueNameByString(self.moduleName))
		node.SetParameter("ClipOutsideSurface", "1")
		node.SetParameter("FillValue", "-1")
		return node

	def clipVolumeWithModel(self, inputVolume, clippingModel, clipOutsideSurface, fillValue, outputVolume):
		"""
		Fill voxels of the input volume inside/outside the clipping model with the provided fill value
		"""
		
		# Determine the transform between the box and the image IJK coordinate systems
		
		rasToModel = vtk.vtkMatrix4x4()    
		if clippingModel.GetTransformNodeID() != None:
			modelTransformNode = slicer.mrmlScene.GetNodeByID(clippingModel.GetTransformNodeID())
			boxToRas = vtk.vtkMatrix4x4()
			modelTransformNode.GetMatrixTransformToWorld(boxToRas)
			rasToModel.DeepCopy(boxToRas)
			rasToModel.Invert()
			
		ijkToRas = vtk.vtkMatrix4x4()
		inputVolume.GetIJKToRASMatrix( ijkToRas )

		ijkToModel = vtk.vtkMatrix4x4()
		vtk.vtkMatrix4x4.Multiply4x4(rasToModel,ijkToRas,ijkToModel)
		modelToIjkTransform = vtk.vtkTransform()
		modelToIjkTransform.SetMatrix(ijkToModel)
		modelToIjkTransform.Inverse()
		
		transformModelToIjk=vtk.vtkTransformPolyDataFilter()
		transformModelToIjk.SetTransform(modelToIjkTransform)
		transformModelToIjk.SetInputConnection(clippingModel.GetPolyDataConnection())

		# Use the stencil to fill the volume
		
		# Convert model to stencil
		polyToStencil = vtk.vtkPolyDataToImageStencil()
		polyToStencil.SetInputConnection(transformModelToIjk.GetOutputPort())
		polyToStencil.SetOutputSpacing(inputVolume.GetImageData().GetSpacing())
		polyToStencil.SetOutputOrigin(inputVolume.GetImageData().GetOrigin())
		polyToStencil.SetOutputWholeExtent(inputVolume.GetImageData().GetExtent())
		
		# Apply the stencil to the volume
		stencilToImage=vtk.vtkImageStencil()
		stencilToImage.SetInputConnection(inputVolume.GetImageDataConnection())
		stencilToImage.SetStencilConnection(polyToStencil.GetOutputPort())
		if clipOutsideSurface:
			stencilToImage.ReverseStencilOff()
		else:
			stencilToImage.ReverseStencilOn()
		stencilToImage.SetBackgroundValue(fillValue)
		stencilToImage.Update()

		# Update the volume with the stencil operation result
		outputImageData = vtk.vtkImageData()
		outputImageData.DeepCopy(stencilToImage.GetOutput())
		
		outputVolume.SetAndObserveImageData(outputImageData);
		outputVolume.SetIJKToRASMatrix(ijkToRas)

		# Add a default display node to output volume node if it does not exist yet
		if not outputVolume.GetDisplayNode:
			displayNode=slicer.vtkMRMLScalarVolumeDisplayNode()
			displayNode.SetAndObserveColorNodeID("vtkMRMLColorTableNodeGrey")
			slicer.mrmlScene.AddNode(displayNode)
			outputVolume.SetAndObserveDisplayNodeID(displayNode.GetID())

		return True

	def updateModelFromMarkup(self, inputMarkup, outputModel):
		"""
		Update model to enclose all points in the input markup list
		"""
		
		# Delaunay triangulation is robust and creates nice smooth surfaces from a small number of points,
		# however it can only generate convex surfaces robustly.
		useDelaunay = True
		
		# Create polydata point set from markup points
		
		points = vtk.vtkPoints()
		cellArray = vtk.vtkCellArray()
		
		numberOfPoints = inputMarkup.GetNumberOfFiducials()
		
		# Surface generation algorithms behave unpredictably when there are not enough points
		# return if there are very few points
		if useDelaunay:
			if numberOfPoints<3:
				return
		else:
			if numberOfPoints<10:
				return

		points.SetNumberOfPoints(numberOfPoints)
		new_coord = [0.0, 0.0, 0.0]

		for i in range(numberOfPoints):
			inputMarkup.GetNthFiducialPosition(i,new_coord)
			points.SetPoint(i, new_coord)

		cellArray.InsertNextCell(numberOfPoints)
		for i in range(numberOfPoints):
			cellArray.InsertCellPoint(i)

		pointPolyData = vtk.vtkPolyData()
		pointPolyData.SetLines(cellArray)
		pointPolyData.SetPoints(points)

		
		# Create surface from point set

		if useDelaunay:
					
			delaunay = vtk.vtkDelaunay3D()
			delaunay.SetInputData(pointPolyData)

			surfaceFilter = vtk.vtkDataSetSurfaceFilter()
			surfaceFilter.SetInputConnection(delaunay.GetOutputPort())

			smoother = vtk.vtkButterflySubdivisionFilter()
			smoother.SetInputConnection(surfaceFilter.GetOutputPort())
			smoother.SetNumberOfSubdivisions(3)
			smoother.Update()

			outputModel.SetPolyDataConnection(smoother.GetOutputPort())
			
		else:
			
			surf = vtk.vtkSurfaceReconstructionFilter()
			surf.SetInputData(pointPolyData)
			surf.SetNeighborhoodSize(20)
			surf.SetSampleSpacing(80) # lower value follows the small details more closely but more dense pointset is needed as input

			cf = vtk.vtkContourFilter()
			cf.SetInputConnection(surf.GetOutputPort())
			cf.SetValue(0, 0.0)

			# Sometimes the contouring algorithm can create a volume whose gradient
			# vector and ordering of polygon (using the right hand rule) are
			# inconsistent. vtkReverseSense cures this problem.
			reverse = vtk.vtkReverseSense()
			reverse.SetInputConnection(cf.GetOutputPort())
			reverse.ReverseCellsOff()
			reverse.ReverseNormalsOff()

			outputModel.SetPolyDataConnection(reverse.GetOutputPort())

		# Create default model display node if does not exist yet
		if not outputModel.GetDisplayNode():
			modelDisplayNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLModelDisplayNode")
			modelDisplayNode.SetColor(0,0,1) # Blue
			modelDisplayNode.BackfaceCullingOff()
			modelDisplayNode.SliceIntersectionVisibilityOn()
			modelDisplayNode.SetOpacity(0.3) # Between 0-1, 1 being opaque
			slicer.mrmlScene.AddNode(modelDisplayNode)
			outputModel.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
	
		outputModel.GetDisplayNode().SliceIntersectionVisibilityOn()
			
		outputModel.Modified()

	def showInSliceViewers(self, volumeNode, sliceWidgetNames):
		# Displays volumeNode in the selected slice viewers as background volume
		# Existing background volume is pushed to foreground, existing foreground volume will not be shown anymore
		# sliceWidgetNames is a list of slice view names, such as ["Yellow", "Green"]
		if not volumeNode:
			return
		newVolumeNodeID = volumeNode.GetID()
		for sliceWidgetName in sliceWidgetNames:
			sliceLogic = slicer.app.layoutManager().sliceWidget(sliceWidgetName).sliceLogic()
			foregroundVolumeNodeID = sliceLogic.GetSliceCompositeNode().GetForegroundVolumeID()
			backgroundVolumeNodeID = sliceLogic.GetSliceCompositeNode().GetBackgroundVolumeID()
			if foregroundVolumeNodeID == newVolumeNodeID or backgroundVolumeNodeID == newVolumeNodeID:
				# new volume is already shown as foreground or background
				continue
			if backgroundVolumeNodeID:
				# there is a background volume, push it to the foreground because we will replace the background volume
				sliceLogic.GetSliceCompositeNode().SetForegroundVolumeID(backgroundVolumeNodeID)
			# show the new volume as background
			sliceLogic.GetSliceCompositeNode().SetBackgroundVolumeID(newVolumeNodeID)