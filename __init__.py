"""
/***************************************************************************
 generalizer
                                 A QGIS plugin
"Lines generalization and smoothing (inpired from v.generalize GRASS module)"
                             -------------------
        begin                : 2011-08-17
        copyright            : (C) 2011 by Piotr Pociask
                               (C) 2019 - 2026 by Sylvain POULAIN
        email                : sylvain dot poulain (at) giscan dot com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


def classFactory(iface):
    """Load generalizer class from file generalizer.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .generalizer import generalizer
    return generalizer(iface)
