"""
Supporting functions for polydata and grid objects

"""
import logging
import ctypes
import imageio

import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtkIdTypeArray
from vtk.util.numpy_support import numpy_to_vtk

import os

import vtki


POINT_DATA_FIELD = 0
CELL_DATA_FIELD = 1


def vtk_bit_array_to_char(vtkarr_bint):
    """ Cast vtk bit array to a char array """
    vtkarr = vtk.vtkCharArray()
    vtkarr.DeepCopy(vtkarr_bint)
    return vtkarr


def is_vtki_obj(obj):
    return isinstance(obj, (vtki.Common, vtki.MultiBlock))


def point_scalar(mesh, name):
    """ Returns point scalars of a vtk object """
    vtkarr = mesh.GetPointData().GetArray(name)
    if vtkarr:
        if isinstance(vtkarr, vtk.vtkBitArray):
            vtkarr = vtk_bit_array_to_char(vtkarr)
        return vtk_to_numpy(vtkarr)


def cell_scalar(mesh, name):
    """ Returns cell scalars of a vtk object """
    vtkarr = mesh.GetCellData().GetArray(name)
    if vtkarr:
        if isinstance(vtkarr, vtk.vtkBitArray):
            vtkarr = vtk_bit_array_to_char(vtkarr)
        return vtk_to_numpy(vtkarr)


def get_scalar(mesh, name, preference='cell', info=False):
    """ Searches both point and cell data for an array """
    parr = point_scalar(mesh, name)
    carr = cell_scalar(mesh, name)
    if isinstance(preference, str):
        if preference in ['cell', 'c', 'cells']:
            preference = CELL_DATA_FIELD
        elif preference in ['point', 'p', 'points']:
            preference = POINT_DATA_FIELD
        else:
            raise RuntimeError('Data field ({}) not supported.'.format(preference))
    if all([parr is not None, carr is not None]):
        if preference == CELL_DATA_FIELD:
            if info:
                return carr, CELL_DATA_FIELD
            else:
                return carr
        elif preference == POINT_DATA_FIELD:
            if info:
                return parr, POINT_DATA_FIELD
            else:
                return parr
        else:
            raise RuntimeError('Data field ({}) not supported.'.format(preference))
    arr = None
    field = None
    if parr is not None:
        arr = parr
        field = 0
    if carr is not None:
        arr = carr
        field = 1
    if info:
        return arr, field
    return arr


def vtk_points(points, deep=True):
    """ Convert numpy points to a vtkPoints object """
    if not points.flags['C_CONTIGUOUS']:
        points = np.ascontiguousarray(points)
    vtkpts = vtk.vtkPoints()
    vtkpts.SetData(numpy_to_vtk(points, deep=deep))
    return vtkpts


def lines_from_points(points):
    """
    Generates line from points.  Assumes points are ordered as line segments.

    Parameters
    ----------
    points : np.ndarray
        Points representing line segments.  For example, two line segments
        would be represented as:

        np.array([[0, 0, 0], [1, 0, 0], [1, 0, 0], [1, 1, 0]])

    Returns
    -------
    lines : vtki.PolyData
        PolyData with lines and cells.

    Examples
    --------
    This example plots two line segments at right angles to each other line.

    >>> import vtki
    >>> import numpy as np
    >>> points = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 0], [1, 1, 0]])
    >>> lines = vtki.lines_from_points(points)
    >>> lines.plot() # doctest:+SKIP

    """
    # Assuming ordered points, create array defining line order
    npoints = points.shape[0] - 1
    lines = np.vstack((2 * np.ones(npoints, np.int),
                       np.arange(npoints),
                       np.arange(1, npoints + 1))).T.ravel()

    return vtki.PolyData(points, lines)


def vector_poly_data(orig, vec):
    """ Creates a vtkPolyData object composed of vectors """

    # shape, dimention checking
    if not isinstance(orig, np.ndarray):
        orig = np.asarray(orig)

    if not isinstance(vec, np.ndarray):
        vec = np.asarray(vec)

    if orig.ndim != 2:
        orig = orig.reshape((-1, 3))
    elif orig.shape[1] != 3:
        raise Exception('orig array must be 3D')

    if vec.ndim != 2:
        vec = vec.reshape((-1, 3))
    elif vec.shape[1] != 3:
        raise Exception('vec array must be 3D')

    # Create vtk points and cells objects
    vpts = vtk.vtkPoints()
    vpts.SetData(numpy_to_vtk(np.ascontiguousarray(orig), deep=True))

    npts = orig.shape[0]
    cells = np.hstack((np.ones((npts, 1), 'int'),
                       np.arange(npts).reshape((-1, 1))))

    if cells.dtype != ctypes.c_int64 or cells.flags.c_contiguous:
        cells = np.ascontiguousarray(cells, ctypes.c_int64)
    cells = np.reshape(cells, (2*npts))
    vcells = vtk.vtkCellArray()
    vcells.SetCells(npts, numpy_to_vtkIdTypeArray(cells, deep=True))

    # Create vtkPolyData object
    pdata = vtk.vtkPolyData()
    pdata.SetPoints(vpts)
    pdata.SetVerts(vcells)

    # Add vectors to polydata
    name = 'vectors'
    vtkfloat = numpy_to_vtk(np.ascontiguousarray(vec), deep=True)
    vtkfloat.SetName(name)
    pdata.GetPointData().AddArray(vtkfloat)
    pdata.GetPointData().SetActiveVectors(name)

    # Add magnitude of vectors to polydata
    name = 'mag'
    scalars = (vec * vec).sum(1)**0.5
    vtkfloat = numpy_to_vtk(np.ascontiguousarray(scalars), deep=True)
    vtkfloat.SetName(name)
    pdata.GetPointData().AddArray(vtkfloat)
    pdata.GetPointData().SetActiveScalars(name)

    return vtki.PolyData(pdata)


