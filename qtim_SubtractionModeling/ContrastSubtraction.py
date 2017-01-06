""" This file is picked up by 3D Slicer and used to create a widget. ContrastSubtraction
	(the class) specifies the Help and Acknowledgements qt box seen in Slicer.
	ContrastSubtractionWidget start the main action of the module, creating a workflow
	from ctk and creating initial links to Slicer's MRML data. Most of this
	module is modeled after ChangeTracker by Fedorov, which can be found in
	the following GitHub repository: https://github.com/fedorov/ChangeTrackerPy


	vtk is a libary associated with image processing, ctk a refined version of
	vtk meant specifically for medical imaging and used to here to create a
	step-by-step workflow, qt a popular user interface library, and slicer.
	The program 3D Slicer has access to these libraries (and more), and is
	referenced here as __main__. ContrastSubtractionWizard is a folder that 
	contains the individual steps of the workflow and does most of the computational
	work. 

	This module is meant to subtract pre- and post-contrast images, and then create
	a label volume highlighting the differences. It allows one to register images,
	normalize image intensities, and select a region of interest (ROI) along the way.

	All the best, Andrew Beers
"""

from __main__ import vtk, qt, ctk, slicer

import ContrastSubtractionWizard

# def batch():
# 	print 'Batched!'
# 	open('testcase.txt', 'a').close()

class ContrastSubtraction:

	def __init__( self, parent ):

		""" This class specifies the Help + Acknowledgements section. One assumes
			that Slicer looks for a class with the same name as the file name. 
			Modifications to the parent result in modifications to the qt box that 
			contains the relevant information.
		"""
		parent.title = """ContrastSubtraction"""
		parent.categories = ["""Examples"""]
		parent.contributors = ["""Andrew Beers"""]
		parent.helpText = """
		A multi-step wizard meant to subtract 3D pre- and post-contrast images, and then highlight their differences. Comes with registration, normalization, and ROI tools.
		""";
		parent.acknowledgementText = """Andrew Beers, Brown University. Special thanks to the TCIA for providing public testing contrast data.
		"""
		self.parent = parent
		self.collapsed = False

class ContrastSubtractionWidget:

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
			a workflow from ctk, which simply means that it creates a certies of UI
			steps one can traverse with "next" / "previous" buttons. The steps themselves
			are contained within ContrastSubtractionWizard.
		"""

		# Currently unclear on the difference between ctkWorkflow and
		# ctkWorkflowStackedWidget, but presumably the latter creates a UI
		# for the former
		self.workflow = ctk.ctkWorkflow()
		workflowWidget = ctk.ctkWorkflowStackedWidget()
		workflowWidget.setWorkflow( self.workflow )

		# Create workflow steps.
		self.Step1 = ContrastSubtractionWizard.VolumeSelectStep('VolumeSelectStep')
		self.Step2 = ContrastSubtractionWizard.RegistrationStep('RegistrationStep')
		self.Step3 = ContrastSubtractionWizard.NormalizeSubtractStep('NormalizeSubtractStep')
		self.Step4 = ContrastSubtractionWizard.ROIStep('ROIStep')
		self.Step5 = ContrastSubtractionWizard.ThresholdStep('ThresholdStep')
		self.Step6 = ContrastSubtractionWizard.ReviewStep('ReviewStep')

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

		# The following code creates a 'parameter node' from the vtkMRMLScriptedModuleNode class. 
		# A parameter node helps to keep track of module variables between steps. It also helps 
		# keep track of variables if someone leaves the module halfway through and then returns. 
		# Below, we check if a module already exists upon entry, and, if not, we create a new one.
		# The method of iterating through nNodes in a roundabout way is mysterious to me - but if 
		# it's not broke, don't fix it.
		nNodes = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLScriptedModuleNode')
		self.parameterNode = None
		for n in xrange(nNodes):
			compNode = slicer.mrmlScene.GetNthNodeByClass(n, 'vtkMRMLScriptedModuleNode')
			nodeid = None
			if compNode.GetModuleName() == 'ContrastSubtraction':
				self.parameterNode = compNode
				print 'Found existing ContrastSubtraction parameter node'
				break
		if self.parameterNode == None:
			self.parameterNode = slicer.vtkMRMLScriptedModuleNode()
			self.parameterNode.SetModuleName('ContrastSubtraction')
			slicer.mrmlScene.AddNode(self.parameterNode)

		# Individual steps need to remember the parameter node too.
		for s in allSteps:
				s.setParameterNode (self.parameterNode)

		# Restores you to the correct step if you leave and then return to the module.
		currentStep = self.parameterNode.GetParameter('currentStep')
		if currentStep != '':
			print 'Restoring ContrastSubctration workflow step to ', currentStep
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
		import ContrastSubtraction
		print "Contrast Subtraction Module Entered"