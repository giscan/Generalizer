from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingUtils,
    QgsFeatureSink,
    QgsWkbTypes,
    QgsGeometry,
    QgsFeature,
    QgsPointXY,
    QgsPoint,
    QgsProcessingException,
    Qgis,
)
from qgis.PyQt.QtGui import QIcon
import os

from . import smooth, simplify, points as pts_module


def _icon():
    return QIcon(os.path.join(os.path.dirname(__file__), 'icon.png'))


def _layer_to_line_pnts(geom_part):
    """Converts a list of QgsPointXY (QGIS 4) or tuples into line_pnts."""
    return pts_module.Vect_new_line_struct(geom_part)


def _process_layer(source, sink, feedback, process_func, **kwargs):
    """A common loop over all features, applying process_func to each one."""
    features = list(source.getFeatures())
    total = len(features)
    for i, feat in enumerate(features):
        if feedback.isCanceled():
            break
        feedback.setProgress(int(i / total * 100))

        geom = feat.geometry()
        out_feat = QgsFeature(feat)

        if geom is None or geom.isEmpty():
            sink.addFeature(out_feat, QgsFeatureSink.Flag.FastInsert)
            continue

        if geom.isMultipart():
            parts = geom.asMultiPolyline()
            new_parts = []
            for part in parts:
                p = process_func(part, **kwargs)
                coords = [QgsPointXY(p.x[n], p.y[n]) for n in range(p.n_points)]
                if len(coords) > 1:
                    new_parts.append(coords)
            if len(new_parts) > 1:
                out_feat.setGeometry(QgsGeometry.fromMultiPolylineXY(new_parts))
            elif len(new_parts) == 1:
                out_feat.setGeometry(QgsGeometry.fromPolylineXY(new_parts[0]))
            else:
                continue
        else:
            part = geom.asPolyline()
            p = process_func(part, **kwargs)
            coords = [QgsPointXY(p.x[n], p.y[n]) for n in range(p.n_points)]
            if len(coords) < 2:
                continue
            out_feat.setGeometry(QgsGeometry.fromPolylineXY(coords))

        sink.addFeature(out_feat, QgsFeatureSink.Flag.FastInsert)


