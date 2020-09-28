# ========================================================
#   Copyright (C) 2018 All rights reserved.
#   
#   filename : exrsp.py
#   author   : wangkai
#   updater  : jiangjiacheng, dajiangyu
#   date     : 2019-10-03
#   desc     : 
# ======================================================== 


import sys


# ----------------------------------------------------------------------------------------------------------------------
# 语音相关
# ----------------------------------------------------------------------------------------------------------------------
def Errback(message):
    resSets = {'msg': message,
               'code': 1501
               }

    return resSets


def BackTypeA(high, low):
    resSets = {'code': 0,
               'data': {'id': 1,
                        'pressure': {'high': high,
                                     'low': low
                                     }
                        }
               }
    return resSets


def BackTypeB(value):
    resSets = {'code': 0,
               'data': {'id': 2,
                        'heartRate': value
                        }
               }
    return resSets


def BackTypeC(value):
    resSets = {'code': 0,
               'data': {'id': 3,
                        'weight': value
                        }
               }
    return resSets


def BackTypeD(medicines):
    resSets = {'code': 0,
               'data': {'id': 4,
                        'medicines': medicines
                        }
               }
    return resSets


def BackTypeE(status):
    resSets = {'code': 0,
               'data': {'id': 5,
                        'status': status
                        }
               }
    return resSets


# add by jiangjiacheng
def AudioErr():
    resSets = {'msg': 'Please say it again!',
               'code': 1502
               }

    return resSets


# add by jiangjiacheng
def AudioServerErr():
    resSets = {'msg': 'Please input by hand!',
               'code': 1503
               }

    return resSets


def UnknownAudioError(ip, src, data, msg):
    resSets = {
        'msg': 'Missing information, Permission denied!',
        'code': 1599
    }
    return resSets