def trans_from_matrix(matrix):
    """ Convert a vtk matrix to a numpy.ndarray """
    t = np.zeros((4, 4))
    for i in range(4):
        for j in range(4):
            t[i, j] = matrix.GetElement(i, j)
    return t


def wrap(vtkdataset):
    """This is a convenience method to safely wrap any given VTK data object
    to its appropriate ``vtki`` data object.
    """
    wrappers = {
        'vtkUnstructuredGrid' : vtki.UnstructuredGrid,
        'vtkRectilinearGrid' : vtki.RectilinearGrid,
        'vtkStructuredGrid' : vtki.StructuredGrid,
        'vtkPolyData' : vtki.PolyData,
        'vtkImageData' : vtki.UniformGrid,
        'vtkStructuredPoints' : vtki.UniformGrid,
        'vtkMultiBlockDataSet' : vtki.MultiBlock,
        }
    key = vtkdataset.GetClassName()
    try:
        wrapped = wrappers[key](vtkdataset)
    except:
        logging.warning('VTK data type ({}) is not currently supported by vtki.'.format(key))
        return vtkdataset # if not supported just passes the VTK data object
    return wrapped

def read(filename):
    """This will read any VTK file! It will figure out what reader to use
    then wrap the VTK object for use in ``vtki``
    """
    filename = os.path.abspath(os.path.expanduser(filename))
    def legacy(filename):
        reader = vtk.vtkDataSetReader()
        reader.SetFileName(filename)
        reader.Update()
        return reader.GetOutputDataObject(0)
    ext = os.path.splitext(filename)[1].lower()
    if ext in '.vtk':
        # Use a legacy reader and wrap the result
        return wrap(legacy(filename))
    else:
        # From the extension, decide which reader to use
        if ext in '.vti': # ImageData
            return vtki.UniformGrid(filename)
        elif ext in '.vtr': # RectilinearGrid
            return vtki.RectilinearGrid(filename)
        elif ext in '.vtu': # UnstructuredGrid
            return vtki.UnstructuredGrid(filename)
        elif ext in ['.ply', '.obj', '.stl']: # PolyData
            return vtki.PolyData(filename)
        elif ext in '.vts': # UnstructuredGrid
            return vtki.StructuredGrid(filename)
        elif ext in ['.vtm', '.vtmb']:
            return vtki.MultiBlock(filename)
        else:
            # Attempt to use the legacy reader...
            try:
                return wrap(legacy(filename))
            except:
                pass
    raise IOError("This file was not able to be automatically read by vtki.")


def set_error_output_file(filename):
    """Sets a file to write out the VTK errors"""
    filename = os.path.abspath(os.path.expanduser(filename))
    fileOutputWindow = vtk.vtkFileOutputWindow()
    fileOutputWindow.SetFileName(filename)
    outputWindow = vtk.vtkOutputWindow()
    outputWindow.SetInstance(fileOutputWindow)
    return fileOutputWindow, outputWindow


def load_texture(filename):
    """Loads a ``vtkTexture`` from an image file."""
    filename = os.path.abspath(os.path.expanduser(filename))
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.jpg', '.jpeg']:
        reader = vtk.vtkJPEGReader()
    elif ext in ['.tif', '.tiff']:
        reader = vtk.vtkTIFFReader()
    elif ext in ['.png']:
        reader = vtk.vtkPNGReader()
    else:
        # Otherwise, use the imageio reader
        return numpy_to_texture(imagio.imread(filename))
    reader.SetFileName(filename)
    reader.Update()
    texture = vtk.vtkTexture()
    texture.SetInputDataObject(reader.GetOutputDataObject(0))
    texture.Update()
    return texture


def numpy_to_texture(image):
    """Convert a NumPy image array to a vtk.vtkTexture"""
    if not isinstance(image, np.ndarray):
        raise TypeError('Unknown input type ({})'.format(type(image)))
    if image.ndim != 3 or image.shape[2] != 3:
        raise AssertionError('Input image must be nn by nm by RGB')
    grid = vtki.UniformGrid((image.shape[1], image.shape[0], 1))
    grid.point_arrays['Image'] = np.flip(image.swapaxes(0,1), axis=1).reshape((-1, 3), order='F')
    grid.set_active_scalar('Image')
    vtex = vtk.vtkTexture()
    vtex.SetInputDataObject(grid)
    vtex.Update()
    return vtex


def is_inside_bounds(point, bounds):
    """ Checks if a point is inside a set of bounds """
    if not (bounds[0] < point[0] < bounds[1]):
        return False
    if not (bounds[2] < point[1] < bounds[3]):
        return False
    if not (bounds[4] < point[2] < bounds[5]):
        return False
    return True
