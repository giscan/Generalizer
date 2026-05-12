"""
/***************************************************************************
 generalizerDialog — QGIS 4
Lines generalization and smoothing (inpired from v.generalize GRASS module)
        begin                : 2011-08-17
        copyright            : (C) 2011 by Piotr Pociask
        adapted to QGIS 3 & 4: 2019 - 2026 by Sylvain POULAIN
        email                : sylvain dot poulain (at) giscan dotcom
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QDialog, QMessageBox, QInputDialog,
                                  QDoubleSpinBox, QSpinBox, QTableWidgetItem)
from qgis.core import QgsProject, QgsMapLayer, QgsMessageLog, Qgis

import processing

from .dialogs import saveDialog, openDir
from .ui_generalizer import Ui_generalizer

try:
    UNCHECKED = Qt.CheckState.Unchecked
    CHECKED   = Qt.CheckState.Checked
except AttributeError:
    UNCHECKED = Qt.Unchecked
    CHECKED   = Qt.Checked

ALGO_ID = {
    'Remove small objects':                    'generalizer3:remove_small_objects',
    'Douglas-Peucker Algorithm':               'generalizer3:douglas_peucker',
    "Jenk's Algorithm":                        'generalizer3:jenks',
    'Lang Algorithm':                          'generalizer3:lang',
    'Reumann-Witkam Algorithm':                'generalizer3:reumann_witkam',
    'Vertex Reduction':                        'generalizer3:vertex_reduction',
    "Boyle's Forward-Looking Algorithm":       'generalizer3:boyle',
    "Chaiken's Algorithm":                     'generalizer3:chaiken',
    'Hermite Spline Interpolation':            'generalizer3:hermite',
    "McMaster's Distance-Weighting Algorithm": 'generalizer3:distance_weighting',
    "McMaster's Sliding Averaging Algorithm":  'generalizer3:sliding_averaging',
    'Snakes Algorithm':                        'generalizer3:snakes',
}

def _params_from_ui(alg_name, ui):
    """Builds the Processing parameters from the dialog's widgets."""
    mapping = {
        'Remove small objects':                    lambda: {'THRESHOLD': ui.sbRemove_thresh.value()},
        'Douglas-Peucker Algorithm':               lambda: {'THRESHOLD': ui.sbDP_thresh.value()},
        "Jenk's Algorithm":                        lambda: {'THRESHOLD': ui.sbJenks_thresh.value(),
                                                            'ANGLE_THRESHOLD': ui.sbJenks_angle.value()},
        'Lang Algorithm':                          lambda: {'THRESHOLD': ui.sbLang_thresh.value(),
                                                            'LOOK_AHEAD': ui.sbLang_LA.value()},
        'Reumann-Witkam Algorithm':                lambda: {'THRESHOLD': ui.sbRW_thresh.value()},
        'Vertex Reduction':                        lambda: {'THRESHOLD': ui.sbReduction_thresh.value()},
        "Boyle's Forward-Looking Algorithm":       lambda: {'LOOK_AHEAD': ui.sbBoyle_LA.value()},
        "Chaiken's Algorithm":                     lambda: {'LEVEL': ui.sbChaiken_level.value(),
                                                            'WEIGHT': ui.sbChaiken_weight.value()},
        'Hermite Spline Interpolation':            lambda: {'THRESHOLD': ui.sbHermite_steps.value(),
                                                            'TIGHTNESS': ui.sbHermite_tightness.value()},
        "McMaster's Distance-Weighting Algorithm": lambda: {'SLIDE': ui.sbDist_slide.value(),
                                                            'LOOK_AHEAD': ui.sbDist_LA.value()},
        "McMaster's Sliding Averaging Algorithm":  lambda: {'SLIDE': ui.sbSlide_slide.value(),
                                                            'LOOK_AHEAD': ui.sbSlide_LA.value()},
        'Snakes Algorithm':                        lambda: {'ALPHA': ui.sbSnakes_alpha.value(),
                                                            'BETA': ui.sbSnakes_beta.value()},
    }
    return mapping[alg_name]()


