from pymongo import MongoClient
import json
import random
import os
import hashlib
import urllib
import http

base_path = "db"
target_path = "db_process"
author_db_path = "/author_db.json"
paper_db_path = "/paper_db.json"
conference_db_path = "/conference_db.json"
journal_db_path = "/journal_db.json"
institution_db_path = "/institution_db.json"
exception_path = "/exception.json"
translation_path = "translation.json"


def translate(text, exception):
    with open(translation_path, "r", encoding="utf-8") as fw:
        translation = json.load(fw)
    if text in translation.keys():
        return translation[text]
    else:
        if text != "":
           exception.add(text)
        return text


def post_process():
    # 预翻译
    # pre_translate()

    # 数据处理
    with open(base_path+conference_db_path, "r", encoding="utf-8") as fw:
        data = json.load(fw)
        conferences = set([i["acronym"] for i in data])
    with open(base_path+journal_db_path, "r", encoding="utf-8") as fw:
        data = json.load(fw)
        journals = set([i["name"] for i in data])
    with open(base_path+paper_db_path, "r", encoding="utf-8") as fw:
        data = json.load(fw)
        papers = set([i["title"] for i in data])
    with open(base_path+author_db_path, "r", encoding="utf-8") as fw:
        data = json.load(fw)
        authors = {i["name"]: i["name_zh"] for i in data}
    exception = set()
    for file in [author_db_path, conference_db_path, paper_db_path, journal_db_path, institution_db_path]:
        print(file)
        count = 1
        with open(base_path+file, "r", encoding="utf-8") as fw:
            data = json.load(fw)
        result = []
        for i in data:
            print(count, end=" ")
            count += 1
            if file == author_db_path:
                i["field"] = [translate(j,exception) for j in i["field"]]
                i["affiliation"] = [translate(j,exception) for j in i["affiliation"].split("/")]
            elif file == conference_db_path:
                i["location"] = translate(i["location"],exception)
                i["category"] = [translate(j,exception) for j in i["category"].split(",")]
                for j in i["bestPaper"]:
                    if j["name"] in papers:
                        j["isSave"] = True
                    else:
                        j["isSave"] = False
                k = []
                for j in i["confRelated"]:
                    if j in conferences:
                        k.append({"acronym": j, "isSave": True})
                    else:
                        k.append({"acronym": j, "isSave": False})
                i["confRelated"] = k
                for j in i["journalRelated"]:
                    if j["name"] in journals:
                        j["isSave"] = True
                    else:
                        j["isSave"] = False
            elif file == journal_db_path:
                i["speed"] = i["speed"].replace("网友分享经验：", "")
                i["rate"] = i["rate"].replace("网友分享经验：", "")
            elif file == paper_db_path:
                k = []
                for j in i["author"]:
                    if j["name"] in authors.keys():
                        k.append(authors[j["name"]])
                i["author"]=k
            else:
                i["name_zh"] = translate(i["name"],exception)
            result.append(i)
        with open(target_path+file, "w", newline='\n', encoding="utf-8") as fw:
            fw.write(json.dumps(result, indent=1, ensure_ascii=False))
    with open(target_path+exception_path, "w", newline='\n', encoding="utf-8") as fw:
        fw.write(json.dumps(list(exception), indent=1, ensure_ascii=False))


def pre_translate():
    # 预翻译
    fromLang = []
    for file in [author_db_path, conference_db_path, paper_db_path, journal_db_path, institution_db_path]:
        with open(base_path+file, "r", encoding="utf-8") as fw:
            data = json.load(fw)
        for i in data:
            if file == author_db_path:
                if i["field"] is not None:
                    fromLang.extend(i["field"])
                if i["affiliation"] is not None:
                    fromLang.extend(i["affiliation"].split("/"))
            elif file == conference_db_path:
                if i["location"] is not None:
                    fromLang.extend(i["location"])
                if i["category"] is not None:
                    fromLang.extend(i["category"].split(","))
            elif file == institution_db_path:
                if i["name"] is not None:
                    fromLang.extend(i["name"])
    fromLang = list(set(fromLang))
    toLang = {}
    for i in fromLang:
        j = baiduTranslate(i)
        if j is not None and len(j) > 0:
            toLang[i] = j
            
    with open(translation_path, "w", newline='\n', encoding="utf-8") as fw:
            fw.write(json.dumps(toLang, indent=1, ensure_ascii=False))


def post_translate():
    # 断点续翻
    with open(translation_path, "r", encoding="utf-8") as fw:
        data=json.load(fw)
    with open(target_path+exception_path, "r", encoding="utf-8") as fw:
        fromLang = set(json.load(fw))
    
    count = 1
    for i in fromLang:
        j = baiduTranslate(i)
        if j is not None and len(j) > 0:
            data[i] = j
            print(count, end=" ")
            count += 1
    with open(translation_path, "w", newline='\n', encoding="utf-8") as fw:
        fw.write(json.dumps(data, indent=1, ensure_ascii=False))


def baiduTranslate(translate_text, flag=0):
    appid = '20210413000775885'  # 填写你的appid
    secretKey = 'DZpSeASsT2Lnbn8yQB8c'  # 填写你的密钥
    httpClient = None
    myurl = '/api/trans/vip/translate'  # 通用翻译API HTTP地址
    fromLang = 'auto'  # 原文语种

    if flag:
        toLang = 'en'  # 译文语种
    else:
        toLang = 'zh'  # 译文语种

    salt = random.randint(3276, 65536)

    sign = appid + translate_text + str(salt) + secretKey
    sign = hashlib.md5(sign.encode()).hexdigest()
    myurl = myurl + '?appid=' + appid + '&q=' + urllib.parse.quote(translate_text) + '&from=' + fromLang + \
            '&to=' + toLang + '&salt=' + str(salt) + '&sign=' + sign

    # 建立会话，返回结果
    try:
        httpClient = http.client.HTTPConnection('api.fanyi.baidu.com')
        httpClient.request('GET', myurl)
        # response是HTTPResponse对象
        response = httpClient.getresponse()
        result_all = response.read().decode("utf-8")
        result = json.loads(result_all)
        # print(result)

        # return result
        return result['trans_result'][0]['dst']

    except Exception as e:
        print(e)
    finally:
        if httpClient:
            httpClient.close()


if __name__ == "__main__":
    post_process()
    # post_translate()
