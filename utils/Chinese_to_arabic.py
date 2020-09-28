# constants for chinese_to_arabic
# ========================================================
#   Copyright (C) 2018 All rights reserved.
#   
#   filename : Chinese_to_arabic.py
#   author   : wangkai
#   date     : 2019-03-02
#   desc     : 
# ======================================================== 
import re
import sys


CN_NUM = {
    '〇': 0, '一' : 1, '二' : 2, '三' : 3, '四' : 4, '五' : 5, '六' : 6, '七' : 7, '八' : 8, '九' : 9, 
    '零': 0, '壹' : 1, '贰' : 2, '叁' : 3, '肆' : 4, '伍' : 5, '陆' : 6, '柒' : 7, '捌' : 8, '玖' : 9,
    '两': 2, '幺' : 1, '么' : 1,
}

CN_UNIT = {
    '十' : 10,
    '拾' : 10,
    '百' : 100,
    '佰' : 100,
    '千' : 1000,
    '仟' : 1000,
    '万' : 10000,
    '萬' : 10000,
    '亿' : 100000000,
    '億' : 100000000,
    '兆' : 1000000000000,
}

SPLIT_UNIT = '零十拾百佰千仟万萬亿億兆'

SPLIT_NUM = '〇一二三四五六七八九零壹贰叁肆伍陆柒捌玖两幺'

EXCEPTION_UNIT = ['十万', '百万', '千万', '十亿', '百亿', '千亿', '十兆', '百兆', '千兆',
                  '十萬', '百萬', '千萬', '十億', '百億', '千億']

def standard_chinese_to_arabic(cn:str) -> int:
    unit = 0   # current
    ldig = []  # digest
    for cndig in reversed(cn):
        if cndig in CN_UNIT:
            unit = CN_UNIT.get(cndig)
            if unit == 10000 or unit == 100000000:
                ldig.append(unit)
                unit = 1
        else:
            dig = CN_NUM.get(cndig)
            if dig is None:
                return 0 
            if unit:
                dig *= unit
                unit = 0
            ldig.append(dig)
    if unit == 10:
        ldig.append(10)
    val, tmp = 0, 0
    for x in reversed(ldig):
        if x == 10000 or x == 100000000:
            val += tmp * x
            tmp = 0
        else:
            tmp += x
    val += tmp

    # 考虑诸如“一百二，三千四”的通俗说法
    if len(cn) > 1: # 当数字大于“十”的时候
        if cn[-1] in CN_NUM and cn[-2] in CN_UNIT:
            last, unit = CN_NUM.get(cn[-1]), CN_UNIT.get(cn[-2])
            val = val - last + last * (unit // 10)

    return val


def legalDesc(cn):
    cn_ldig = re.split(r'[{}]'.format(SPLIT_UNIT), cn)
    cn_ldig = list(filter(None, cn_ldig))
    for cndig in cn_ldig:
        dig = CN_NUM.get(cndig)
        if dig is None:
            return 0

    cn_lunit = re.split(r'[{}]'.format(SPLIT_NUM), cn)
    cn_lunit = list(filter(None, cn_lunit))
    for cndig in cn_lunit:
        dig = CN_UNIT.get(cndig)
        if dig is None and cndig not in EXCEPTION_UNIT:
                return 0
    return True

# 全数字情况
def unstandard_chinese_to_arabic(cn:str) -> int:
    cndig_list = list(cn)
    ldig = []
    for cndig in cndig_list:
        dig = CN_NUM.get(cndig)
        if dig is not None:
            ldig.append(str(dig))
        else:
            return 0
    return int(''.join(ldig))


def chinese_to_arabic(cn:str) -> int:
    # 首先进行非标准转换
    value = unstandard_chinese_to_arabic(cn)
    # 是否是全数字
    if value:
        return value
    else:
        if legalDesc(cn):
            return standard_chinese_to_arabic(cn)
        else:
            return 0

if __name__ == '__main__':
    print(chinese_to_arabic(str(sys.argv[1])))
