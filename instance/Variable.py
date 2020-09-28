# ========================================================
#   Copyright (C) 2018 All rights reserved.
#   
#   filename : Variable
#   author   : wangkai
#   date     : 2019-07-15
#   desc     : 
# ======================================================== 


##   --------------------   项目配置

# 端口
PORT = 8088


#    --------------------   字典
# 医学字典
DICT_MED = './dict/hf_dict_utf8.txt'
# 改错拼音字典
DICT_PY = './dict/pinyin_list.txt'
# 切词字典
DICT_SEG = './dict/userdict.txt'
# Rule
DIR_RULE = './dict/rule'
# 改错预处理替换规则
DICT_PRE_RULE = './dict/dict_pre_rule.txt'
# 改错附加自定义字典
DICT_CUSTOM = './dict/dict_custom.txt'
# 改错过滤规则
DICT_FILTER_RULE = './dict/dict_filter_rule.txt'
# 记录改错字典
DICT_STAT = './dict/dict_stat.txt'

# -------------------------------
# 语音相关
# 1.阈值
LOWEST_HIGH_PRESSURE = 60
HIGHEST_HIGH_PRESSURE = 240
LOWEST_LOW_PRESSURE = 40
HIGHEST_LOW_PRESSURE = 140

LOWEST_HEARTRATE = 20
HIGHEST_HEARTRATE = 220

LOWEST_WEIGHT = 20
HIGHEST_WEIGHT = 250

MAXIMUM_RECORD = 10

# 2.话术
MSG_BLOOD_HIGH_NO = '高压值未听清，请重新输入'
MSG_BLOOD_LOW_NO = '低压值未听清，请重新输入'
MSG_BLOOD_HIGHHIGH = '高压值{}过高，请及时就医'
MSG_BLOOD_HIGHLOW = '高压值{}过低，请及时就医'
MSG_BLOOD_LOWHIGH = '低压值{}过高，请及时就医'
MSG_BLOOD_LOWLOW = '低压值{}过低，请及时就医'
MSG_BLOOD_NOTHIGHERTHAN = '高压值{}小于等于低压值{}，请重新录入'

MSG_HEARTRATE_NO = '心率值未听清，请重新录入'
MSG_HEARTRATE_HIGH = '心率值{}过高，请重新录入'
MSG_HEARTRATE_LOW = '心率值{}过低，请重新录入'

MSG_WEIGHT_NO = '体重值未听清，请重新录入'
MSG_WEIGHT_HIGH = '体重值{}过高，请重新录入'
MSG_WEIGHT_LOW = '体重值{}过低，请重新录入'

MSG_MEDICINE_NO = '药名未听清，请重新录入'

MSG_NO = '没有听清楚，请再说一次'
MSG_NONE = '未检测到语音输入'
MSG_DIFF = '请正确回答问题'
MSG_WEIRD = '请正确表达意思'
# ---------------------------------
