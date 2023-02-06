import pymongo
import json
import re
import random
import sys
# sys.path.append('..')
from static.utils import *

class Mongo:
    def __init__(self, url="mongodb://localhost:27017/", database="sciDial"):
        myClient = pymongo.MongoClient(url)
        self.db = myClient[database]
    
    # return all result
    def find(self, collection, filter={}, projection={"_id":0}):
        col = self.db[collection]
        return col.find(filter, projection)
    
    # return one result
    def find_one(self, collection, filter={}, projection={"_id":0}):
        col = self.db[collection]
        return col.find_one(filter, projection)


# database
mongodb = Mongo()
# date contraints condidate
with open("constraints/date.json", "r", encoding="utf-8") as fw:
    times=json.load(fw)
time_dict = {}
for i in times:
    for message in i[2:]:
        time_dict[message] = i[:2]


'''
    description: select conference
    constraints: {"PaperDue": ["最近"], "location": ["葡萄牙"]}
'''
def select_conference(constraints):
    filter = {}
    for slot,values in constraints.items():
        if "Due" in slot or "Date" in slot: # 时间
            temp = []
            # 从value拿到start和end
            for value in values:
                start, end = time_dict[value]
                start = "%d-%02d-%02d" % (start[0], start[1], start[2])
                end = "%d-%02d-%02d" % (end[0], end[1], end[2])
                temp.append({slot:{"$gte": start, "$lte": end}})
            filter["$or"] = temp
        elif slot=="ccf":
            temp = []
            for value in values:
                value=re.sub(r"ccf| |-|类","",value.lower())
                if "以上" in value:
                    if "b" in value:
                        temp += ["a","b"]
                    else:
                        temp += ["a","b","c"]
                elif "以下" in value:
                    if "b" in value:
                        temp += ["b","c"]
                    else:
                        temp += ["a","b","c"]
                else:
                    temp.append(value)
            filter["ccf"] = {"$in": list(set(temp))}
        else: # location or category
            filter[slot] = {"$in": [re.compile(value) for value in values]}
    output = list(mongodb.find("conference", filter))
    # print("filter:", filter)
    # print("output:", output)
    return len(output), output


'''
    description: select paper
    constraints: {"author": ["王琪"], "year": ["2005"]}
'''
def select_paper(constraints):
    filter = {}
    for slot,values in constraints.items():
        if slot == "year": # year
            temp = []
            for value in values:
                value=value.replace("年","")
                if value=="今":
                    value="2022"
                elif value=="去":
                    value="2021"
                elif value=="前":
                    value="2020"
                temp.append(value)
            filter["year"] = {"$in": temp}
        elif slot=="venue": # venue
            filter[slot] = {"$in": values}
        else: # author or institution
            filter[slot] = {"$in": [re.compile(value) for value in values]}
    output = list(mongodb.find("paper", filter))
    # print("filter:", filter)
    # print("output:", output)
    return len(output), output


'''
    description: select journal
    constraints: {"IF": ["IF影响因子>10"], "category": ["人工智能"]}
'''
def select_journal(constraints):
    filter = {}
    for slot,values in constraints.items():
        if slot=="IF" or slot=="h_index": # IF or h_index
            temp = []
            for value in values:
                floor = int(re.split(r'>|大于',value)[-1])
                temp.append({slot:{"$gt": floor}})
            filter["$or"] = temp
        elif slot=="ccf": # ccf
            temp = []
            for value in values:
                value=re.sub(r"ccf| |-|类","",value.lower())
                if "以上" in value:
                    if "b" in value:
                        temp += ["a","b"]
                    else:
                        temp += ["a","b","c"]
                elif "以下" in value:
                    if "b" in value:
                        temp += ["b","c"]
                    else:
                        temp += ["a","b","c"]
                else:
                    temp.append(value)
            filter["ccf"] = {"$in": list(set(temp))}
        elif slot=="sci": # sci
            temp = [re.sub(r"sci| ","",value.lower()) for value in values]
            filter["sci"] = {"$in": list(set(temp))}
        else: # category
            filter[slot] = {"$in": [re.compile(value) for value in values]}
    output = list(mongodb.find("journal", filter))
    # print("filter:", filter)
    # print("output:", output)
    return len(output), output


