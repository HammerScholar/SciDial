# -*- coding: utf-8 -*-
# @Time : 2022-12-21 21:28
# @Author : Tian-Yi Che
# @Email : ccty@bit.edu.cn
# @File : pre_process.py

import json
from itertools import combinations
from static import *

user_template_file = "./template/user_template.json"
system_template_file = "./template/system_template.json"
action_file = "action_slot.json"
with open(action_file, "r", encoding="utf-8") as fw:
    action_details = json.load(fw)


def pre_process():
    user,system,m,n = [],[],0,0

    for intent in ["Recommend", "Request", "Confirm", "Doubt", "Browse", "Download"]:
        for domain, v in action_details[intent].items():
            fenbu = get_combinations(v)
            for slot in fenbu:
                globals().get("%s_user" % intent)(domain, slot, user)
                globals().get("%s_system" % intent)(domain, slot, system)
        print("%s user:%d system:%d" % (intent,len(user)-m,len(system)-n))
        m,n=len(user),len(system)
    print("Total user:%d system:%d" % (len(user), len(system)))
    with open(user_template_file, "w", encoding="utf-8") as fw:
        fw.write(json.dumps(user, indent=4, ensure_ascii=True))
    with open(system_template_file, "w", encoding="utf-8") as fw:
        fw.write(json.dumps(system, indent=4, ensure_ascii=False))
        

def get_combinations(value):
    result = []
    for i in range(1,len(value)+1):
        temp=combinations(value,i)
        for j in temp:
            if len(j)==0:
                continue
            if len(j)>1 and type(j[0]) is list and type(j[1]) is list:
                result.extend([[x,y]+list(j[2:]) for x in j[0] for y in j[1]])
            elif len(j)>0 and type(j[0]) is list:
                result.extend([[x]+list(j[1:]) for x in j[0]])
            else:
                result.append(list(j))
    return result
    

def template_generate(action=[], required_slot=[], requested_slot=[], description="", message=[]):
    data = {
        "action": action,
        "required_slot": required_slot,
        "requested_slot": requested_slot,
        "description": description,
        "message": message
    }
    return data


recommend_user_flag=False
def Recommend_user(domain, slot, output):
    global recommend_user_flag
    # positive
    if not recommend_user_flag:
        action=["General-Positive"]
        description="When system confirms, give positive answer"
        data=template_generate(action=action, description=description)
        output.append(data)
    # inform
    action=["%s-Inform" % domain]
    description="Given " + ','.join(slot) + "; Recommend " + domain
    data=template_generate(action=action, required_slot=slot, description=description)
    output.append(data)
    # positive+inform
    action=["%s-Inform" % domain, "General-Positive"]
    description="When choice=0 and system confirms, give positive answer then inform again"
    data=template_generate(action=action, required_slot=slot, description=description)
    output.append(data)
    # negative+inform
    action=["%s-Inform" % domain, "General-Negative"]
    description="When system confirms, find error then claim statement again"
    data=template_generate(action=action, required_slot=slot, description=description)
    output.append(data)

    if len(slot)>1:  # Only one slot can be updated or added
        return None
    # update        
    action=["%s-Update" % domain]
    description="Update " + slot[0] + "; Recommend " + domain
    data=template_generate(action=action, required_slot=slot, description=description)
    output.append(data)
    # positive+update
    action=["%s-Update" % domain, "General-Positive"]
    description="When choice=0 and system confirms, give positive answer then update a constraint to continue searching"
    data=template_generate(action=action, required_slot=slot, description=description)
    output.append(data)
    # negative+update
    action=["%s-Update" % domain, "General-Negative"]
    description="When system confirms, find error and update the wrong constraints"
    data=template_generate(action=action, required_slot=slot, description=description)
    output.append(data)
    # add       
    action=["%s-Add" % domain]
    description="Add " + slot[0] + "; Recommend " + domain
    data=template_generate(action=action, required_slot=slot, description=description)
    output.append(data)
    # negative+add
    action=["%s-Add" % domain, "General-Negative"]
    description="When choice>=4 and system confirms whether output, give negative answer and add constraints"
    data=template_generate(action=action, required_slot=slot, description=description)
    output.append(data)
    recommend_user_flag=True


