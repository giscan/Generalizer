from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from os.path import splitext, dirname

def saveDialog(parent):
    """Shows a save file dialog and return the selected file path."""
    settings = QSettings()
    key = '/UI/lastShapefileDir'
    outDir = settings.value(key)

    filter = 'GeoPackage (*.gpkg)'
    outFilePath, __ = QFileDialog.getSaveFileName(parent, parent.tr('Save output GeoPackage'), outDir, filter)
    outFilePath = str(outFilePath)

    if outFilePath:
        root, ext = splitext(outFilePath)
        if ext.upper() != '.GPKG':
            outFilePath = '%s.gpkg' % outFilePath
        outDir = dirname(outFilePath)
        settings.setValue(key, outDir)

    return outFilePath

def openDir(parent):
    settings = QSettings()
    key = '/UI/lastShapefileDir'
    outDir = settings.value(key)

    outPath = QFileDialog.getExistingDirectory(parent, 'Generalizer', outDir)
    return outPath
