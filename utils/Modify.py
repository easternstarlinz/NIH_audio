# ！/usr/bin/env python3
# -*- coding: utf-8 -*-

# ========================================================
#   Copyright (C) 2018 All rights reserved.
#
#   filename : Modify.py
#   author   : shenge
#   update   :
#   date     : 2019-10-14
#   desc     :
# ========================================================

import os, sys, copy, time
from pathlib import Path
from enum import Enum, unique

from pypinyin import pinyin, lazy_pinyin, Style
from pypinyin.style import convert

## 单测使用
#    --------------------   字典
# # 医学字典
# DICT_MED = './dict/hf_dict_utf8.txt'
# # 改错拼音字典
# DICT_PY = './dict/pinyin_list.txt'
# # 改错预处理替换规则
# DICT_PRE_RULE = './dict/dict_pre_rule.txt'
# # 改错附加自定义字典
# DICT_CUSTOM = './dict/dict_custom.txt'
# # 改错过滤规则
# DICT_FILTER_RULE = './dict/dict_filter_rule.txt'

## 线上使用
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from instance.Variable import *

# utils update by shenge
def get_pinyin_for_match(pinyin_tone_list):
    result = {}
    for pinyin_tone in pinyin_tone_list:
        initial = convert(pinyin_tone, strict=True, style=Style.INITIALS)
        final = convert(pinyin_tone, strict=True, style=Style.FINALS)

        complete = ''
        if not initial and not final: # handle possible bad case
            complete = pinyin_tone
        else:
            complete = f"{initial}{final}"

        if complete not in result:
            result[complete] = (initial, final)

    return result

# enum for threshold level
@unique
class ASR_Corrector_FuzzyLevel(Enum):
    Normal = 0
    MoreFuzzy = 1
    MoreStrict = 2


# jump table entry, head for all items passed start_th, tail are all sim scores excluding start pinyin
class JumpTableEntry(object):
    def __init__(self, num):
        self.head_table = []
        self.tail_table = [[] for i in range(num)]

    def __repr__(self):
        return f"[head-> {self.head_table}, tail-> {self.tail_table}]"


# match status, keeping track of specific matches
class MatchStatus(object):
    def __init__(self, id, text, the_item_len, text_start, match_score, sum_score_th, max_single_score):
        self.text = text
        self.max_ch_score = max_single_score

        self.item_id = id  # item id is the id of predefined item
        self.cur_pos = 0
        self.item_len = the_item_len

        self.text_start_pos = text_start
        self.sum_score = match_score
        self.score_th = sum_score_th

    def __repr__(self):
        return f"[{self.item_id} -> {self.text}, pos: {self.cur_pos} < {self.item_len}, text_start: {self.text_start_pos}, score: {self.sum_score}, th: {self.score_th}"

    # return is_pass, is_prune
    def check_stop(self):
        if self.sum_score >= self.score_th:
            return True, False

        if (self.sum_score + max(0, self.item_len - self.cur_pos - 1) * self.max_ch_score) < self.score_th:
            return False, True

        return False, False


