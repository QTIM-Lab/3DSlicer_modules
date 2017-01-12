""" This is Step 4. The user selects a ROI and subtracts the two images.
	Much of this step is copied from ChangeTracker, located at 
	https://github.com/fedorov/ChangeTrackerPy. Previously, I had been
	using the cubic ROI tool. This tool, although built in to Slicer,
	could cause painful slowdowns, and sometimes crashed. I also was
	having trouble applying transformations to the ROI. It also was
	not very intuitive. I now instead use the VolumeClip with Model module
	created by Andras Lasso. Its logic is copied wholesale into this code,
	which is unnessecary; it can be imported. However, I want to be able
	to do spot-edits while debugging. The VolumeClip module uses Delaunay
	Triangulation. This is very good at creating convex bubbles, but terrible
	at creating concave, complicated segmentations. Perhaps someone at project
	week will know an even better method.
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

		""" I got into the habit of creating a gratuitous amount of internal 
			variables in this step. Where possible, some of these should be
			pruned because they are hard to keep track of.
		"""

		self.initialize( stepid )
		self.setName( '4. Define Region(s) of Interest' )
		self.__logic = VolumeClipWithModelLogic()

		# Does declaring this one achieve anything? It doesn't happen in other steps.
		# It may even hurt things..
		self.__parameterNode = None

		self.__parameterNodeObserver = None

		self.__clippingModelNode = None
		self.__clippingMarkupNode = None
		self.__clippingMarkupNodeObserver = None
		
		# For future implementation of multiple models.
		self.__modelList = []
		self.__markupList = []
		self.__outputList = []

		# 3D Rendering Variables
		self.__vrDisplayNode = None
		self.__vrDisplayNodeID = ''
		self.__vrOpacityMap = None
		self.__threshRange = [ -1, -1 ]

		# These don't seem necessary; investigate.
		self.__roiTransformNode = None
		self.__baselineVolume = None
		self.__fillValue = 0

		# TODO: Remove portions about Cubic ROIs. This will not be in final program.
		self.__roi = None
		self.__roiObserverTag = None
		self.__CubicROI = False
		self.__ConvexROI = True

		self.__parent = super( ROIStep, self )

	def createUserInterface( self ):

		""" This UI currently is not easy to use. One has to know
			where the markups button is, know to mark it as persistent,
			and know how to move labels in 3D space. 
		"""

		self.__layout = self.__parent.createUserInterface()

		step_label = qt.QLabel( """Create either a convex ROI or a box ROI around the area you wish to threshold. Only voxels inside these ROIs will be thresholded in the next step. Click to add points to the convex ROI, or click and drag existing points to move them. A curved ROI will be filled in around these points. Similarly, click and drag the points on the box ROI to change its location and size.""")
		step_label.setWordWrap(True)
		self.__primaryGroupBox = qt.QGroupBox()
		self.__primaryGroupBox.setTitle('Information')
		self.__primaryGroupBoxLayout = qt.QFormLayout(self.__primaryGroupBox)
		self.__primaryGroupBoxLayout.addRow(step_label)
		self.__layout.addRow(self.__primaryGroupBox)


		# Toolbar with model buttons.
		self.__roiToolbarGroupBox = qt.QGroupBox()
		self.__roiToolbarGroupBox.setTitle('ROI Toolbar')
		self.__roiToolbarGroupBoxLayout = qt.QFormLayout(self.__roiToolbarGroupBox)

		self.__markupButton = qt.QToolButton()
		self.__markupButton.icon = qt.QIcon.addFile('TestIcon.png')
		self.__roiToolbarGroupBoxLayout.addRow('Toolbar Test Row', self.__markupButton)

		self.__layout.addRow(self.__roiToolbarGroupBox)

		# I'm referring to the Delaunay Triangulation as a "Convex ROI"
		# I don't think this is very clear; a better title would be good.
		self.__convexGroupBox = qt.QGroupBox()
		self.__convexGroupBox.setTitle('Convex ROI')
		self.__convexGroupBoxLayout = qt.QFormLayout(self.__convexGroupBox)

		""" There is an interesting entanglement between markups and models
			here which I believe is confusing to the user. Markups is a list
			of nodes, while the model is the 3D representation created from
			those nodes. It MIGHT be useful, or overly complicated, to have
			users be able to load previous models at this point. But then
			what would they be loading -- the model, or the markups? Which
			should they prefer? It's not clear where one saves models in
			Slicer, so that's a good reason to perhaps abandon it...
		"""
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

		# Below is a markups box that I would rather not have, because
		# it is confusing when matched with Models.

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

		""" Below is a gameplan for making loading previous models
			more obvious. Most Slice users understand loading nifti
			files or DICOMsegs, even if they don't understand vtk
			models. Converting labelmaps to models may be the way to
			go. Better yet, integrating with the Segmentations module,
			if users can easily understand that.
		"""

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

		""" How to describe the 3D Visualization threshold? I don't think
			most people will know what it means. It controls how transparent
			different intensities are in the visualization - it's bit hard
			to get an intuitive handle on it.
		"""

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

		# In case we wanted to set specific parameters for Volume Clip...

		# self.valueEditWidgets = {"ClipOutsideSurface": True, "FillValue": 0}
		# # self.nodeSelectorWidgets = {"InputVolume": self.inputVolumeSelector, "ClippingModel": self.clippingModelSelector, "ClippingMarkup": self.clippingMarkupSelector, "OutputVolume": self.outputVolumeSelector}

		# Intialize Volume Rendering...
		# Why here, if not init?
		self.__vrLogic = slicer.modules.volumerendering.logic()

		qt.QTimer.singleShot(0, self.killButton)

		# Likely more functions will need to be connected here.
		self.__clippingModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onClippingModelSelect)

	def onClippingModelSelect(self, node):

		if node != None and node != '':
			if node.GetID() not in self.__modelList:
				self.__modelList.append(node.GetID())
				new_clippingMarkupNode = slicer.vtkMRMLMarkupsFiducialNode()
				new_clippingMarkupNode.SetScene(slicer.mrmlScene)
				slicer.mrmlScene.AddNode(new_clippingMarkupNode)
				self.__markupList.append([node.GetID(), new_clippingMarkupNode.GetID(), 'Convex'])
			
			self.__clippingModelNode = node
			self.setAndObserveClippingMarkupNode(Helper.getNodeByID(self.__markupList[self.__modelList.index(node.GetID())][1]))

	def setAndObserveClippingMarkupNode(self, clippingMarkupNode):

		# Remove observer to old parameter node
		if self.__clippingMarkupNode and self.__clippingMarkupNodeObserver:
			self.__clippingMarkupNode.RemoveObserver(self.__clippingMarkupNodeObserver)
			self.__clippingMarkupNodeObserver = None

		# Set and observe new parameter node
		self.__clippingMarkupNode = clippingMarkupNode
		if self.__clippingMarkupNode:
			self.__clippingMarkupNodeObserver = self.__clippingMarkupNode.AddObserver(vtk.vtkCommand.ModifiedEvent, self.onClippingMarkupNodeModified)

		# Update GUI
		self.updateModelFromClippingMarkupNode()

	def onClippingMarkupNodeModified(self, observer, eventid):

		self.updateModelFromClippingMarkupNode()

	def updateModelFromClippingMarkupNode(self):

		if not self.__clippingMarkupNode or not self.__clippingModelSelector.currentNode():
			return
		self.__logic.updateModelFromMarkup(self.__clippingMarkupNode, self.__clippingModelSelector.currentNode())

	def onThresholdChanged(self): 
	
		# This is for controlling the 3D Visualization.

		if self.__vrOpacityMap == None:
			return
		
		range0 = self.__threshRange.minimumValue
		range1 = self.__threshRange.maximumValue

		# 75 is a pretty arbitrary number. Might fail for very wide ranges of intensities.
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

		if self.__modelList == []:
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

		self.updateWidgetFromParameters(pNode)

		# I believe this changes the layout to four-up; will check.
		lm = slicer.app.layoutManager()
		lm.setLayout(3)
		pNode = self.parameterNode()
		Helper.SetLabelVolume(None)

		# Why slices now? I think this is held over from previous program.
		slices = [lm.sliceWidget('Red'),lm.sliceWidget('Yellow'),lm.sliceWidget('Green')]
		for s in slices:
			s.sliceLogic().GetSliceNode().SetSliceVisible(0)

		""" vtk, the image analysis library, and Slicer use different coordinate
			systems: IJK and RAS, respectively. This prep calculates a simple matrix 
			transformation on a ROI transform node to be used in the next step.
		"""

		roiTransformID = pNode.GetParameter('roiTransformID')

		if roiTransformID != '':
			roiTransformNode = Helper.getNodeByID(roiTransformID)
		else:
			roiTransformNode = slicer.vtkMRMLLinearTransformNode()
			slicer.mrmlScene.AddNode(roiTransformNode)
			pNode.SetParameter('roiTransformID', roiTransformNode.GetID())

		self.__roiTransformID = roiTransformID

		# TODO: Understand the precise math behind this section of code..
		dm = vtk.vtkMatrix4x4()
		self.__visualizedVolume.GetIJKToRASDirectionMatrix(dm)
		dm.SetElement(0,3,0)
		dm.SetElement(1,3,0)
		dm.SetElement(2,3,0)
		dm.SetElement(0,0,abs(dm.GetElement(0,0)))
		dm.SetElement(1,1,abs(dm.GetElement(1,1)))
		dm.SetElement(2,2,abs(dm.GetElement(2,2)))
		roiTransformNode.SetAndObserveMatrixTransformToParent(dm)

		# Unsure about this step... might be a hold-over.
		if self.__roi != None:
			self.__roi.SetDisplayVisibility(1)

		pNode.SetParameter('currentStep', self.stepid)
		
		qt.QTimer.singleShot(0, self.killButton)

	def updateWidgetFromParameters(self, pNode):

		if pNode.GetParameter('followupVolumeID') == None or pNode.GetParameter('followupVolumeID') == '':
			Helper.SetBgFgVolumes(pNode.GetParameter('baselineVolumeID'), '')
			self.__visualizedVolume = Helper.getNodeByID(pNode.GetParameter('baselineVolumeID'))
		else:
			Helper.SetBgFgVolumes(pNode.GetParameter('subtractVolumeID'), pNode.GetParameter('followupVolumeID'))
			self.__visualizedVolume = Helper.getNodeByID(pNode.GetParameter('subtractVolumeID'))

		# These may seem redundant - maybe they are - but I think they are useful for
		# multiple program runs.
		if pNode.GetParameter('modelList') == '' or pNode.GetParameter('modelList') == None:
			self.__markupList = []
			self.__modelList = []
			self.__outputList = []

		# Gratuitous?
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
			else:
				self.InitVRDisplayNode()
				self.__vrDisplayNodeID = self.__vrDisplayNode.GetID()
		else:
			if self.__followupVolumeID == None or self.__followupVolumeID == '':
				Helper.InitVRDisplayNode(self.__vrDisplayNode, self.__baselineVolumeID, '')	
			else:
				Helper.InitVRDisplayNode(self.__vrDisplayNode, self.__followupVolumeID, '')	

	def InitVRDisplayNode(self):

		"""	This method calls a series of steps necessary to initailizing a volume 
			rendering node with an ROI.
		"""
		if self.__vrDisplayNode == None or self.__vrDisplayNode == '':
			pNode = self.parameterNode()
			self.__vrDisplayNode = self.__vrLogic.CreateVolumeRenderingDisplayNode()
			slicer.mrmlScene.AddNode(self.__vrDisplayNode)

			# Documentation on UnRegister is scant so far..
			self.__vrDisplayNode.UnRegister(self.__vrLogic) 

			Helper.InitVRDisplayNode(self.__vrDisplayNode, self.__visualizedVolume.GetID(), '')
			self.__visualizedVolume.AddAndObserveDisplayNodeID(self.__vrDisplayNode.GetID())

		# This is a bit messy. Is there a more specific way to get the view window?
		viewNode = slicer.util.getNode('vtkMRMLViewNode1')
		self.__vrDisplayNode.AddViewNodeID(viewNode.GetID())
		
		self.__vrLogic.CopyDisplayToVolumeRenderingDisplayNode(self.__vrDisplayNode)

		# Is this redundant with the portion below?
		self.__vrOpacityMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetScalarOpacity()
		self.__vrColorMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetRGBTransferFunction()

		# Renders in yellow, like the label map in the next steps.
		# Maybe ask radiologists what color they would prefer. I favor solid colors
		# to deal with images with non-normalized itensities.

		vrRange = self.__visualizedVolume.GetImageData().GetScalarRange()

		self.__vrColorMap.RemoveAllPoints()
		self.__vrColorMap.AddRGBPoint(vrRange[0], 0.8, 0.8, 0) 
		self.__vrColorMap.AddRGBPoint(vrRange[1], 0.8, 0.8, 0) 

		self.__threshRange.minimum = vrRange[0]
		self.__threshRange.maximum = vrRange[1]

		pNode = self.parameterNode()

		if pNode.GetParameter('vrThreshRangeMin') == '' or pNode.GetParameter('vrThreshRangeMin') == None:
			self.__threshRange.setValues(vrRange[1]/3, 2*vrRange[1]/3)
		else:
			self.__threshRange.setValues(int(pNode.GetParameter('vrThreshRangeMin')), int(pNode.GetParameter('vrThreshRangeMax')))

		self.__vrOpacityMap = self.__vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().GetScalarOpacity()

	def onExit(self, goingTo, transitionType):

		pNode = self.parameterNode()

		pNode.SetParameter('vrThreshRangeMin', str(self.__threshRange[0]))
		pNode.SetParameter('vrThresRangeMax', str(self.__threshRange[1]))

		if goingTo.id() == 'ThresholdStep':
			# Does a great deal of work to prepare for the segmentation step.
			self.ThresholdPrep()

			# lm = slicer.app.layoutManager()
			# slices = [lm.sliceWidget('Red'),lm.sliceWidget('Yellow'),lm.sliceWidget('Green')]
			# for s in slices:
			# 	s.sliceLogic().GetSliceNode().SetSliceVisible(0)

			pNode.SetParameter('clippingModelNodeID', self.__clippingModelSelector.currentNode().GetID())
			# pNode.SetParameter('clippingMarkupNodesID', self.__clippingMarkupSelector.currentNode().GetID())
			for ROI in self.__markupList:
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

		for ROI_idx, ROI in enumerate(self.__markupList):
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

				# Bit of an arbitrary value..
				self.__fillValue = inputVolume.GetImageData().GetScalarRange()[0] - 1

				self.__logic.clipVolumeWithModel(inputVolume, clippingModel, clipOutsideSurface, self.__fillValue, outputVolume)

				# I don't think OutputList is currently useful. The better tool would be to merge several models.
				self.__outputList.append(outputVolume.GetID())

				outputVolume.SetName(baselineVolume.GetName() + '_roi_image')

		pNode.SetParameter('outputList', '__'.join(self.__outputList))
		pNode.SetParameter('modelList', '__'.join(self.__modelList))

		""" Below is some junk code that I was thinking about to combined separate modles into one threshold ROI.
			Probably doesn't work. Better choice is to find a vtk function. 
		"""

		# volumesLogic = slicer.modules.volumes.logic()
		# combinedOutputVolume = volumesLogic.CloneVolume(slicer.mrmlScene, baselineVolume, baselineVolume.GetName() + '_roi')
		# volumesLogic.ClearVolumeImageData(combinedOutputVolume)
		# combinedOutputImageData = combinedOutputVolume.GetImageData()
		# shape = list(combinedOutputVolume.GetImageData().GetDimensions())
		# shape.reverse()
		# combinedOutputArray = vtk.util.numpy_support.vtk_to_numpy(combinedOutputImageData.GetPointData().GetScalars()).reshape(shape)

		# for output_idx, output in enumerate(self.__outputList):

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

		# Get starting threshold parameters.
		roiLabelID = pNode.GetParameter('croppedVolumeLabelID') 
		roiRange = outputVolume.GetImageData().GetScalarRange()
		thresholdParameter = str(0.5*(roiRange[0]+roiRange[1]))+','+str(roiRange[1])
		pNode.SetParameter('intensityThreshRangeMin', str(roiRange[0]))
		pNode.SetParameter('intensityThreshRangeMax', str(roiRange[1]))

		# Create a label node for segmentation. Should one make a new one each time? Who knows
		vl = slicer.modules.volumes.logic()

		if pNode.GetParameter('croppedVolumeLabelID') == '' or pNode.GetParameter('croppedVolumeLabelID') == None:
			roiSegmentation = vl.CreateLabelVolume(slicer.mrmlScene, outputVolume, baselineVolume.GetName() + '_roi_threshold')
		else:
			roiSegmentation = Helper.getNodeByID(pNode.GetParameter('croppedVolumeLabelID'))

		pNode.SetParameter('croppedVolumeLabelID', roiSegmentation.GetID())

		if pNode.GetParameter('modelLabelID') == '' or pNode.GetParameter('modelLabelID') == None:
			roiSegmentation = vl.CreateLabelVolume(slicer.mrmlScene, outputVolume, baselineVolume.GetName() + '_roi')
		else:
			roiSegmentation = Helper.getNodeByID(pNode.GetParameter('modelLabelID'))

		pNode.SetParameter('modelLabelID', roiSegmentation.GetID())

		self.__clippingMarkupNode.RemoveObserver(self.__clippingMarkupNodeObserver)
		self.__clippingMarkupNodeObserver = None

	""" The following are kept from ChangeTracker, might be useful later.
	"""

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