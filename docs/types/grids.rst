Gridded Data
============


Gridded datasets in vtki capture ``vtkRectilinearGrid`` and ``vtkImageData``
data objects on the VTK backend. These data types have common features which
are encompassed int their shared inheritance of :class:`vtki.Grid`



.. autoclass:: vtki.Grid
   :show-inheritance:
   :members:
   :undoc-members:


Rectilinear Grid
----------------

.. autoclass:: vtki.RectilinearGrid
   :show-inheritance:
   :members:
   :undoc-members:



Uniform Grid
------------

`vtki`'s definition of a uniform grid is an extension of VTK's ``vtkImageData``

.. autoclass:: vtki.UniformGrid
   :show-inheritance:
   :members:
   :undoc-members:
