from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon
import os

from .generalizer_algorithms import (
    RemoveSmallObjectsAlgorithm,
    DouglasPeuckerAlgorithm,
    JenksAlgorithm,
    LangAlgorithm,
    ReumannWitkamAlgorithm,
    VertexReductionAlgorithm,
    BoyleAlgorithm,
    ChaikenAlgorithm,
    HermiteAlgorithm,
    DistanceWeightingAlgorithm,
    SlidingAveragingAlgorithm,
    SnakesAlgorithm,
)


class GeneralizerProvider(QgsProcessingProvider):

    def __init__(self):
        super().__init__()

    def id(self):
        return 'generalizer3'

    def name(self):
        return 'Generalizer'

    def longName(self):
        return 'Generalizer - line simplification and smoothing'

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        return QIcon(icon_path)

    def loadAlgorithms(self):
        for alg in [
            RemoveSmallObjectsAlgorithm(),
            DouglasPeuckerAlgorithm(),
            JenksAlgorithm(),
            LangAlgorithm(),
            ReumannWitkamAlgorithm(),
            VertexReductionAlgorithm(),
            BoyleAlgorithm(),
            ChaikenAlgorithm(),
            HermiteAlgorithm(),
            DistanceWeightingAlgorithm(),
            SlidingAveragingAlgorithm(),
            SnakesAlgorithm(),
        ]:
            self.addAlgorithm(alg)
