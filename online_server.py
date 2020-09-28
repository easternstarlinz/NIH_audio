# ========================================================
#   Copyright (C) 2018 All rights reserved.
#
#   filename : server.py
#   author   : wangkai
#   updater  : jiangjiacheng
#   date     : 2019-05-03
#   desc     :
# ========================================================

from flask import request, Flask
import requests, json, os, uuid
from utils import *
from instance import *
import pkuseg
import time
import sys
import traceback


# ----------------------------------------------------------------------------------------------------------------------
#  工程接口
# ----------------------------------------------------------------------------------------------------------------------

app = Flask(__name__)

@app.route('/getAudio', methods=['POST'])
def getAudio():
    ip = request.remote_addr
    src = "GetAudio"
    formData = request.form
    f = request.files['file']
    upfilename = f.filename
    datas = formData
    try:

        openid = formData["userid"]
        situation = formData["situation"]
        logger.debug("[Request Log] ip:{} src:{} openid:{} data:{}".format(ip, src, openid, str(datas)).replace("\n","").replace("\r", ""))

        basepath = os.path.dirname(__file__)  # 当前文件所在路径
        createTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(time.time())))

        # 语音接口
        random_name = str(uuid.uuid1())
        audio_mp3, audio_wav = openid + "@" + random_name + ".mp3", openid + "@" + random_name + ".wav"
        logger.debug(
            "[Request Log] ip:{} src:{} filename:{} data:{}".format(ip, src, audio_mp3, str(datas)).replace("\n","").replace("\r", ""))
        upload_path = os.path.join(basepath, 'tmp/')

        if os.path.exists(upload_path) == False:
            os.makedirs(upload_path)
        f.save(upload_path + audio_mp3)


        info = asr_engine.stt(upload_path + audio_mp3)

        # 拼音纠正
        if situation != '3':
            corr, _ = asr_corrector_stat.asr_correct_text(info)
        else:
            corr = info

        # 切词
        text = rule.WordSeg(corr)

        # 修正结果
        resSets = rule.JudgeType(text, situation)

        resSets.update({"txt": info,
                        "corr": corr,
                        "seg": ' '.join(text)
                        })

        response = json.dumps(resSets, ensure_ascii=False)
        logger.debug("[Response Log] {}".format(response))
        return response

    # 语音识别API出现问题
    # add by jiangjiacheng
    except ASRServerError as e:
        logger.error("[AudioServer Error] Msg: {} Code: {}".format(e.message, e.status))
        return json.dumps(AudioServerErr(), ensure_ascii=False)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logger.error("[UnknownAudioError] upfilename: {}".format(upfilename))
        resSets = UnknownAudioError(ip, src, datas, "\t".join(traceback.format_exception(exc_type, exc_value, exc_traceback)).replace("\n","").replace("\r", ""))
        return json.dumps(resSets)


@app.route('/getRawAudio', methods=['POST'])
def getRawAudio():
    ip = request.remote_addr
    src = "GetRawAudio"
    formData = request.form
    f = request.files['file']
    upfilename = f.filename
    datas = formData
    try:

        openid = formData["userid"]
        logger.debug("[Request Log] ip:{} src:{} openid:{}".format(ip, src, openid).replace("\n", "").replace("\r", ""))
        basepath = os.path.dirname(__file__)  # 当前文件所在路径
        createTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(time.time())))

        # 语音接口
        random_name = str(uuid.uuid1())
        audio_mp3, audio_wav = openid + "@" + random_name + ".mp3", openid + "@" + random_name + ".wav"
        logger.debug(
            "[Request Log] ip:{} src:{} filename:{} data:{}".format(ip, src, audio_mp3, str(datas)).replace("\n","").replace("\r", ""))

        upload_path = os.path.join(basepath, 'tmp/')
        if os.path.exists(upload_path) == False:
            os.makedirs(upload_path)
        f.save(upload_path + audio_mp3)

        info = asr_engine.stt(upload_path + audio_mp3)

        resSets = {'code': 0,
                   'txt': info
                   }

        logger.info(resSets)
        return json.dumps(resSets, ensure_ascii=False)


    # 语音识别API出现问题
    # add by jiangjiacheng
    except ASRServerError as e:
        logger.warning("[AudioServer Error] Msg: {} Code: {}".format(e.message, e.status))
        return json.dumps(AudioServerErr(), ensure_ascii=False)

    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logger.error("[UnknownAudioError] upfilename: {}".format(upfilename))
        resSets = UnknownAudioError(ip, src, datas, "\t".join(traceback.format_exception(exc_type, exc_value, exc_traceback)).replace("\n","").replace("\r", ""))
        return json.dumps(resSets)


@app.route('/getCorrection', methods=['POST'])
def getCorrection():
    src = "getCorrection"
    datas, ip = request.json, request.remote_addr
    try:

        logger.debug("[Request Log] ip:{} src:{} datas:{}".format(ip, src, datas).replace("\n", "").replace("\r", ""))

        info = datas['txt']

        # 拼音纠正
        corr, _ = asr_corrector.asr_correct_text(info)

        resSets = {'code': 0,
                   'corr': corr
                   }
        response = json.dumps(resSets, ensure_ascii=False)
        logger.debug("[Response Log] {}".format(response))
        return response

    # general exception
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        resSets = UnknownAudioError(ip, src, datas, "\t".join(traceback.format_exception(exc_type, exc_value,exc_traceback)).replace("\n","").replace("\r", ""))
        return json.dumps(resSets)


rule = Rule()
asr_engine = BasicCloudASR(CLOUD_URL, CLOUD_APPID, CLOUD_SECRET)
asr_corrector = ASR_Corrector()
asr_corrector_stat = ASR_Corrector(fuzzy_level=ASR_Corrector_FuzzyLevel.MoreStrict, hf_dict=None, rep_rule=DICT_PRE_RULE,filter_dict=None, custom_dict=DICT_STAT)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
