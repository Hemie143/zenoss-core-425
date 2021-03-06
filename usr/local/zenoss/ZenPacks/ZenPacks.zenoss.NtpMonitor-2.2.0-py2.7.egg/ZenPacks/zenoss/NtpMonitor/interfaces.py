##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2010, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


from Products.Zuul.interfaces import IRRDDataSourceInfo
from Products.Zuul.form import schema
from Products.Zuul.utils import ZuulMessageFactory as _t


class INtpMonitorDataSourceInfo(IRRDDataSourceInfo):
    timeout = schema.Int(title=_t(u'Timeout (seconds)'))
    cycletime = schema.Int(title=_t(u'Cycle Time (seconds)'))
    hostname = schema.TextLine(title=_t(u'Host Name'),
                               group=_t(u'Ntp'))
    warning = schema.Int(title=_t(u'Warning Response Time (seconds)'),
                           group=_t(u'Ntp'))
    critical = schema.Int(title=_t(u'Critical Response Time (seconds)'),
                           group=_t(u'Ntp'))