def _run_remove(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    p1 = pts_module.point(); p2 = pts_module.point()
    length = 0.
    for i in range(p.n_points - 1):
        pts_module.point_assign(p, i, p1)
        pts_module.point_assign(p, i + 1, p2)
        length += pts_module.point_dist(p1, p2)
    if length < kw['threshold']:
        p.x = []; p.y = []; p.n_points = 0
    return p

def _run_dp(part, **kw):
    l_tuples = [(pt.x(), pt.y()) if hasattr(pt, 'x') else (pt[0], pt[1]) for pt in part]
    tmp = simplify.douglas_peucker(l_tuples, kw['threshold'])
    return pts_module.Vect_new_line_struct(tmp)

def _run_jenks(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    simplify.jenks(p, kw['threshold'], kw['angle_threshold'])
    return p

def _run_lang(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    simplify.lang(p, kw['threshold'], kw['look_ahead'])
    return p

def _run_rw(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    simplify.reumann_witkam(p, kw['threshold'])
    return p

def _run_reduction(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    simplify.vertex_reduction(p, kw['threshold'])
    return p

def _run_boyle(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    smooth.boyle(p, kw['look_ahead'])
    return p

def _run_chaiken(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    smooth.chaiken(p, kw['level'], kw['weight'])
    return p

def _run_hermite(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    smooth.hermite(p, kw['threshold'], kw['tightness'])
    return p

def _run_distance(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    smooth.distance_weighting(p, kw['slide'], kw['look_ahead'])
    return p

def _run_sliding(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    smooth.sliding_averaging(p, kw['slide'], kw['look_ahead'])
    return p

def _run_snakes(part, **kw):
    p = pts_module.Vect_new_line_struct(part)
    smooth.snakes(p, kw['alpha'], kw['beta'])
    return p


class _BaseGeneralizerAlgorithm(QgsProcessingAlgorithm):
    INPUT  = 'INPUT'
    OUTPUT = 'OUTPUT'

    def icon(self):
        return _icon()

    def group(self):
        return self.groupName()

    def groupId(self):
        return self.group().lower().replace(' ', '_').replace("'", '')

    def groupName(self):
        raise NotImplementedError

    def createInstance(self):
        return self.__class__()

    def _add_io_params(self):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, 'Input line layer',
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Output layer'))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            source.fields(), source.wkbType(), source.sourceCrs())
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        kwargs = self._get_kwargs(parameters, context)
        _process_layer(source, sink, feedback, self._run_func, **kwargs)
        return {self.OUTPUT: dest_id}

    def _get_kwargs(self, parameters, context):
        raise NotImplementedError

    def _run_func(self, part, **kw):
        raise NotImplementedError


class RemoveSmallObjectsAlgorithm(_BaseGeneralizerAlgorithm):
    THRESHOLD = 'THRESHOLD'

    def name(self):         return 'remove_small_objects'
    def displayName(self):  return 'Remove small objects'
    def groupName(self):    return 'Generalize'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, 'Threshold', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0001, defaultValue=1.0))

    def _get_kwargs(self, p, c):
        return {'threshold': self.parameterAsDouble(p, self.THRESHOLD, c)}

    def _run_func(self, part, **kw): return _run_remove(part, **kw)

    def shortHelpString(self):
        return 'Removes line features shorter than the threshold distance.'


class DouglasPeuckerAlgorithm(_BaseGeneralizerAlgorithm):
    THRESHOLD = 'THRESHOLD'

    def name(self):         return 'douglas_peucker'
    def displayName(self):  return 'Douglas-Peucker'
    def groupName(self):    return 'Simplify'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, 'Threshold', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0001, defaultValue=1.0))

    def _get_kwargs(self, p, c):
        return {'threshold': self.parameterAsDouble(p, self.THRESHOLD, c)}

    def _run_func(self, part, **kw): return _run_dp(part, **kw)

    def shortHelpString(self):
        return 'Simplifies lines using the Douglas-Peucker algorithm. Higher threshold = more simplification.'


class JenksAlgorithm(_BaseGeneralizerAlgorithm):
    THRESHOLD       = 'THRESHOLD'
    ANGLE_THRESHOLD = 'ANGLE_THRESHOLD'

    def name(self):         return 'jenks'
    def displayName(self):  return "Jenks' algorithm"
    def groupName(self):    return 'Simplify'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, 'Threshold', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0, defaultValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.ANGLE_THRESHOLD, 'Angle threshold (degrees)',
            type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0, maxValue=180.0, defaultValue=3.0))

    def _get_kwargs(self, p, c):
        return {
            'threshold':       self.parameterAsDouble(p, self.THRESHOLD, c),
            'angle_threshold': self.parameterAsDouble(p, self.ANGLE_THRESHOLD, c),
        }

    def _run_func(self, part, **kw): return _run_jenks(part, **kw)

    def shortHelpString(self):
        return "Simplifies lines using Jenks' algorithm."


class LangAlgorithm(_BaseGeneralizerAlgorithm):
    THRESHOLD  = 'THRESHOLD'
    LOOK_AHEAD = 'LOOK_AHEAD'

    def name(self):         return 'lang'
    def displayName(self):  return 'Lang algorithm'
    def groupName(self):    return 'Simplify'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, 'Threshold', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0001, defaultValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.LOOK_AHEAD, 'Look ahead', type=QgsProcessingParameterNumber.Type.Integer,
            minValue=1, defaultValue=8))

    def _get_kwargs(self, p, c):
        return {
            'threshold':  self.parameterAsDouble(p, self.THRESHOLD, c),
            'look_ahead': self.parameterAsInt(p, self.LOOK_AHEAD, c),
        }

    def _run_func(self, part, **kw): return _run_lang(part, **kw)

    def shortHelpString(self):
        return 'Simplifies lines using the Lang algorithm.'


class ReumannWitkamAlgorithm(_BaseGeneralizerAlgorithm):
    THRESHOLD = 'THRESHOLD'

    def name(self):         return 'reumann_witkam'
    def displayName(self):  return 'Reumann-Witkam algorithm'
    def groupName(self):    return 'Simplify'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, 'Threshold', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0001, defaultValue=1.0))

    def _get_kwargs(self, p, c):
        return {'threshold': self.parameterAsDouble(p, self.THRESHOLD, c)}

    def _run_func(self, part, **kw): return _run_rw(part, **kw)

    def shortHelpString(self):
        return 'Simplifies lines using the Reumann-Witkam algorithm.'


class VertexReductionAlgorithm(_BaseGeneralizerAlgorithm):
    THRESHOLD = 'THRESHOLD'

    def name(self):         return 'vertex_reduction'
    def displayName(self):  return 'Vertex reduction'
    def groupName(self):    return 'Simplify'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, 'Threshold', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0001, defaultValue=1.0))

    def _get_kwargs(self, p, c):
        return {'threshold': self.parameterAsDouble(p, self.THRESHOLD, c)}

    def _run_func(self, part, **kw): return _run_reduction(part, **kw)

    def shortHelpString(self):
        return 'Removes vertices closer than the threshold distance.'


class BoyleAlgorithm(_BaseGeneralizerAlgorithm):
    LOOK_AHEAD = 'LOOK_AHEAD'

    def name(self):         return 'boyle'
    def displayName(self):  return "Boyle's forward-looking algorithm"
    def groupName(self):    return 'Smooth'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.LOOK_AHEAD, 'Look ahead', type=QgsProcessingParameterNumber.Type.Integer,
            minValue=2, defaultValue=7))

    def _get_kwargs(self, p, c):
        return {'look_ahead': self.parameterAsInt(p, self.LOOK_AHEAD, c)}

    def _run_func(self, part, **kw): return _run_boyle(part, **kw)

    def shortHelpString(self):
        return "Smooths lines using Boyle's forward-looking algorithm."