# the main corrector class
class ASR_Corrector(object):
    def __init__(self, fuzzy_level=ASR_Corrector_FuzzyLevel.Normal,
                 hf_dict=DICT_MED,
                 py_dict=DICT_PY,
                 rep_rule=DICT_PRE_RULE,
                 filter_dict=DICT_FILTER_RULE,
                 custom_dict=DICT_CUSTOM,
                 extra_dict=None):
        self.init(fuzzy_level)
        self.load_filter_rule(filter_dict)
        self.load_dict_file(hf_dict)
        self.load_py_dict_file(py_dict)
        self.load_rule(rep_rule)
        self.custom_process(custom_dict, extra_dict)
        self.build_index()

    # all the initializations are done here
    def init(self, fuzzy_level):
        if fuzzy_level == ASR_Corrector_FuzzyLevel.MoreFuzzy:
            # more fuzzy thresholds
            self.py_full_match = 0.95
            self.py_fuzzy_match_level_4 = 0.9
            self.py_fuzzy_match_level_3 = 0.8
            self.py_final_match = 0.6
            self.py_fuzzy_match_level_2 = 0.55
            self.py_initial_match = 0.5
            self.py_fuzzy_match_level_1 = 0.45

            self.start_th = 0.5
            self.avg_th = 0.6
        elif fuzzy_level == ASR_Corrector_FuzzyLevel.MoreStrict:
            # with more
            self.py_full_match = 0.95
            self.py_fuzzy_match_level_4 = 0.9
            self.py_fuzzy_match_level_3 = 0.8
            self.py_final_match = 0.75
            self.py_fuzzy_match_level_2 = 0.7
            self.py_initial_match = 0.5
            self.py_fuzzy_match_level_1 = 0.45

            self.start_th = 0.9
            self.avg_th = 0.78
        else:
            # normal or not captured by previous conditions
            self.py_full_match = 0.95
            self.py_fuzzy_match_level_4 = 0.9
            self.py_fuzzy_match_level_3 = 0.8
            self.py_final_match = 0.75
            self.py_fuzzy_match_level_2 = 0.7
            self.py_initial_match = 0.5
            self.py_fuzzy_match_level_1 = 0.45

            self.start_th = 0.9
            self.avg_th = 0.7

        self.med_names = set()
        self.med_py_list = []

        self.filter_pre_dict = {}
        self.filter_dict = {}

        self.hf_symptom = []
        self.hf_examination = []
        self.hf_medicine = []

        # standard fuzzy pinyin replacement
        # z - zh, s - sh, c - ch, n - l, r - l, h - f
        # an - ang, en - eng, in - ing, ian - iang, uan - uang
        # hui - fei, huang - wang
        self.py_initial_fuzzy_map = {'z': 'zh', 's': 'sh', 'c': 'ch', 'n': 'l', 'r': 'l', 'h': 'f'}
        self.py_final_fuzzy_map = {'an': 'ang', 'en': 'eng', 'in': 'ing', 'ian': 'iang', 'uan': 'uang'}
        self.py_full_fuzzy_map = {'hui': 'fei', 'huang': 'wang'}

        # map from matching status to actual score
        self.fuzzy_score_map = {'mm': self.py_full_match,
                                'fm': self.py_fuzzy_match_level_4, 'mf': self.py_fuzzy_match_level_4,
                                'f': self.py_fuzzy_match_level_4,  # this is the special case for full replacement
                                'ff': self.py_fuzzy_match_level_3,
                                'nm': self.py_final_match,
                                'nf': self.py_fuzzy_match_level_2,
                                'mn': self.py_initial_match,
                                'fn': self.py_fuzzy_match_level_1,
                                'nn': 0.0
                                }

        # index related
        self.all_pinyin = {}
        self.sim_score_cache = {}
        self.jump_table = {}

        # pre-process related initialization
        # for remove chinese punctuations
        self.cn_remove_table = str.maketrans(dict.fromkeys('，；、。？！'))
        # for saving bad case, do some replace
        self.replace_list = []

        # special character handling, syntax only work for python 3.5+
        self.special_placeholder = '_'
        self.ph_remove_table = str.maketrans(dict.fromkeys(self.special_placeholder))
        self.special_py_list = {
            **dict.fromkeys(['a', 'A'], [{'ei': ('', 'ei')}]),
            **dict.fromkeys(['b', 'B'], [{'bi': ('b', 'i')}]),
            **dict.fromkeys(['c', 'C'], [{'sei': ('s', 'ei')}]),
            **dict.fromkeys(['d', 'D'], [{'di': ('d', 'i')}]),
            **dict.fromkeys(['e', 'E'], [{'i': ('', 'i')}]),
            **dict.fromkeys(['f', 'F'], [{'ei': ('', 'ei')}, {'f': ('f', '')}]),
            **dict.fromkeys(['g', 'G'], [{'ji': ('j', 'i')}]),
            **dict.fromkeys(['h', 'H'], [{'ei': ('', 'ei')}, {'ch': ('ch', '')}]),
            **dict.fromkeys(['i', 'I'], [{'ai': ('', 'ai')}]),
            **dict.fromkeys(['j', 'J'], [{'jie': ('j', 'ie')}]),
            **dict.fromkeys(['k', 'K'], [{'kei': ('k', 'ei')}]),
            **dict.fromkeys(['l', 'L'], [{'ei': ('', 'ei')}, {'l': ('l', '')}]),
            **dict.fromkeys(['m', 'M'], [{'ei': ('', 'ei')}, {'m': ('m', '')}]),
            **dict.fromkeys(['n', 'N'], [{'ei': ('', 'ei')}, {'n': ('n', '')}]),
            **dict.fromkeys(['o', 'O'], [{'ou': ('', 'ou')}]),
            **dict.fromkeys(['p', 'P'], [{'pi': ('p', 'i')}]),
            **dict.fromkeys(['q', 'Q'], [{'kiou': ('k', 'iou')}]),
            **dict.fromkeys(['r', 'R'], [{'a': ('', 'a')}]),
            **dict.fromkeys(['s', 'S'], [{'ei': ('', 'ei')}, {'s': ('s', '')}]),
            **dict.fromkeys(['t', 'T'], [{'ti': ('t', 'i')}]),
            **dict.fromkeys(['u', 'U'], [{'iou': ('', 'iou')}]),
            **dict.fromkeys(['v', 'V'], [{'uei': ('', 'uei')}]),
            **dict.fromkeys(['w', 'W'], [{'da': ('d', 'a')}, {'b': ('b', '')}, {'liou': ('l', 'iou')}]),
            **dict.fromkeys(['x', 'X'], [{'ai': ('', 'ei')}, {'k': ('k', '')}, {'s': ('s', '')}]),
            **dict.fromkeys(['y', 'Y'], [{'uai': ('', 'uai')}]),
            **dict.fromkeys(['z', 'Z'], [{'zei': ('z', 'ei')}]),
            '0': [{'ling': ('l', 'ing')}], '1': [{'i': ('', 'i'), 'iao': ('', 'iao')}],
            '2': [{'er': ('', 'er')}],     '3': [{'san': ('s', 'an')}],
            '4': [{'si': ('s', 'i')}],     '5': [{'u': ('', 'u')}],
            '6': [{'liou': ('l', 'iou')}], '7': [{'qi': ('q', 'i')}],
            '8': [{'ba': ('b', 'a')}],     '9': [{'jiou': ('j', 'iou')}],
            '.': [{'dian': ('d', 'ian')}]
        }
        self.jump_table_special = {}

    # load filter rule
    def load_filter_rule(self, filter_dict):
        if filter_dict is None:
            return

        filter_dict_path = Path(filter_dict)
        if not filter_dict_path.is_file():  # file not exists, we search for correct file
            filter_dict_path = Path(__file__).resolve().parent / '../dict/dict_filter_rule.txt'

        with open(str(filter_dict_path), mode='r', encoding='utf-8') as filter_dict_f:
            for line in filter_dict_f:
                s = line.strip().split('\t')

                # current only first split has effect, but it could be extend later
                self.filter_pre_dict[s[0]] = []

    # load medicine list
    def load_dict_file(self, hf_dict):
        if hf_dict is None:
            return

        dict_path = Path(hf_dict)
        if not dict_path.is_file():  # file not exists, we search for correct file
            dict_path = Path(__file__).resolve().parent / '../dict/hf_dict_utf8.txt'

        with open(str(dict_path), mode='r', encoding='utf-8') as dict_f:
            for line in dict_f:
                s = line.strip().split('\t')

                if s[1] == '症状-体征':
                    self.hf_symptom.append(s[0])
                elif s[1] == '监测指标':
                    self.hf_examination.append(s[0])
                elif s[1] == '药物':
                    self.hf_medicine.append(s[0])
                else:
                    print(f"Unrecognized data {s[0]} {s[1]}")

        for item in self.hf_medicine:
            self.add_item_to_pylist(item)

    # load all possible pinyin list, for building indices
    def load_py_dict_file(self, py_dict):
        py_dict_path = Path(py_dict)
        if not py_dict_path.is_file():  # file not exists, we search for correct file
            py_dict_path = Path(__file__).resolve().parent / '../dict/pinyin_list.txt'

        with open(str(py_dict_path), mode='r', encoding='utf-8') as dict_f:
            for line in dict_f:
                s = line.rstrip('\n').split('\t')

                self.all_pinyin[s[0]] = (s[1], s[2])

    # load pre-process rules, to get rid of some stubborn bad cases
    def load_rule(self, rep_rule):
        if rep_rule is None:
            return

        rep_rule_path= Path(rep_rule)
        if not rep_rule_path.is_file():  # file not exists, we search for correct file
            rep_rule_path = Path(__file__).resolve().parent / '../dict/dict_pre_rule.txt'

        with open(str(rep_rule_path), mode='r', encoding='utf-8') as dict_f:
            for line in dict_f:
                s = line.rstrip('\n').split('\t')

                self.replace_list.append((s[0], s[1]))

    # add some temporary custom terms to the system
    def custom_process(self, custom_dict, extra_dict):
        if custom_dict:
            custom_dict_path = Path(custom_dict)
            if not custom_dict_path.is_file():  # file not exists, we search for correct file
                custom_dict_path = Path(__file__).resolve().parent / '../dict/dict_custom.txt'

            with open(str(custom_dict_path), mode='r', encoding='utf-8') as dict_f:
                for line in dict_f:
                    s = line.rstrip('\n')

                    self.add_item_to_pylist(s)

        if type(extra_dict) in [list, tuple]:
            for s in extra_dict:
                self.add_item_to_pylist(s)

    # get pinyin list for given text
    def get_item_py(self, item, heteronym=False):
        pys = []

        # get different type of pinyin, based on input flag
        if heteronym is True:
            pys = pinyin(item, heteronym=True)
        else:
            pys = pinyin(item)

        # special handling for new pypinyin version which removes all numbers
        item_py = []
        pos = 0
        for py_items in pys:
            if not py_items: # defensive programming, py_items should be at least >= 1
                continue

            py_len = len(py_items[0])
            if item[pos:pos+py_len] == py_items[0]: # direct copy of string, so not pinyin, we will not process
                item_py.append({py_items[0]: ('', '')})
                pos += py_len
            else:
                item_py.append(get_pinyin_for_match(py_items))
                pos += 1

        return item_py

    # add special contents to the altered text and pinyin buffer, based on given special character mapping
    def handle_ch_special_py(self, ch_spec, item_spec, item_py_spec):
        ch_mapped = self.special_py_list[ch_spec]

        ch_len = len(ch_mapped)
        item_spec.append(ch_spec)
        item_spec.extend([self.special_placeholder]*(ch_len-1))

        item_py_spec.extend(ch_mapped)

    # process original content, handling special characters
    def handle_item_special_py(self, item, item_py):
        item_special = []
        item_py_special = []

        pos_i = 0
        pos_i_limit = len(item)
        pos_j = 0
        pos_sub_j = 0
        pos_sub_j_limit = 0

        while pos_i < pos_i_limit:
            ch = item[pos_i]

            if pos_sub_j < pos_sub_j_limit:  # already in a character range with no pinyin
                if ch in self.special_py_list:
                    self.handle_ch_special_py(ch, item_special, item_py_special)

                pos_sub_j += 1
            else:
                ch_py = next(iter(item_py[pos_j].keys()))

                # len(ch_py) == 0 will not be true
                if ch_py[0] != ch: # means ch_py is py and ch is character with pinyin, so they must be different
                    item_special.append(ch)
                    item_py_special.append(item_py[pos_j])
                else: # else we need to enter special loop
                    pos_sub_j_limit = len(ch_py)

                    if ch in self.special_py_list:
                        self.handle_ch_special_py(ch, item_special, item_py_special)
                    pos_sub_j = 1

            if pos_sub_j >= pos_sub_j_limit:
                pos_j += 1
            pos_i += 1

        return ''.join(item_special), item_py_special

    # add items to our correction list
    def add_item_to_pylist(self, item):
        if len(item) < 2:
            print('ERROR: cannot add correction item with length < 2')
            return

        # avoid repeat add
        if item in self.med_names:
            return
        else:
            self.med_names.add(item)

        item_py = self.get_item_py(item)

        item_s, item_py_s = self.handle_item_special_py(item, item_py)

        # check filter list and add processed name to filter list
        if item in self.filter_pre_dict:
            self.filter_dict[item_s] = [len(item_s)]

        # currently we have two kind of indices to support two types of API
        self.med_py_list.append((item, item_py, len(item), item_s, item_py_s, len(item_s)))

        # assign column number, easier for future changes
        self.special_pinyin_col = 4
        self.special_pinyin_len_col = 5

    # build indices
    def build_index(self):
        # build common index
        for k, v in self.all_pinyin.items():
            cur_entry = JumpTableEntry(len(self.med_py_list))

            for item_id, item in enumerate(self.med_py_list):
                py_list = item[1]
                l = min(len(py_list), item[2])

                for i in range(l):
                    # get top-1 result, if program is correct, length will be exactly 1
                    py, py_part = next(iter(py_list[i].items()))

                    score = self.get_single_match_score(k, v, py, py_part)

                    if i == 0:  # start ch
                        if score >= self.start_th:
                            cur_entry.head_table.append((item_id, score))
                    else:
                        cur_entry.tail_table[item_id].append(score)

            self.jump_table[k] = copy.deepcopy(cur_entry)

        # build special index
        for k, v in self.all_pinyin.items():
            cur_entry = JumpTableEntry(len(self.med_py_list))

            for item_id, item in enumerate(self.med_py_list):
                py_list = item[self.special_pinyin_col] # special
                l = item[self.special_pinyin_len_col]

                for i in range(l):
                    # need to process multiple case
                    score = 0.0
                    for py, py_part in py_list[i].items():
                        cur_score = self.get_single_match_score(k, v, py, py_part)
                        score = max(score, cur_score)

                    if i == 0:  # start ch
                        if score >= self.start_th:
                            cur_entry.head_table.append((item_id, score))
                    else:
                        cur_entry.tail_table[item_id].append(score)

            self.jump_table_special[k] = copy.deepcopy(cur_entry)

    # v0 version, exhaustive search with no early stop
    def asr_correct_text_v0(self, text):
        pys = pinyin(text, heteronym=True)

        text_py = [get_pinyin_for_match(py_item) for py_item in pys]
        text_len = len(text_py)

        match_list = []

        for med_item in self.med_py_list:  # loop for each pre-defined medical entity
            item_py = med_item[1]
            item_len = med_item[2]

            for i in range(text_len - item_len + 1):
                is_match, score = self.check_match_v0(text_py, i, item_py, False)
                if is_match:
                    match_list.append((med_item[0], i, score))

        result = text
        if match_list:  # not empty
            if len(match_list) > 1:  # need sort
                match_list = self.filter_match(sorted(match_list, key=lambda x: -x[2]), text)  # score descending

            result = self.apply_correction_use_match(text, match_list)

        return result, match_list

    # check match simple version used in v0
    def check_match_v0(self, text_py, start_pos, item_py, use_cache=True):
        avg_score = 0.0

        for i, ch_py in enumerate(item_py):
            score = self.get_sim_score_v0(text_py[start_pos + i], ch_py, use_cache)
            if i == 0 and score < self.start_th:
                return False, 0  # fail to match
            avg_score += score

        l = len(item_py)
        avg_score *= self.score_adjust(l) / l  # lower score for short words to alleviate false positives
        if avg_score > self.avg_th:
            return True, avg_score
        else:
            return False, avg_score

    # get similarity score simple version
    def get_sim_score_v0(self, text_ch_py, item_ch_py, use_cache=True):
        score = 0.0
        m_k, m_v = next(iter(item_ch_py.items()))  # for item, we only consider top-1

        # check complete match, return fast
        if m_k in text_ch_py:
            return self.py_full_match

        # check partial match
        for k, v in text_ch_py.items():  # text pinyin have multiple form
            cur_score = self.get_single_match_score(k, v, m_k, m_v, use_cache)

            if cur_score > score:
                score = cur_score

        return score

    # filter overlapping match based on similarity, using non-maximum-suppress logic
    def filter_match(self, match_list, text):
        l = len(match_list)
        filtered = [False] * l

        # first filter all items with correct text
        # currently disable for better results
        # for i in range(l):
        #     i_st = match_list[i][1]
        #     i_ed = match_list[i][1] + len(match_list[i][0])

        #     if text[i_st:i_ed] == match_list[i][0]:
        #         filtered[i] = True

        # then we use non-maximum-supress style algorithm to filter cross ranges
        for i in range(l - 1):
            if filtered[i]:
                continue
            i_st = match_list[i][1]
            i_ed = match_list[i][1] + len(match_list[i][0])

            j = i + 1
            while j < l:
                if not filtered[j]:
                    j_st = match_list[j][1]
                    j_ed = match_list[j][1] + len(match_list[j][0])

                    cross_st = max(i_st, j_st)
                    cross_ed = min(i_ed, j_ed)

                    if cross_st < cross_ed:  # find cross, throw j away
                        filtered[j] = True

                j += 1

        return [item[0] for item in zip(match_list, filtered) if not item[1]]

    # apply match
    def apply_correction_use_match(self, text, match_list):
        for item in match_list:
            text = f"{text[:item[1]]}{item[0]}{text[(item[1] + len(item[0])):]}"

        return text

    # check table to get match score for current pinyin and the character of item_id at pos
    def get_item_rest_match_score(self, ch_py, item_id, pos):
        result_score = 0

        if pos < 1:
            return 0

        for k, v in ch_py.items():
            if k in self.jump_table:
                tail_list = self.jump_table[k].tail_table

                result_score = max(result_score, tail_list[item_id][pos - 1])

        return result_score

        # when confirmed match, we calculate the actual score
    def finish_match_score(self, match_status, text):
        pos = match_status.cur_pos + 1
        limit = match_status.item_len
        result_score = match_status.sum_score

        while pos < limit:
            text_pos = match_status.text_start_pos + pos

            cur_score = self.get_item_rest_match_score(text[text_pos], match_status.item_id, pos)

            result_score += cur_score

            pos += 1

        result_score *= self.score_adjust(limit) / limit

        return result_score

    # check match with special index
    def get_item_rest_match_score_special(self, ch_py, item_id, pos):
        result_score = 0

        if pos < 1:
            return 0

        for k, v in ch_py.items():
            if k in self.jump_table:
                tail_list = self.jump_table_special[k].tail_table

                result_score = max(result_score, tail_list[item_id][pos - 1])

        return result_score

    # finish score special version
    def finish_match_score_special(self, match_status, text):
        pos = match_status.cur_pos + 1
        limit = match_status.item_len
        result_score = match_status.sum_score

        while pos < limit:
            text_pos = match_status.text_start_pos + pos

            cur_score = self.get_item_rest_match_score_special(text[text_pos], match_status.item_id, pos)

            result_score += cur_score

            pos += 1

        result_score *= self.score_adjust(limit) / limit

        return result_score

    # do text pre-process, removing punctuations and apply pre-process rule
    def preprocess_text(self, text):
        # remove punctuations, reduce erroneous punctuation placement
        text = text.translate(self.cn_remove_table)

        # apply predefined bad case saving, only for small data
        for k, v in self.replace_list:
            text = text.replace(k, v)

        return text

    # main API for correction, v1 version, with no special character handling
    def asr_correct_text_v1(self, text):

        text = self.preprocess_text(text)

        pys = pinyin(text, heteronym=True)

        text_py = [get_pinyin_for_match(py_item) for py_item in pys]
        text_len = len(text_py)

        match_status_list = []
        final_matches = []

        # loop through each pinyin in text
        for i, ch_py in enumerate(text_py):
            # process existing matches
            for pos, match_item in enumerate(match_status_list):
                match_item.cur_pos += 1
                cur_score = self.get_item_rest_match_score(ch_py, match_item.item_id, match_item.cur_pos)

                match_item.sum_score += cur_score

            # process start match
            score_map = {}
            for k, v in ch_py.items():
                if k in self.jump_table:
                    head_list = self.jump_table[k].head_table

                    for item_id, score in head_list:
                        if item_id in score_map:
                            score_map[item_id] = max(score_map[item_id], score)
                        else:
                            score_map[item_id] = score

            # add all head status
            for m_id, m_score in score_map.items():
                item_len = self.med_py_list[m_id][2]
                if i + item_len <= text_len:  # possible to get full item match
                    cur_status = MatchStatus(m_id, self.med_py_list[m_id][0], item_len, i, m_score, self.get_score_threshold(item_len),
                                             self.py_full_match)

                    match_status_list.append(cur_status)

            # check stop criterion
            pos = 0
            limit = len(match_status_list)
            while pos < limit:
                cur_match_status = match_status_list[pos]
                is_pass, is_prune = cur_match_status.check_stop()

                if is_pass:
                    final_score = self.finish_match_score(cur_match_status, text_py)

                    final_matches.append((self.med_py_list[cur_match_status.item_id][0],
                                          cur_match_status.text_start_pos,
                                          final_score))

                if is_pass or is_prune:  # do remove, use last element to fill in and pop last
                    match_status_list[pos] = match_status_list[-1]
                    match_status_list.pop()

                    limit -= 1
                else:
                    pos += 1

        # post process, filter inappropriate matches, such as exact same match and matches that have range conflicts
        result = text
        if final_matches:  # not empty
            if len(final_matches) > 1:  # need sort
                final_matches = self.filter_match(sorted(final_matches, key=lambda x: -x[2]), text)  # score descending

            result = self.apply_correction_use_match(text, final_matches)

        return result, final_matches

    # do adjust for short items, alleviating false positives
    def score_adjust(self, l):
        return min(1.0, 0.7 + 0.075 * l)

    # based on adjust to infer the threshold of original sum
    def get_score_threshold(self, l):
        return self.avg_th * l / self.score_adjust(l)

    # get single pinyin match score with cached results, avoiding repeat calculations
    def get_single_match_score(self, py_full_1, py_tuple_1, py_full_2, py_tuple_2, use_cache=True):
        cache_key_1, cache_key_2 = '', ''
        if use_cache is True:
            cache_key_1 = f"{py_full_1}_{py_full_2}"
            cache_key_2 = f"{py_full_2}_{py_full_1}"

            if cache_key_1 in self.sim_score_cache:
                return self.sim_score_cache[cache_key_1]

        py_full_match_status = self.get_py_part_match_status(self.py_full_fuzzy_map, py_full_1, py_full_2)

        final_score = -1.0

        if py_full_match_status == 'f':
            final_score = self.fuzzy_score_map['f']  # for overall fuzzy mapping rule
        else:
            py_tuple_match_status = self.get_py_tuple_match_status(py_tuple_1, py_tuple_2)

            final_score = self.fuzzy_score_map[py_tuple_match_status]

        if use_cache is True:
            # update cache
            self.sim_score_cache[cache_key_1] = final_score
            self.sim_score_cache[cache_key_2] = final_score

        return final_score

    # get match scores for different situations
    # return 'xx', x = 'm', 'f' or 'n'
    # 'm' for 'match', 'f' for 'fuzzy match', 'n' for 'not match'
    def get_py_tuple_match_status(self, py_tuple_1, py_tuple_2):
        py_initial_match_status = self.get_py_part_match_status(self.py_initial_fuzzy_map, py_tuple_1[0], py_tuple_2[0])
        py_final_match_status = self.get_py_part_match_status(self.py_final_fuzzy_map, py_tuple_1[1], py_tuple_2[1])

        return f"{py_initial_match_status}{py_final_match_status}"

    # return match status for pinyin initial or final
    def get_py_part_match_status(self, py_fuzzy_map, py_part_1, py_part_2):
        if py_part_1 == py_part_2:
            return 'm'
        elif self.get_mapped_py(py_fuzzy_map, py_part_1) \
                == self.get_mapped_py(py_fuzzy_map, py_part_2):
            return 'f'
        else:
            return 'n'

    # handle fuzzy pinyin
    def get_mapped_py(self, py_fuzzy_map, py):
        if py in py_fuzzy_map:
            return py_fuzzy_map[py]
        else:
            return py

    # remove all place holders and adjust match start positions
    def adjust_result_special(self, result, matches):
        move_table = []

        ph_num = 0
        for ch in result:
            if ch == self.special_placeholder:
                ph_num += 1

            move_table.append(ph_num)

        adjusted_matches = []
        for m in matches:
            pos = m[1]
            pos -= move_table[pos]

            adjusted_matches.append((m[0].translate(self.ph_remove_table), pos, m[2]))

        return result.translate(self.ph_remove_table), adjusted_matches

    def judge_filter_match(self, match, text):
        if match[0] in self.filter_dict:
            filter_rule = self.filter_dict[match[0]]

            # actual filter rule, currently simple, but may be extended
            if len(text) != filter_rule[0]:
                return True
            else:
                return False

        return False

    # filter match using NMS logic, promoting similarity scores for exact matches
    # also handle some filter rules to turn down some matches
    def filter_match_special(self, match_list, text):
        l = len(match_list)
        filtered = [False] * l

        # for exact match, we should raise similarity score to 1.0
        for i in range(l):
            i_st = match_list[i][1]
            i_ed = match_list[i][1] + len(match_list[i][0])

            if text[i_st:i_ed] == match_list[i][0]:
                match_list[i] = (match_list[i][0], match_list[i][1], 1.0)

            # check filter rule
            filtered[i] = self.judge_filter_match(match_list[i], text)

        # score adjust end, we do sort here
        match_list = [match for match, filter_flag in zip(match_list, filtered) if not filter_flag]
        match_list = sorted(match_list, key=lambda x: (x[2], len(x[0])), reverse=True)
        l = len(match_list)
        filtered = [False] * l

        # then we use non-maximum-supress style algorithm to filter cross ranges
        for i in range(l - 1):
            if filtered[i]:
                continue
            i_st = match_list[i][1]
            i_ed = match_list[i][1] + len(match_list[i][0])

            j = i + 1
            while j < l:
                if not filtered[j]:
                    j_st = match_list[j][1]
                    j_ed = match_list[j][1] + len(match_list[j][0])

                    cross_st = max(i_st, j_st)
                    cross_ed = min(i_ed, j_ed)

                    if cross_st < cross_ed:  # find cross, throw j away
                        filtered[j] = True

                j += 1

        return [match for match, filter_flag in zip(match_list, filtered) if not filter_flag]

    # main API for correction,v2 version, advanced version with special character handling
    def asr_correct_text(self, text):

        text_r = self.preprocess_text(text)

        # pys = pinyin(text_r, heteronym=True)
        # text_py_r = [get_pinyin_for_match(py_item) for py_item in pys]

        text_py_r = self.get_item_py(text_r, heteronym=True)
        text_len_r = len(text_py_r)

        text, text_py = self.handle_item_special_py(text_r, text_py_r)
        text_len = len(text_py)

        #print(text_py)

        match_status_list = []
        final_matches = []

        # loop through each pinyin in text
        for i, ch_py in enumerate(text_py):
            # process existing matches
            for pos, match_item in enumerate(match_status_list):
                match_item.cur_pos += 1
                cur_score = self.get_item_rest_match_score_special(ch_py, match_item.item_id, match_item.cur_pos)

                match_item.sum_score += cur_score

            # process start match
            score_map = {}
            for k, v in ch_py.items():
                if k in self.jump_table:
                    head_list = self.jump_table_special[k].head_table

                    for item_id, score in head_list:
                        if item_id in score_map:
                            score_map[item_id] = max(score_map[item_id], score)
                        else:
                            score_map[item_id] = score

            # add all head status
            for m_id, m_score in score_map.items():
                item_len = self.med_py_list[m_id][5] # item special length
                if i + item_len <= text_len:  # possible to get full item match
                    cur_status = MatchStatus(m_id, self.med_py_list[m_id][3], item_len, i, m_score, self.get_score_threshold(item_len),
                                             self.py_full_match)

                    match_status_list.append(cur_status)

            # check stop criterion
            pos = 0
            limit = len(match_status_list)
            while pos < limit:
                cur_match_status = match_status_list[pos]
                is_pass, is_prune = cur_match_status.check_stop()

                if is_pass:
                    final_score = self.finish_match_score_special(cur_match_status, text_py)

                    final_matches.append((self.med_py_list[cur_match_status.item_id][3], # special
                                          cur_match_status.text_start_pos,
                                          final_score))

                if is_pass or is_prune:  # do remove, use last element to fill in and pop last
                    match_status_list[pos] = match_status_list[-1]
                    match_status_list.pop()

                    limit -= 1
                else:
                    pos += 1

        # post process, filter inappropriate matches, such as exact same match and matches that have range conflicts
        result = text
        if final_matches:  # not empty
            final_matches = self.filter_match_special(final_matches, text)  # postpone sort

            result = self.apply_correction_use_match(text, final_matches)

        # since we introduce place holder, we need to remove them in any cases
        result, final_matches = self.adjust_result_special(result, final_matches)

        return result, final_matches


