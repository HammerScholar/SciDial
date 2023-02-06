# -*- coding: utf-8 -*-
# @Time : 2022-12-22 13:15
# @Author : Tian-Yi Che
# @Email : ccty@bit.edu.cn
# @File : post_process.py

import json
from itertools import product

user_template_file = "./template/user_template.json"
system_template_file = "./template/system_template.json"

# Recommend 300 300 221
# Request 47 49 141
# Confirm 22 22 23
# Doubt 15 16 17
# Browse 6 6 6
# Download 2 5 5
def annotate_process():
    with open(user_template_file, "r", encoding="utf-8") as fw:
        user=json.load(fw)
    with open(system_template_file, "r", encoding="utf-8") as fw:
        system=json.load(fw)
    diag = data_util()
    # 300 349 371 387 393 398 
    # 221 362 385 402 408 413
    tList = [
        ("Recommend", user[:300], system[:221]),
        # ("Request", user[300:349], system[221:362]),
        # ("Confirm", user[349:371], system[362:385]),
        # ("Doubt", user[371:387], system[385:402]),
        # ("Browse", user[387:393], system[402:408]),
        # ("Download", user[393:], system[408:]),
    ]
    positive = ["嗯嗯是的呢", "是的，我问的就是这个问题", "没错", "是的呢", "是的", "嗯嗯", "是这个问题", "没错，就是这个问题", "你理解的没错", "没有问题", "你说的没错，就是这个问题", "对的", "没错，帮我找一下这个问题的答案吧", "确定"]
    negative = ["不对", "不对吧", "不是", "不是吧","错的吧","呃不对吧","呃不是"]

    for intent,i,j in tList:
        count = 0
        for template in i:
            if len(template["action"])==1 and template["action"][0]=="General-Positive":
                template["message"] = positive
            elif len(template["action"])==1 and template["action"][0]=="General-Negative":
                template["message"] = negative
            elif len(template["action"])==2 and template["action"][1]=="General-Positive":
                key = template["action"][0] + " " + " ".join(template["required_slot"]) + " " + " ".join(template["requested_slot"])
                if key in diag.keys():
                    template["message"] = [i+"，"+j for i,j in product(positive, diag[key]["message"])]
            elif len(template["action"])==2 and template["action"][1]=="General-Negative":
                key = template["action"][0] + " " + " ".join(template["required_slot"]) + " " + " ".join(template["requested_slot"])
                if key in diag.keys():
                    template["message"] = [i+"，"+j for i,j in product(negative, diag[key]["message"])]
            else:
                key = " ".join(template["action"]) + " " + " ".join(template["required_slot"]) + " " + " ".join(template["requested_slot"])
                if key in diag.keys():
                    template["message"] = diag[key]["message"]

            if len(template["message"])>0:
                    count += 1
        print(intent, count)
        with open("annotate/%s_user.json" % intent, "w", encoding="utf-8") as fw:
            json.dump(i, fw, indent=4, ensure_ascii=False)
        
        with open("annotate/%s_system.json" % intent, "w", encoding="utf-8") as fw:
            json.dump(j, fw, indent=4, ensure_ascii=False)


def data_util():
    data=[]
    result = {}
    for file in ["UC.json", "UP.json", "UJ.json", "UA.json", "UI.json"]:
        with open("before/"+file, "r", encoding="utf-8") as fw:
            data.extend(json.load(fw))
    for template in data:
        key = " ".join(template["action"]) + " " + " ".join(template["required_slot"]) + " " + " ".join(template["requested_slot"])
        if "增加" in template["description"]:
            key=key.replace("Inform", "Add")
        elif "修改" in template["description"]:
            key=key.replace("Inform", "Update")
        result[key]=template
    return result


def post_process():
    pass

if __name__ == "__main__":
    annotate_process()
    post_process()