recommend_system_list=[]
def Recommend_system(domain, slot, output):
    # confirm
    action=["%s-Confirm" % domain]
    description="Confirm whether constraints are " + ','.join(slot)
    data=template_generate(action=action, required_slot=slot, description=description)
    output.append(data)
    # choice=0+confirm
    action=["%s-Recommend" % domain, "%s-Confirm" % domain]
    description="cannot find eligible %s and confirm constraints" % domain
    data=template_generate(action=action, required_slot=["choice-0"]+slot, description=description)
    output.append(data)
    global recommend_system_list
    if domain not in recommend_system_list:
        # choice=0
        action=["%s-Recommend" % domain]
        description="cannot find eligible %s" % domain
        data=template_generate(action=action, required_slot=["choice-0"], description=description)
        output.append(data)
        # choice=1+return
        action=["%s-Recommend" % domain]
        description="find one eligible %s and return" % domain
        data=template_generate(action=action, required_slot=["choice-1", identify_dict[domain]], description=description)
        output.append(data)
        # choice=2~3+return
        action=["%s-Recommend" % domain]
        description="find two eligible %s and return" % domain
        data=template_generate(action=action, required_slot=["choice-2", identify_dict[domain]], description=description)
        output.append(data)
        # choice=2~3+reqmore
        action=["%s-Recommend" % domain, "%s-Reqmore" % domain]
        description="find two eligible %s and ask user for more constraints" % domain
        data=template_generate(action=action, required_slot=["choice-2"], description=description)
        output.append(data)
        # choice=50+confirm
        action=["%s-Recommend" % domain, "%s-Confirm" % domain]
        description="find 50 eligible %s and ask user whether output those" % domain
        data=template_generate(action=action, required_slot=["choice-50"], description=description)
        output.append(data)
        # choice=50+return
        action=["%s-Recommend" % domain]
        description="find 50 eligible %s and return" % domain
        data=template_generate(action=action, required_slot=["choice-50", identify_dict[domain]], description=description)
        output.append(data)
        # choice=50+reqmore
        action=["%s-Recommend" % domain, "%s-Reqmore" % domain]
        description="find 50 eligible %s and ask user for more constraints" % domain
        data=template_generate(action=action, required_slot=["choice-50"], description=description)
        output.append(data)

    if len(slot)>1:  # Only one slot can be updated or added
        return None
    # choice=0+recommend update
    action=["%s-Recommend" % domain]
    description="cannot find eligible %s and recommend a slot to update" % domain
    data=template_generate(action=action, required_slot=["choice-0", slot[0]], description=description)
    output.append(data)
    # choice=2~3+reqmore
    action=["%s-Recommend" % domain, "%s-Reqmore" % domain]
    description="find two eligible %s and require additional slot" % domain
    data=template_generate(action=action, required_slot=["choice-2"], requested_slot=slot, description=description)
    output.append(data)
     # choice=50+reqmore
    action=["%s-Recommend" % domain, "%s-Reqmore" % domain]
    description="find 50 eligible %s and require additional slot" % domain
    data=template_generate(action=action, required_slot=["choice-50"], requested_slot=slot, description=description)
    output.append(data)
    recommend_system_list.append(domain)


def get_identify(domain, slot):
    identify = [identify_dict[domain]]
    if domain=="Conference":
        for s in slot:
            if s not in Conference_no_year:
                identify = [identify_dict[domain], "year"]
                break
    return identify


def Request_user(domain, slot, output):
    if len(slot)>2 or (len(slot)==2 and slot not in two_slot_dict[domain]):  # one or two slot
        return None
    identify=get_identify(domain, slot)
    # request
    action=["%s-Request" % domain]
    description="Request detail of " + ','.join(slot)
    data=template_generate(action=action, required_slot=identify, requested_slot=slot, description=description)
    output.append(data)


def Confirm_user(domain, slot, output):
    if len(slot)>1:  # one slot
        return None
    identify=get_identify(domain, slot)
    # confirm
    action=["%s-Confirm" % domain]
    description="Confirm detail of " + ','.join(slot)
    data=template_generate(action=action, required_slot=identify+slot, description=description)
    output.append(data)


def Request_system(domain, slot, output):
    if len(slot)>2 or (len(slot)==2 and slot not in two_slot_dict[domain]):  # one or two slot
        return None
    identify=get_identify(domain, slot)
    # Inform
    action=["%s-Inform" % domain]
    description="find the value of " + ','.join(slot)
    data=template_generate(action=action, required_slot=identify+slot, description=description)
    output.append(data)
    # NoInform
    action=["%s-NoInform" % domain]
    description="there is no detail of " + ','.join(slot)
    data=template_generate(action=action, required_slot=identify+slot, description=description)
    output.append(data)

    if len(slot)>1:  # one slot
        return None
    # Recommend more
    action=["%s-Recommend" % domain, ]
    description="recommend other slot of %s" % domain
    data=template_generate(action=action, required_slot=identify, requested_slot=slot, description=description)
    output.append(data)
    

