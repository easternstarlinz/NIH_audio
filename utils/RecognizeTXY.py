# ========================================================
#   Copyright (C) 2018 All rights reserved.
#   
#   filename : Recognize.py 
#   author   : wangkai
#   date     : 2019-09-17
#   desc     : 本产品调用腾讯云语音识别，若返回服务器错误，错误码
# ======================================================== 

import time, sys, os, json
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.asr.v20190614 import asr_client, models
import base64

DEBUG = True

# for import purpose
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from instance import *


# 语音识别API错误
# add by jiangjiacheng
class ASRServerError(Exception):
    def __init__(self, message, status):
        super().__init__(message, status)
        self.message = message
        self.status = status


class BaseASR(object):
    ext2idx = {'mp3': '1', 'wav': '2'}

    def __init__(self, api_url, app_id, app_key):
        self.api_url = api_url
        self.app_id = app_id
        self.app_key = app_key

    def stt(self, audio_file):
        raise Exception("Unimplemented!")


class BasicCloudASR(BaseASR):
    """ Online ASR from Tencent
    https://ai.qq.com/doc/aaiasr.shtml
    """

    def __init__(self, api_url, app_id, app_key):
        super(BasicCloudASR, self).__init__(api_url, app_id, app_key)

    def stt(self, audio_file):
        try :
            fwave = open(audio_file, mode='rb')
            data = fwave.read()
            dataLen = len(data)
            base64Wav = base64.b64encode(data)
            fwave.close()


            params = '{"ProjectId":0,"SubServiceType":2,"EngSerViceType":"16k","SourceType":1,"VoiceFormat":"mp3","UsrAudioKey":"session-123", ' + '"Data":"' + str(base64Wav, 'utf-8') + '", "DataLen":' + str(dataLen) + '}'

            cred = credential.Credential(self.app_id, self.app_key)
            httpProfile = HttpProfile()
            httpProfile.endpoint = self.api_url

            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            client = asr_client.AsrClient(cred, "ap-chengdu", clientProfile)

            req = models.SentenceRecognitionRequest()

            req.from_json_string(params)
            res = client.SentenceRecognition(req)
            resp = json.loads(res.to_json_string())

            return resp['Result']
        except TencentCloudSDKException as err:
            ASRServerError(err, "404")