def _params_from_table(alg_name, par1, par2):
    """Constructs the Processing parameters from the values in the batch array."""
    mapping = {
        'Remove small objects':                    lambda: {'THRESHOLD': par1},
        'Douglas-Peucker Algorithm':               lambda: {'THRESHOLD': par1},
        "Jenk's Algorithm":                        lambda: {'THRESHOLD': par1, 'ANGLE_THRESHOLD': par2 if par2 != -1 else 3.0},
        'Lang Algorithm':                          lambda: {'THRESHOLD': par1, 'LOOK_AHEAD': int(par2)},
        'Reumann-Witkam Algorithm':                lambda: {'THRESHOLD': par1},
        'Vertex Reduction':                        lambda: {'THRESHOLD': par1},
        "Boyle's Forward-Looking Algorithm":       lambda: {'LOOK_AHEAD': int(par1)},
        "Chaiken's Algorithm":                     lambda: {'LEVEL': int(par1), 'WEIGHT': par2},
        'Hermite Spline Interpolation':            lambda: {'THRESHOLD': par1, 'TIGHTNESS': par2},
        "McMaster's Distance-Weighting Algorithm": lambda: {'SLIDE': par1, 'LOOK_AHEAD': int(par2)},
        "McMaster's Sliding Averaging Algorithm":  lambda: {'SLIDE': par1, 'LOOK_AHEAD': int(par2)},
        'Snakes Algorithm':                        lambda: {'ALPHA': par1, 'BETA': par2},
    }
    return mapping[alg_name]()