class ChaikenAlgorithm(_BaseGeneralizerAlgorithm):
    LEVEL  = 'LEVEL'
    WEIGHT = 'WEIGHT'

    def name(self):         return 'chaiken'
    def displayName(self):  return "Chaiken's algorithm"
    def groupName(self):    return 'Smooth'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.LEVEL, 'Level', type=QgsProcessingParameterNumber.Type.Integer,
            minValue=1, defaultValue=1))
        self.addParameter(QgsProcessingParameterNumber(
            self.WEIGHT, 'Weight', type=QgsProcessingParameterNumber.Type.Double,
            minValue=1.0, defaultValue=3.0))

    def _get_kwargs(self, p, c):
        return {
            'level':  self.parameterAsInt(p, self.LEVEL, c),
            'weight': self.parameterAsDouble(p, self.WEIGHT, c),
        }

    def _run_func(self, part, **kw): return _run_chaiken(part, **kw)

    def shortHelpString(self):
        return "Smooths lines using Chaiken's algorithm (corner cutting)."


class HermiteAlgorithm(_BaseGeneralizerAlgorithm):
    THRESHOLD = 'THRESHOLD'
    TIGHTNESS = 'TIGHTNESS'

    def name(self):         return 'hermite'
    def displayName(self):  return 'Hermite spline interpolation'
    def groupName(self):    return 'Smooth'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, 'Threshold', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0001, defaultValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.TIGHTNESS, 'Tightness', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0, maxValue=1.0, defaultValue=0.5))

    def _get_kwargs(self, p, c):
        return {
            'threshold': self.parameterAsDouble(p, self.THRESHOLD, c),
            'tightness': self.parameterAsDouble(p, self.TIGHTNESS, c),
        }

    def _run_func(self, part, **kw): return _run_hermite(part, **kw)

    def shortHelpString(self):
        return 'Smooths lines using Hermite spline interpolation.'


class DistanceWeightingAlgorithm(_BaseGeneralizerAlgorithm):
    SLIDE      = 'SLIDE'
    LOOK_AHEAD = 'LOOK_AHEAD'

    def name(self):         return 'distance_weighting'
    def displayName(self):  return "McMaster's distance-weighting algorithm"
    def groupName(self):    return 'Smooth'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.SLIDE, 'Slide', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0, maxValue=1.0, defaultValue=0.5))
        self.addParameter(QgsProcessingParameterNumber(
            self.LOOK_AHEAD, 'Look ahead (odd number)', type=QgsProcessingParameterNumber.Type.Integer,
            minValue=3, defaultValue=7))

    def _get_kwargs(self, p, c):
        la = self.parameterAsInt(p, self.LOOK_AHEAD, c)
        if la % 2 == 0:
            la += 1  # forcer impair silencieusement
        return {'slide': self.parameterAsDouble(p, self.SLIDE, c), 'look_ahead': la}

    def _run_func(self, part, **kw): return _run_distance(part, **kw)

    def shortHelpString(self):
        return "Smooths lines using McMaster's distance-weighting algorithm. Look ahead must be odd."


class SlidingAveragingAlgorithm(_BaseGeneralizerAlgorithm):
    SLIDE      = 'SLIDE'
    LOOK_AHEAD = 'LOOK_AHEAD'

    def name(self):         return 'sliding_averaging'
    def displayName(self):  return "McMaster's sliding averaging algorithm"
    def groupName(self):    return 'Smooth'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.SLIDE, 'Slide', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0, maxValue=1.0, defaultValue=0.5))
        self.addParameter(QgsProcessingParameterNumber(
            self.LOOK_AHEAD, 'Look ahead (odd number)', type=QgsProcessingParameterNumber.Type.Integer,
            minValue=3, defaultValue=7))

    def _get_kwargs(self, p, c):
        la = self.parameterAsInt(p, self.LOOK_AHEAD, c)
        if la % 2 == 0:
            la += 1
        return {'slide': self.parameterAsDouble(p, self.SLIDE, c), 'look_ahead': la}

    def _run_func(self, part, **kw): return _run_sliding(part, **kw)

    def shortHelpString(self):
        return "Smooths lines using McMaster's sliding averaging algorithm. Look ahead must be odd."


class SnakesAlgorithm(_BaseGeneralizerAlgorithm):
    ALPHA = 'ALPHA'
    BETA  = 'BETA'

    def name(self):         return 'snakes'
    def displayName(self):  return 'Snakes algorithm'
    def groupName(self):    return 'Smooth'

    def initAlgorithm(self, config=None):
        self._add_io_params()
        self.addParameter(QgsProcessingParameterNumber(
            self.ALPHA, 'Alpha', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0, defaultValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.BETA, 'Beta', type=QgsProcessingParameterNumber.Type.Double,
            minValue=0.0, defaultValue=0.5))

    def _get_kwargs(self, p, c):
        return {
            'alpha': self.parameterAsDouble(p, self.ALPHA, c),
            'beta':  self.parameterAsDouble(p, self.BETA, c),
        }

    def _run_func(self, part, **kw): return _run_snakes(part, **kw)

    def shortHelpString(self):
        return 'Smooths lines using the Snakes algorithm (slowest but highest quality).'
