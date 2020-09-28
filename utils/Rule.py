# ========================================================
#   Copyright (C) 2018 All rights reserved.
#   
#   filename : Rule.py 
#   author   : wangkai
#   date     : 2019-05-21
#   desc     : 
# ======================================================== 

from utils.Chinese_to_arabic import *
from utils.Exrsp import *
import pkuseg
import os
from utils.Logger import logger
import re

from instance.Variable import *


class Rule:
    """
    Rule类
    类变量：药名字典、切词字典、关键词->问题映射字典、单位名称列表、否定词&消极词名称列表以及同义词映射字典
    类函数：切词函数
    """

    def __init__(self):
        self.init_load()

        # 加载药名字典
        self.drugName = self.LoadDrugName(DICT_MED)
        # 加载切词字典
        self.seg = self.InitPkuseg(DICT_SEG)

    def init_load(self):
        # 加载“关键词->问题”映射词典        
        self.status = self.load_dict_file(DIR_RULE, 'ques')
        # 加载“单位”名称列表     
        self.weight, self.unit, self.parts = self.load_list_file(DIR_RULE, 'unit')
        # 加载“否定词&消极词&坏词”名称列表
        self.no, self.negative, self.bad = self.load_list_file(DIR_RULE, 'no&neg')
        # 加载“同义词”映射词典
        self.mapping = self.load_dict_file(DIR_RULE, 'synonym')

    # 加载字典数据文件
    def load_dict_file(self, path, name):
        filename = os.path.join(path, name + '_dict.txt')
        with open(filename, mode='r', encoding='utf-8') as dict_f:
            res = {}
            for line in dict_f:
                s = line.strip().split('\t')
                res.setdefault(s[0], s[1])
        return res

    # 加载列表数据文件
    def load_list_file(self, path, name):
        filename = os.path.join(path, name + '_dict.txt')
        with open(filename, mode='r', encoding='utf-8') as dict_f:
            res = []
            # 初始化列表标签flag和列表内容tmp
            flag, tmp = '0', []
            for line in dict_f:
                s = line.strip().split('\t')
                if flag != s[1]:
                    res.append(tmp)
                    flag, tmp = s[1], []
                tmp.append(s[0])
            # 添加最后一组列表内容
            res.append(tmp)
        return res

    def InitPkuseg(self, filename):
        seg = pkuseg.pkuseg(model_name='medicine', user_dict=filename)
        return seg

    def LoadDrugName(self, filename, DrugName=set()):
        fd = open(filename, 'r')
        for line in fd:
            line = line.strip()
            item = line.split("\t")
            if item[1] == "药物":
                DrugName.add(item[0])
        fd.close()
        return DrugName

    def WordSeg(self, info):
        text = self.seg.cut(info)
        return text

    # 解析名字
    def _CalcName(self, wordseg, index, num, DrugList):
        key, ix, maxlen = "NULL", index - 1, len(wordseg) - 1
        if ix >= 0:
            key = wordseg[ix]
        if key not in self.drugName or key in DrugList:
            ix = index + num + 1
            if ix <= maxlen and wordseg[ix] in self.drugName:
                key = wordseg[ix]
        return key

    # 解析带数量的文字（高压一百二、六十次、五十千克、一片药等）
    def _CalcNumber(self, wordseg, index, DrugList=[], flag=False, radius=2):
        key, value = "NULL", 0
        for num in radius * [1]:
            if flag:
                index = index - num
                if index < 0:
                    return [key, value]
                key = self._CalcName(wordseg, index, num, DrugList)
            else:
                index = index + num
                if index >= len(wordseg):
                    return [key, value]
            try:
                # 不允许输入负数
                if wordseg[index] in ['负', '附', '副']:
                    value = 0
                    break

                # 跳过分钟数
                elif index < len(wordseg) - 1:
                    if wordseg[index + 1] in ['分钟']:
                        value = 0
                        continue

                value = int(wordseg[index])
            except:
                value = chinese_to_arabic(wordseg[index])
                # if index + 1 < len(wordseg):
                #     tmp = chinese_to_arabic(''.join(wordseg[index: index + 2]))
                #     value = tmp if tmp > value else value

                # if index + 2 < len(wordseg):
                #     tmp = chinese_to_arabic(''.join(wordseg[index: index + 3]))
                #     value = tmp if tmp > value else value

            # print(value, type(value))

            if value != 0:
                if '斤' in wordseg[index + 1:] :
                    value = round(value / 2)
                elif '磅' in wordseg[index + 1:]:
                    value = round(value / 2.2)
                break
        # print(wordseg[index], key, value)
        return [key, value]

    # 提取回答关键词
    def _ModifyType(self, wordseg, TypeNum, Index):
        # 今天血压是多少？
        if TypeNum == '1':
            if len(wordseg) > 0:
                if wordseg[Index] == '毫米汞柱':
                    index = -1

            # 如果是没有匹配关键词，或者关键词是单位
            if Index == -1:
                high, low = 0, 0
                for ind in range(Index, len(wordseg)):
                    # 高压值还未获取
                    if high == 0:
                        [_, high] = self._CalcNumber(wordseg, ind, radius=1)
                    elif low == 0:
                        [_, low] = self._CalcNumber(wordseg, ind, radius=1)

                # 如果高低压相反
                if high < low:
                    high, low = low, high

                # 处理数字相连的情况
                if high < LOWEST_HIGH_PRESSURE or high > HIGHEST_HIGH_PRESSURE or low < LOWEST_LOW_PRESSURE or low > HIGHEST_LOW_PRESSURE:
                    sen = ''.join(wordseg)
                    start, end = -1, len(sen)
                    for ind, ele in enumerate(sen):
                        if ele in SPLIT_UNIT or ele in SPLIT_NUM or 47 < ord(ele) < 58:
                            if start == -1:
                                start = ind
                        else:
                            if start != -1:
                                end = ind
                                break

                    # print(start, end)
                    confusedNum = sen[start: end]

                    # 按顺序遍历分割混淆数字
                    candidates = []
                    for i in range(len(confusedNum)):
                        numFirst, numLast = 0, 0
                        front, back = confusedNum[:i], confusedNum[i:]
                        # print(front, back)
                        # 第一位不为百或0，不存在“十X十”样式，不存在“十x百”样式，不存在“一十”开头样式，不存在两个“数字汉字”相连形式
                        char = '(一|二|三|四|五|六|七|八|九)'
                        if back[0] not in ['百', '0'] and not re.search(r'十(.*)十', back) and not re.search(r'十(.*)百', front) and not re.search(r'十(.*)百', back) and not re.search(r'\b一十', back) and not re.search(char + char, back):
                            if len(front) >= 1:
                                try:
                                    numFirst = int(front)
                                except:
                                    numFirst = chinese_to_arabic(front)

                            if len(back) >= 1:
                                try:
                                    numLast = int(back)
                                except:
                                    numLast = chinese_to_arabic(back)
                            
                            # print('{}\t{}'.format(numFirst, numLast))

                            candidates.append((max(numFirst, numLast), min(numFirst, numLast)))
                    # print(candidates)
                    
                    # 从中选择合理的数值
                    for big, small in candidates:
                        # 备选的高低压合理
                        if LOWEST_HIGH_PRESSURE <= big <= HIGHEST_HIGH_PRESSURE and LOWEST_LOW_PRESSURE <= small <= HIGHEST_LOW_PRESSURE:
                            # 实际的高低压合理
                            if LOWEST_HIGH_PRESSURE <= high <= HIGHEST_HIGH_PRESSURE and LOWEST_LOW_PRESSURE <= low <= HIGHEST_LOW_PRESSURE:
                                # 选择绝对值小的作为实际高低压
                                high, low = (big, small) if abs(big - small) < abs(high - low) else (high, low)
                            # 否则直接选择备选高低压作为结果
                            else:
                                high, low = big, small
                            break

                        # 备选的高低压不合理
                        else:
                            # 实际的高低压合理
                            if LOWEST_HIGH_PRESSURE <= high <= HIGHEST_HIGH_PRESSURE and LOWEST_LOW_PRESSURE <= low <= HIGHEST_LOW_PRESSURE:
                                pass
                            # 否则直接选择备选高低压作为结果
                            else:
                                # 如果实际高压值未获取其一
                                if high == 0 or low == 0:
                                    high, low = (big, small) if big != 0 and small != 0 else (high, low) 
                                else:
                                    high, low = (big, small) if abs(big - small) < abs(high - low) and big != 0 and small != 0 else (high, low) 
                        # print(high, low)

            # 含有关键字的情况
            else:
                high, low, value = 0, 0, 0
                WordList, flag = {'高压': 0, '高': 0, '收缩压': 0, '低压': 1, '低': 1, '舒张压': 1}, False
                for i, item in enumerate(wordseg):
                    if item in WordList:
                        flag = True
                        if WordList[item] == 0:
                            [_, high] = self._CalcNumber(wordseg, i)
                        elif WordList[item] == 1:
                            [_, low] = self._CalcNumber(wordseg, i)


            # 校验高低压是否合理
            # https://xw.qq.com/cmsid/20190107A053DR00
            if  high == 0:
                return Errback(MSG_BLOOD_HIGH_NO)
            elif low == 0:
                return Errback(MSG_BLOOD_LOW_NO)
            elif high < LOWEST_HIGH_PRESSURE:
                return Errback(MSG_BLOOD_HIGHLOW.format(high))
            elif high > HIGHEST_HIGH_PRESSURE:
                return Errback(MSG_BLOOD_HIGHHIGH.format(high))
            elif low < LOWEST_LOW_PRESSURE:
                return Errback(MSG_BLOOD_LOWLOW.format(low))
            elif low > HIGHEST_LOW_PRESSURE:
                return Errback(MSG_BLOOD_LOWHIGH.format(low))
            elif low >= high:
                return Errback(MSG_BLOOD_NOTHIGHERTHAN.format(high, low))
            else:
                return BackTypeA(high, low)

        # 今天心率是多少？
        if TypeNum == '2':
            # 判断是正向或者反向
            if wordseg[Index] in ['下', '次', '回']:
                flag = True
            else:
                flag = False
            [_, value] = self._CalcNumber(wordseg, Index, radius=len(wordseg), flag=flag)

            # if value == 0:
            #     for i, item in enumerate(wordseg):
            #         if item in self.unit:
            #             [_, value] = self._CalcNumber(wordseg, i, True)


            # 校验心率是否合理
            # https://baike.baidu.com/item/%E4%BA%BA%E4%BD%93%E6%9E%81%E9%99%90/9669783?fr=aladdin
            if value == 0:
                return Errback(MSG_HEARTRATE_NO)
            elif value < LOWEST_HEARTRATE:
                return Errback(MSG_HEARTRATE_LOW.format(value))
            elif value > HIGHEST_HEARTRATE:
                return Errback(MSG_HEARTRATE_HIGH.format(value))
            else:
                return BackTypeB(value)

        # 今天体重是多少？
        if TypeNum == '3':
            # 判断是正向或者反向
            if wordseg[Index] in self.weight:
                flag = True
            else:
                flag = False
            [_, value] = self._CalcNumber(wordseg, Index, radius=len(wordseg), flag=flag)

            # if value == 0:
            #     for i, item in enumerate(wordseg):
            #         if item in self.weight:
            #             [_, value] = self._CalcNumber(wordseg, i, True)

            # 校验体重是否合理
            if value == 0:
                return Errback(MSG_WEIGHT_NO)
            elif value < LOWEST_WEIGHT:
                return Errback(MSG_WEIGHT_LOW.format(value))
            elif value > HIGHEST_WEIGHT:
                return Errback(MSG_WEIGHT_HIGH.format(value))
            else:
                return BackTypeC(value)

        # 今天服药情况如何？
        if TypeNum == '4':
            medicines, DrugList, flag = [], [], False
            for i, item in enumerate(wordseg):
                if item in self.no:
                    return BackTypeD('NULL')
                if item in self.unit:
                    flag = True
                    [key, value] = self._CalcNumber(wordseg, i, DrugList, True)
                    # 确认为药物并且非与之前重复的药物
                    if key in self.drugName and key not in DrugList:
                        DrugList.append(key)
                        medicines.append({"name": key, "number": value, "unit": self.mapping.get(item)})

            # 对于没有单位的药物
            for item in wordseg:
                if item in self.drugName and item not in DrugList:
                    flag = True
                    DrugList.append(item)
                    medicines.append({'name': item, 'number': '', 'unit': ''})

            if flag:
                return BackTypeD(medicines)
            else:
                logger.info("[Audio Mark] {}".format(wordseg))
                return Errback(MSG_MEDICINE_NO)

        # 今天状态如何？
        if TypeNum == '5':
            status, tmp = [], None
            for word in wordseg:
                keyword = self.mapping.get(word)
                # 在映射表中除去消极词的症状词
                if keyword and keyword not in self.bad:
                    # 部位症状
                    if keyword in self.parts:
                        tmp = {'specific': keyword, 'statusCode': 1}
                    else:
                        status.append({"specific": keyword, "statusCode": 2})
                else:
                    # “疼、痛、痒、难受”类部位疾病
                    if word in self.bad:
                        # 之前有部位记录
                        if tmp:
                            tmp = {"specific": tmp['specific'] + keyword, "statusCode": 2}
                            status.append(tmp)
                            tmp = None
                        else:
                            status.append({'specific': '', 'statusCode': 2})
                    # 除上述词以外的消极词
                    elif word in self.negative:
                        status.append({"specific": '', "statusCode": 2})
            # 是否筛选出不良状态
            if status:
                specific_list = [instance['specific'] for instance in status if instance['specific']]
                specific = ','.join(specific_list)
                if specific:
                    return BackTypeE({"specific": specific, "statusCode": 2})
                else:
                    return BackTypeE({"specific": '状态不好', "statusCode": 2})
            else:
                return BackTypeE({"specific": '状态好', "statusCode": 1})
        # 错误记录
        logger.info("[Audio Mark] {}".format(wordseg))
        return Errback(MSG_NO)

    # 判断句子回答的哪个问题
    def JudgeType(self, wordseg, situation):
        if wordseg:
            # KeyWord, TypeNum, Index, Gflag = "NULL", 0, 0, False
            TypeNum, Index = 0, 0
            for i, item in enumerate(wordseg):
                if item in self.status:
                    # KeyWord, Index = item, i
                    # 第一次找到关键字
                    if TypeNum == 0:
                        TypeNum = self.status[item]
                        Index = i
                    # 关键字与之前的相同
                    elif TypeNum == self.status[item]:
                        pass
                    else:
                        return Errback(MSG_WEIRD)

            mapping = {'0': '3', '1': '1', '2':'2'}

            # 如果situation和分析得到的情境一样
            if TypeNum == mapping[situation]:
                return self._ModifyType(wordseg, TypeNum, Index)

            # 如果situation和分析得到的情境不一样
            if TypeNum != mapping[situation]:
                # 如果未分析出情境，采取situation表示的情境
                if TypeNum == 0:
                    return self._ModifyType(wordseg, mapping[situation], -1)
                return Errback(MSG_DIFF)

            return Errback(MSG_NO)
        else:
            return Errback(MSG_NONE)