confirm_system_flag = False
def Confirm_system(domain, slot, output):
    if len(slot)>1:  # one slot
        return None
    identify=get_identify(domain, slot)
    global confirm_system_flag
    if not confirm_system_flag:
        # positive 
        action=["General-Positive"]
        description="When user confirms, give positive answer"
        data=template_generate(action=action, description=description)
        output.append(data)
    # negative+inform
    action=["General-Negative", "%s-Inform" % domain]
    description="when system confirms, give negative answer and true value"
    data=template_generate(action=action, required_slot=identify+slot, description=description)
    output.append(data)
    confirm_system_flag=True


doubt_user_flag=False
def Doubt_user(domain, slot, output):
    identify=get_identify(domain, slot)
    global doubt_user_flag
    if not doubt_user_flag:
        # doubt
        action=["General-Doubt"]
        description="Doubt to system response"
        data=template_generate(action=action, description=description)
        output.append(data)
    if len(slot)>1:  # one slot
        return None
    # doubt specific slot
    action=["%s-Doubt" % domain]
    description="Doubt specific slot to system response"
    data=template_generate(action=action, required_slot=identify+slot, description=description)
    output.append(data)
    doubt_user_flag=True


doubt_system_flag=False
def Doubt_system(domain, slot, output):
    identify=get_identify(domain, slot)
    global doubt_system_flag
    if not doubt_system_flag:
        # check
        action=["General-Check"]
        description="Receive the doubt, and we will check after"
        data=template_generate(action=action, description=description)
        output.append(data)
        # negative
        action=["General-Negative"]
        description="negative doubt from user"
        data=template_generate(action=action, description=description)
        output.append(data)
    if len(slot)>1:  # one slot
        return None
    # negative+inform
    action=["General-Negative", "%s-Inform" % domain]
    description="negative doubt from user and inform true value"
    data=template_generate(action=action, required_slot=identify+slot, description=description)
    output.append(data)
    doubt_system_flag=True


def Browse_user(domain, slot, output):
    if len(slot)>1:
        return None
    # Browse
    action=["%s-Browse" % domain]
    description="Browse the website of %s" % domain
    data=template_generate(action=action, required_slot=slot[0].split(), description=description)
    output.append(data)


Browse_system_list=[]
def Browse_system(domain, slot, output):
    if len(slot)>1:
        return None
    if domain not in Browse_system_list:
        # Browse
        action=["%s-Browse" % domain]
        description="Can browse the website of %s" % domain
        data=template_generate(action=action, required_slot=slot[0].split(), description=description)
        output.append(data)
        # NoBrowse
        action=["%s-NoBrowse" % domain]
        description="Cannot browse the website of %s" % domain
        data=template_generate(action=action, required_slot=slot[0].split(), description=description)
        output.append(data)
        Browse_system_list.append(domain)


download_user_flag=False
def Download_user(domain, slot, output):
    assert(domain=="Paper")
    if len(slot)>1:
        return None
    # Download
    action=["%s-Download" % domain]
    description="Download the paper with path"
    data=template_generate(action=action, required_slot=slot+["path"], description=description)
    output.append(data)
    # Download
    action=["%s-Download" % domain]
    description="Download the paper without path"
    data=template_generate(action=action, required_slot=slot, description=description)
    output.append(data)
    global download_user_flag
    if not download_user_flag:
        # Tell path
        action=["%s-Inform" % domain]
        description="tell path"
        data=template_generate(action=action, required_slot=["path"], description=description)
        output.append(data)
    download_user_flag=True


download_system_flag=False
def Download_system(domain, slot, output):
    assert(domain=="Paper")
    if len(slot)>1:
        return None
    global download_system_flag
    if not download_system_flag:
        # req path
        action=["%s-Reqmore" % domain]
        description="require download path"
        data=template_generate(action=action, requested_slot=["path"], description=description)
        output.append(data)
    # download
    action=["%s-Download" % domain]
    description="succeed download"
    data=template_generate(action=action, required_slot=slot+["path"], description=description)
    output.append(data)
    # nodownload
    action=["%s-NoDownload" % domain]
    description="fail to download"
    data=template_generate(action=action, required_slot=slot+["path"], description=description)
    output.append(data)
    download_system_flag=True


if __name__ == "__main__":
    pre_process()