def select_author(constraints):
    filter = {}
    for slot,values in constraints.items():
        # position
        if slot == "position":
            filter["position_zh"] = {"$in": values}
        else: # field or institution
            filter[slot] = {"$in": values}
    output = list(mongodb.find("author", filter))
    # print("filter:", filter)
    # print("output:", output)
    return len(output), output


select_db = {
    "Conference": select_conference,
    "Paper": select_paper,
    "Journal": select_journal,
    "Author": select_author
}


'''
    description: Given identify, find one doc
    domain: Conference
    identify: {"acronym":"ACL", "year":"2023"}
'''
def find_one(domain, identify):
    # if domain == "Author":
    #     identify = {"name_zh": identify["name"]}
    output = mongodb.find_one(collection=domain.lower(), filter=identify)
    if output is None:
        a = 1

    return output


'''
    description: random select value of constraints
    domain: Conference (not None)
    constraints: paperDue (not None)
    exist_value: ["最近"]
    count: 返回几个值
    return: ["7月","8月","9月"]
    tips: 
'''
def random_constraints(domain, constraints, exist_value=[], count=1):
    # the whole candidates
    if "Due" in constraints or "Date" in constraints: # Date
        with open("constraints/date.json", "r", encoding="utf-8") as fw:
            data=json.load(fw)
        values = [message for time in data for message in time[2:]]
    else:
        with open("constraints/constraints.json", "r", encoding="utf-8") as fw:
            data=json.load(fw)
        values = data[domain][constraints]
    # values - exist_value
    candidate_values = []
    if constraints in ["ccf", "sci"]:  # x is list
        for x in values:
            temp = [y in exist_value for y in x]
            if True not in temp:
                candidate_values.append(random.choice(x))
    else:
        candidate_values = list(set(values) - set(exist_value))
    if len(candidate_values)==0:
        print(domain,constraints,exist_value,values)
    assert(len(candidate_values)>0)
    if count==2 and len(candidate_values)==1:
        output = candidate_values
    elif count==3 and len(candidate_values)<=2:
        output = candidate_values
    else:
        output = random.sample(candidate_values, count)
    return output


'''
    description: 随机取一些exist_value以外的值
    domain: Conference
    slot: paperDue
    exist_value: 2022-08-30
'''
def random_value(domain, slot, exist_value=list()):
    filter = {slot: {"$nin": exist_value}}
    projection = {"_id": 0, slot: 1}
    output = mongodb.find(domain.lower(), filter, projection)
    for doc in output:
        possible_value = doc[slot]
        if type(possible_value) is float or type(possible_value) is int:
            if possible_value == 0:
                continue
            else:
                return possible_value
        else: # list or str
            if len(possible_value) == 0:
                continue
            elif type(possible_value) is str:
                return possible_value
            else: # list
                for v in possible_value:
                    if len(v)>0: # avoid ""
                        return v


'''
    description: User Confirm, give value of slot
    domain: Conference
    identify: {"acronym":"ACL", "year":"2023"}
    slot: paperDue
'''
def confirm_candidate(domain, identify, slot):
    doc = find_one(domain, identify)
    assert(doc is not None)
    value = doc[slot]
    if type(value) is float or type(value) is int:
        if value == 0: # 没有该值，返回假值
            output = [random_value(domain, slot), False]
        else:
            output = [[value, True], [random_value(domain, slot, exist_value=[value]), False]]
            output = random.choice(output)
    else: # list or str
        if len(value) == 0: # 没有该值，返回假值
            output = [random_value(domain, slot), False]
        elif type(value) is str:
            output = [[value, True], [random_value(domain, slot, exist_value=[value]), False]]
            output = random.choice(output)
        else: # list
            output = [[random.choice(value), True], [random_value(domain, slot, exist_value=value), False]]
            output = random.choice(output)
    return output


'''
    desciption: select one identify != correct_value
    domain: Conference
    slot: acronym
    correct_value: ACL
'''
def select_error_identify(domain, slot, correct_value):
    filter = {slot: {"$ne": correct_value}}
    projection = {"_id": 0, slot: 1}
    output = mongodb.find_one(domain.lower(), filter, projection)
    assert(output is not None)

    return output[slot]