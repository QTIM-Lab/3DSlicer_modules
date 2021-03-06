""" This file is picked up by 3D Slicer and used to create a widget. ModelSegmentation
	(the class) specifies the Help and Acknowledgements qt box seen in Slicer.
	ModelSegmentationWidget start the main action of the module, creating a workflow
	from ctk and creating initial links to Slicer's MRML data. Most of this
	module is modeled after ChangeTracker by Andrey Fedorov, which can be found in
	the following GitHub repository: https://github.com/fedorov/ChangeTrackerPy

	vtk is a libary associated with image processing, ctk is a refined version of
	vtk meant specifically for medical imaging and is used here to create a
	step-by-step workflow, qt is a popular user interface library, and Slicer is a
	python library that helps developers hook into the 3D Slicer codebase.
	The program 3D Slicer has access to these libraries (and more), and is
	referenced here as __main__. ModelSegmentationWizard is a folder that 
	contains the individual steps of the workflow and does most of the computational
	work. 

	This module is meant to create easy and effecient segmentations on high slice
	resolution medical images. It can calculate subtraction maps, register images,
	normalize images, create automatic 3D ROIs using Delaunay Triangulation, and 
	threshold intensities within an ROI.

	This module was made by Andrew Beers as part of QTIM and QICCR [LINKS]
"""

from __main__ import vtk, qt, ctk, slicer

import ModelSegmentationWizard

class ModelSegmentation:

	def __init__( self, parent ):

		""" This class specifies the Help + Acknowledgements section. One assumes
			that Slicer looks for a class with the same name as the file name. 
			Modifications to the parent result in modifications to the qt box that 
			then prints the relevant information.
		"""
		parent.title = """Volumetric Segmentation"""
		parent.categories = ["""Segmentation"""]
		parent.contributors = ["""Andrew Beers"""]
		parent.helpText = """
		This module is meant to create easy and effecient segmentations on high slice
		resolution medical images. It can calculate subtraction maps, register images,
		normalize images, create 3D volumetric ROIs using Delaunay Triangulation, and finally
		threshold intensities within an ROI.
		""";
		parent.acknowledgementText = """Andrew Beers, QTIM [LINK] [OTHER ACKNOWLEDGEMENTS].
		"""
		self.parent = parent
		self.collapsed = False

class ModelSegmentationWidget:

	def __init__( self, parent=None ):
		""" It seems to be that Slicer creates an instance of this class with a
			qMRMLWidget parent. My understanding of parenthood when it comes to modules
			is currently limited -- I'll update this when I know more.
		"""

		if not parent:
				self.parent = slicer.qMRMLWidget()
				self.parent.setLayout( qt.QVBoxLayout() )
				self.parent.setMRMLScene( slicer.mrmlScene )
		else:
			self.parent = parent
			self.layout = self.parent.layout()

	def setup( self ):

		""" Slicer seems to call all methods of these classes upon entry. setup creates
			a workflow from ctk, which simply means that it creates a series of UI
			steps one can traverse with "next" / "previous" buttons. The steps themselves
			are contained within ModelSegmentationWizard.
		"""

		# Currently unclear on the difference between ctkWorkflow and
		# ctkWorkflowStackedWidget, but presumably the latter creates a UI
		# for the former.
		self.workflow = ctk.ctkWorkflow()
		workflowWidget = ctk.ctkWorkflowStackedWidget()
		workflowWidget.setWorkflow( self.workflow )

		# Create workflow steps.
		self.Step1 = ModelSegmentationWizard.VolumeSelectStep('VolumeSelectStep')
		self.Step2 = ModelSegmentationWizard.RegistrationStep('RegistrationStep')
		self.Step3 = ModelSegmentationWizard.NormalizeSubtractStep('NormalizeSubtractStep')
		self.Step4 = ModelSegmentationWizard.ROIStep('ROIStep')
		self.Step5 = ModelSegmentationWizard.ThresholdStep('ThresholdStep')
		self.Step6 = ModelSegmentationWizard.ReviewStep('ReviewStep')

		# Add the wizard steps to an array for convenience. Much of the following code
		# is copied wholesale from ChangeTracker.
		allSteps = []
		allSteps.append( self.Step1 )
		allSteps.append( self.Step2 )
		allSteps.append( self.Step3 )
		allSteps.append( self.Step4 )
		allSteps.append( self.Step5 )
		allSteps.append( self.Step6 )

		# Adds transition functionality between steps.
		self.workflow.addTransition(self.Step1, self.Step2)
		self.workflow.addTransition(self.Step2, self.Step3)
		self.workflow.addTransition(self.Step3, self.Step4)
		self.workflow.addTransition(self.Step4, self.Step5)
		self.workflow.addTransition(self.Step5, self.Step6)
		self.workflow.addTransition(self.Step6, self.Step1)

		""" The following code creates a 'parameter node' from the vtkMRMLScriptedModuleNode class. 
			A parameter node keeps track of module variables from step to step, in the case of
			ctkWorkflow, and when users leave the module to visit other modules. The code below
			searches to see if a parameter node already exists for ModelSegmentation among all
			available parameter nodes, and then creates one if it does not.
		"""
		nNodes = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLScriptedModuleNode')
		self.parameterNode = None
		for n in xrange(nNodes):
			compNode = slicer.mrmlScene.GetNthNodeByClass(n, 'vtkMRMLScriptedModuleNode')
			nodeid = None
			if compNode.GetModuleName() == 'ModelSegmentation':
				self.parameterNode = compNode
				print 'Found existing ModelSegmentation parameter node'
				break
		if self.parameterNode == None:
			self.parameterNode = slicer.vtkMRMLScriptedModuleNode()
			self.parameterNode.SetModuleName('ModelSegmentation')
			slicer.mrmlScene.AddNode(self.parameterNode)

		# Individual workflow steps need to remember the parameter node too.
		for s in allSteps:
			s.setParameterNode (self.parameterNode)

		# Restores you to the correct step if you leave and then return to the module.
		currentStep = self.parameterNode.GetParameter('currentStep')
		if currentStep != '':
			print 'Restoring ModelSegmentation workflow step to ', currentStep
			if currentStep == 'VolumeSelectStep':
				self.workflow.setInitialStep(self.Step1)
			if currentStep == 'RegistrationStep':
				self.workflow.setInitialStep(self.Step2)
			if currentStep == 'NormalizeSubtractStep':
				self.workflow.setInitialStep(self.Step3)
			if currentStep == 'ROIStep':
				self.workflow.setInitialStep(self.Step4)
			if currentStep == 'ThresholdStep':
				self.workflow.setInitialStep(self.Step4)
			if currentStep == 'ReviewStep':
				self.workflow.setInitialStep(self.Step4)
		else:
			print 'currentStep in parameter node is empty!'

		# Starts and show the workflow.
		self.workflow.start()
		workflowWidget.visible = True
		self.layout.addWidget( workflowWidget )

	def enter(self):
		""" A quick check to see if the file was loaded. Can be seen in the Python Interactor.
		"""
		import ModelSegmentation
		print "Model Segmentation Module Correctly Entered"