def test_corrector(corrector, text):
    print(text)

    start = time.perf_counter()
    corrected = corrector.asr_correct_text_v0(text)
    duration_ms_old = (time.perf_counter() - start) * 1000
    print(f"--- v0 method --- {corrected}")
    print(f"used {duration_ms_old} ms")

    start = time.perf_counter()
    corrected = corrector.asr_correct_text_v1(text)
    duration_ms = (time.perf_counter() - start) * 1000
    print(f"--- v1 method --- {corrected}")
    print(f"used {duration_ms} ms")
    print(f"improve ratio {duration_ms_old / duration_ms} ms")

    start = time.perf_counter()
    corrected = corrector.asr_correct_text(text)
    duration_ms_new = (time.perf_counter() - start) * 1000
    print(f"--- v2 method --- {corrected}")
    print(f"used {duration_ms_new} ms")
    print(f"use extra {duration_ms_new - duration_ms} ms")

    print()

def test():
    # normal test
    start = time.perf_counter()
    asr_corrector_normal = ASR_Corrector(extra_dict=['酵素W', 'X精华', '妖妖零', '118', '119'])
    print(f"index used {(time.perf_counter() - start) * 1000} ms")

    print('--------------------------------------------------')
    print('Normal correction tests')
    print('--------------------------------------------------')

    simple_str = '我今天吃了一天被拉土的'
    test_corrector(asr_corrector_normal, simple_str)

    simple_str = '我吃了诺心拖一片美洛托尔名片'
    test_corrector(asr_corrector_normal, simple_str)

    simple_str = '我今天吃了一天没错罗尔'
    test_corrector(asr_corrector_normal, simple_str)

    simple_str = '我今天吃了头孢两片落心托两片'
    test_corrector(asr_corrector_normal, simple_str)

    simple_str = '我今天吃了头孢一片若心坨两片'
    test_corrector(asr_corrector_normal, simple_str)

    simple_str = '我今天吃了头孢一片若心托五片'
    test_corrector(asr_corrector_normal, simple_str)

    simple_str = '我今天吃了一片贝，那普利。我今天，吃了；一天没错、罗尔。一天被？拉土的！'
    test_corrector(asr_corrector_normal, simple_str)

    simple_str = '我吃了一片酵素打不溜还有艾克斯精华，以及R V A，闹心腿'
    test_corrector(asr_corrector_normal, simple_str)

    simple_str = '我吃了一片酵素卡托品品我要吃RV A闹心腿110数值： 1 9    3    .25'
    test_corrector(asr_corrector_normal, simple_str)

    simple_str = '高压么么久滴呀，么么吧。'
    test_corrector(asr_corrector_normal, simple_str)

    simple_str = '我吃了ABCDEFGHIJKLMNOPQRSTUVWXYZ0.123456789'
    test_corrector(asr_corrector_normal, simple_str)

    print()

    # fuzzy test
    # start = time.perf_counter()
    # asr_corrector_fuzzy = ASR_Corrector(fuzzy_level=ASR_Corrector_FuzzyLevel.MoreFuzzy, extra_dict=['酵素W', 'X因子'])
    # print(f"index used {(time.perf_counter() - start) * 1000} ms")
    #
    # print('--------------------------------------------------')
    # print('Fuzzy correction')
    # print('--------------------------------------------------')
    #
    # fuzzy_str = '我今天吃了头孢一片若心托八片'
    # test_corrector(asr_corrector_fuzzy, fuzzy_str)
    #
    # fuzzy_str = '我今天吃了一片闹心腿'
    # test_corrector(asr_corrector_fuzzy, fuzzy_str)

    # stat test
    start = time.perf_counter()
    asr_corrector_stat = ASR_Corrector(fuzzy_level=ASR_Corrector_FuzzyLevel.MoreStrict, hf_dict=None, rep_rule=None,
                                       filter_dict=None, custom_dict=DICT_STAT)
    asr_corrector_stat.avg_th=0.78
    print(f"index used {(time.perf_counter() - start) * 1000} ms")

    print('--------------------------------------------------')
    print('Stat correction')
    print('--------------------------------------------------')

    stat_str = '我今天体重二百五十二磅'
    test_corrector(asr_corrector_stat, stat_str)

    stat_str = '其实宫颈心率每分钟乞食高压么么久滴呀么么吧'#'其实宫颈心率每分钟乞食高压么么久滴呀么么吧'
    test_corrector(asr_corrector_stat, stat_str)

if __name__ == '__main__':
    test()
    pass