class generalizerDialog(QDialog):

    def __init__(self, iface):
        QDialog.__init__(self)
        self.ui = Ui_generalizer()
        self.ui.setupUi(self)
        self.iface = iface

        self.ui.sbJenks_angle.setVisible(False)
        self.ui.label_8.setVisible(False)

        self.ui.bBrowse.clicked.connect(self.outFile)
        self.ui.bBrowseDir.clicked.connect(self.outDir)
        self.ui.bOk.clicked.connect(self.generalize)
        self.ui.cbAlgorithm.currentIndexChanged.connect(self.cbChange)
        self.ui.bHelp.clicked.connect(self.showHelp)
        self.ui.cbBatch.stateChanged.connect(self.BatchOn)
        self.ui.bAddAlg.clicked.connect(self.AddAlgorithm)
        self.ui.bDelAlg.clicked.connect(self.DelAlgorithm)
        self.ui.bEditAlg.clicked.connect(self.EditAlgorithm)
        self.ui.cbOutFile.stateChanged.connect(self.FileEnabled)
        self.ui.cbOutDir.stateChanged.connect(self.DirEnabled)

        self.cbChange(self.ui.cbAlgorithm.currentIndex())

        self.layerList = getLayersNames()
        self.ui.cbInput.addItems(self.layerList)
        self.ui.lstLayers.addItems(self.layerList)
        [self.ui.lstLayers.item(i).setCheckState(UNCHECKED) for i in range(self.ui.lstLayers.count())]


    def FileEnabled(self, state):
        enabled = self.ui.eOutput.isEnabled()
        self.ui.eOutput.setEnabled(not enabled)
        self.ui.bBrowse.setEnabled(not enabled)

    def DirEnabled(self, state):
        enabled = self.ui.eDir.isEnabled()
        self.ui.eDir.setEnabled(not enabled)
        self.ui.bBrowseDir.setEnabled(not enabled)

    def BatchOn(self, state):
        self.ui.stackBatch.setCurrentIndex(0 if state == 0 else 1)

    def showHelp(self):
        QMessageBox.information(self, 'Generalizer', (
            'Generalizer v2.0\n\n'
            'Adapted to QGIS 4 by Sylvain POULAIN\n'
            'Originally writtent by Piotr Pociask\n\n'
            'Docs: https://github.com/giscan/Generalizer/wiki'
        ))

    def outFile(self):
        path = saveDialog(self)
        if path:
            self.ui.eOutput.setText(path)

    def outDir(self):
        path = openDir(self)
        if path:
            self.ui.eDir.setText(path)

    def cbChange(self, index):
        combo_to_stack = {
            1: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5,
            9: 6, 10: 7, 11: 8, 12: 9, 13: 10, 14: 11,
        }
        if index in {0, 2, 8}:
            self.ui.cbAlgorithm.setCurrentIndex(index + 1)
            return
        if index in combo_to_stack:
            self.ui.stackOptions.setCurrentIndex(combo_to_stack[index])

    def AddAlgorithm(self):
        self.doAddAlgorithm(self.ui.tblBatchAlg.rowCount())

    def EditAlgorithm(self):
        if self.ui.tblBatchAlg.currentRow() == -1:
            QMessageBox.warning(self, 'Generalizer', 'Select algorithm to edit!')
            return
        self.doAddAlgorithm(self.ui.tblBatchAlg.currentRow())

    def doAddAlgorithm(self, index):
        items = [self.ui.cbAlgorithm.itemText(i) for i in range(self.ui.cbAlgorithm.count())]
        choice = QInputDialog.getItem(None, 'Generalizer', 'Choose algorithm:', items, 1, False)
        if not choice[1] or choice[0].startswith('-'):
            return
        name = choice[0]
        par1 = par2 = None

        if name in ('Remove small objects', 'Douglas-Peucker Algorithm',
                    'Reumann-Witkam Algorithm', 'Vertex Reduction'):
            v = QInputDialog.getDouble(None, 'Generalizer', 'Threshold:', 1.0, 0.0001, 9999999.0, 4)
            if not v[1]: return
            par1 = QDoubleSpinBox(); par1.setDecimals(4); par1.setRange(0.0001, 9999999.0)
            par1.setValue(v[0]); par1.setToolTip('Threshold')

        elif name == "Boyle's Forward-Looking Algorithm":
            v = QInputDialog.getInt(None, 'Generalizer', 'Look ahead:', 7, 2, 999)
            if not v[1]: return
            par1 = QSpinBox(); par1.setRange(2, 999); par1.setValue(v[0]); par1.setToolTip('Look ahead')

        elif name == "Chaiken's Algorithm":
            v = QInputDialog.getInt(None, 'Generalizer', 'Level:', 1, 1, 99)
            if not v[1]: return
            par1 = QSpinBox(); par1.setRange(1, 99); par1.setValue(v[0]); par1.setToolTip('Level')
            v2 = QInputDialog.getDouble(None, 'Generalizer', 'Weight:', 3.0, 1.0, 99.99, 2)
            if not v2[1]: return
            par2 = QDoubleSpinBox(); par2.setRange(1.0, 99.99); par2.setValue(v2[0]); par2.setToolTip('Weight')

        elif name == 'Hermite Spline Interpolation':
            v = QInputDialog.getDouble(None, 'Generalizer', 'Threshold:', 1.0, 0.0001, 9999999.0, 4)
            if not v[1]: return
            par1 = QDoubleSpinBox(); par1.setDecimals(4); par1.setRange(0.0001, 9999999.0)
            par1.setValue(v[0]); par1.setToolTip('Threshold')
            v2 = QInputDialog.getDouble(None, 'Generalizer', 'Tightness:', 0.5, 0.0, 1.0, 2)
            if not v2[1]: return
            par2 = QDoubleSpinBox(); par2.setRange(0.0, 1.0); par2.setValue(v2[0]); par2.setToolTip('Tightness')

        elif name == 'Lang Algorithm':
            v = QInputDialog.getDouble(None, 'Generalizer', 'Threshold:', 1.0, 0.0001, 9999999.0, 4)
            if not v[1]: return
            par1 = QDoubleSpinBox(); par1.setDecimals(4); par1.setRange(0.0001, 9999999.0)
            par1.setValue(v[0]); par1.setToolTip('Threshold')
            v2 = QInputDialog.getInt(None, 'Generalizer', 'Look ahead:', 8, 1, 9999)
            if not v2[1]: return
            par2 = QSpinBox(); par2.setRange(1, 9999); par2.setValue(v2[0]); par2.setToolTip('Look ahead')

        elif name in ("McMaster's Distance-Weighting Algorithm",
                      "McMaster's Sliding Averaging Algorithm"):
            v = QInputDialog.getDouble(None, 'Generalizer', 'Slide:', 0.5, 0.0, 99.99, 2)
            if not v[1]: return
            par1 = QDoubleSpinBox(); par1.setRange(0.0, 99.99); par1.setValue(v[0]); par1.setToolTip('Slide')
            la = 6
            while la % 2 == 0:
                v2 = QInputDialog.getInt(None, 'Generalizer', 'Look ahead (odd):', la + 1, 3, 999)
                if not v2[1]: return
                la = v2[0]
            par2 = QSpinBox(); par2.setRange(3, 999); par2.setSingleStep(2)
            par2.setValue(la); par2.setToolTip('Look ahead')

        elif name == 'Snakes Algorithm':
            v = QInputDialog.getDouble(None, 'Generalizer', 'Alpha:', 1.0, 0.0, 9999.99, 2)
            if not v[1]: return
            par1 = QDoubleSpinBox(); par1.setRange(0.0, 9999.99); par1.setValue(v[0]); par1.setToolTip('Alpha')
            v2 = QInputDialog.getDouble(None, 'Generalizer', 'Beta:', 0.5, 0.0, 9999.99, 2)
            if not v2[1]: return
            par2 = QDoubleSpinBox(); par2.setRange(0.0, 9999.99); par2.setValue(v2[0]); par2.setToolTip('Beta')

        elif name == "Jenk's Algorithm":
            v = QInputDialog.getDouble(None, 'Generalizer', 'Threshold:', 1.0, 0.0, 9999999.0, 4)
            if not v[1]: return
            par1 = QDoubleSpinBox(); par1.setDecimals(4); par1.setRange(0.0, 9999999.0)
            par1.setValue(v[0]); par1.setToolTip('Threshold')

        new = index > self.ui.tblBatchAlg.rowCount() - 1
        if new:
            self.ui.tblBatchAlg.setRowCount(self.ui.tblBatchAlg.rowCount() + 1)

        item = QTableWidgetItem(name)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.ui.tblBatchAlg.setItem(index, 0, item)
        self.ui.tblBatchAlg.setCellWidget(index, 1, par1)
        if par2 is None:
            self.ui.tblBatchAlg.setCellWidget(index, 2, None)
            empty = QTableWidgetItem('')
            empty.setFlags(Qt.ItemFlag.ItemIsSelectable)
            self.ui.tblBatchAlg.setItem(index, 2, empty)
        else:
            self.ui.tblBatchAlg.setCellWidget(index, 2, par2)

    def DelAlgorithm(self):
        if self.ui.tblBatchAlg.currentRow() == -1:
            QMessageBox.warning(self, 'Generalizer', 'Select algorithm to delete!')
            return
        alg = self.ui.tblBatchAlg.item(self.ui.tblBatchAlg.currentRow(), 0).text()
        msg = QMessageBox.question(self, 'Generalizer', f'Delete {alg}?',
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg == QMessageBox.StandardButton.Yes:
            self.ui.tblBatchAlg.removeRow(self.ui.tblBatchAlg.currentRow())

    def _run(self, alg_name, layer, params, output='TEMPORARY_OUTPUT'):
        """Calls processing.run() and returns the result layer or None."""
        proc_id = ALGO_ID.get(alg_name)
        if proc_id is None:
            QMessageBox.critical(None, 'Generalizer', f'Unknown algorithm: {alg_name}')
            return None
        try:
            result = processing.run(proc_id, {'INPUT': layer, 'OUTPUT': output, **params})
            return result['OUTPUT']
        except Exception as e:
            QgsMessageLog.logMessage(str(e), 'Generalizer3', level=Qgis.Critical)
            QMessageBox.critical(None, 'Generalizer', f'Error in {alg_name}:\n{e}')
            return None

    def generalize(self):
        if self.ui.cbBatch.isChecked():
            if self.ui.cbOutDir.isChecked() and self.ui.eDir.text() == '':
                QMessageBox.critical(None, 'Generalizer', 'Enter output directory!')
                return

            layers = [
                self.ui.lstLayers.item(i).text()
                for i in range(self.ui.lstLayers.count())
                if self.ui.lstLayers.item(i).checkState() == CHECKED
            ]
            if not layers:
                QMessageBox.warning(None, 'Generalizer', 'Select at least one layer!')
                return

            outNames = []
            for layer_name in layers:
                layer = getMapLayerByName(layer_name)
                if layer is None:
                    continue

                current = layer
                n_algs = self.ui.tblBatchAlg.rowCount()
                for i in range(n_algs):
                    alg_name = self.ui.tblBatchAlg.item(i, 0).text()
                    w1 = self.ui.tblBatchAlg.cellWidget(i, 1)
                    w2 = self.ui.tblBatchAlg.cellWidget(i, 2)
                    par1 = w1.value() if w1 else 1.0
                    par2 = w2.value() if w2 else -1
                    params = _params_from_table(alg_name, par1, par2)

                    is_last = (i == n_algs - 1)
                    if self.ui.cbOutDir.isChecked() and is_last:
                        sep = '\\' if '\\' in self.ui.eDir.text() else '/'
                        out_path = f"{self.ui.eDir.text()}{sep}{layer_name}_new.gpkg"
                        outNames.append(out_path)
                        output = out_path
                    else:
                        output = 'TEMPORARY_OUTPUT'

                    current = self._run(alg_name, current, params, output)
                    if current is None:
                        break
                else:
                    if not self.ui.cbOutDir.isChecked():
                        QgsProject.instance().addMapLayer(current)

            if self.ui.cbOutDir.isChecked() and outNames:
                self._loadLayers(outNames)

        else:
            if not self.ui.cbInput.currentText():
                QMessageBox.critical(None, 'Generalizer', 'No line layers!')
                return

            alg_name = self.ui.cbAlgorithm.currentText()
            layer    = getMapLayerByName(self.ui.cbInput.currentText())
            params   = _params_from_ui(alg_name, self.ui)

            if self.ui.cbOutFile.isChecked():
                if not self.ui.eOutput.text():
                    QMessageBox.critical(None, 'Generalizer', 'Enter output file name!')
                    return
                result = self._run(alg_name, layer, params, self.ui.eOutput.text())
                if result:
                    self._loadLayers([self.ui.eOutput.text()])
            else:
                result = self._run(alg_name, layer, params)
                if result:
                    QgsProject.instance().addMapLayer(result)

        self.layerList = getLayersNames()
        self.ui.cbInput.clear()
        self.ui.lstLayers.clear()
        self.ui.cbInput.addItems(self.layerList)
        self.ui.lstLayers.addItems(self.layerList)
        [self.ui.lstLayers.item(i).setCheckState(UNCHECKED) for i in range(self.ui.lstLayers.count())]

    def _loadLayers(self, fileList):
        msg = QMessageBox.question(self, 'Generalizer', 'New layer(s) created.\nAdd to TOC?',
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.Yes)
        if msg == QMessageBox.StandardButton.Yes:
            for filePath in fileList:
                sep = '\\' if '\\' in filePath else '/'
                out_name = filePath.split(sep)[-1].removesuffix('.gpkg')
                self.iface.addVectorLayer(filePath, out_name, 'ogr')


def getLayersNames():
    layermap = QgsProject.instance().mapLayers()
    result = []
    for layer in layermap.values():
        if layer.type() == QgsMapLayer.LayerType.VectorLayer:
            try:
                is_line = layer.geometryType() == Qgis.GeometryType.Line
            except AttributeError:
                from qgis.core import QgsWkbTypes
                is_line = layer.geometryType() == QgsWkbTypes.LineGeometry
            if is_line:
                result.append(str(layer.name()))
    return result


def getMapLayerByName(name):
    for layer in QgsProject.instance().mapLayers().values():
        if layer.name() == name and layer.isValid():
            return layer
    return None
