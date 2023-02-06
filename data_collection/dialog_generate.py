import json
from msilib.schema import Error
import random
import re
from itertools import combinations
from copy import deepcopy
from static.utils import *
from threading import Thread, Lock
from dataset.mongo import select_db, find_one, random_constraints, random_value, select_error_identify, confirm_candidate

action_file_path = "static/action_slot.json"
belief_state_file_path = "static/belief_state.json"
user_template = "annotate/user_template.json"
system_template = "annotate/system_template.json"

'''
    description: turn-level update dialogue conversation and belief state
    input: {
        dialogue: [user, system, user, system]
        belief_state: [{}, metadata, {}, metadata]
        exist_slot: {"paperDue", "location"}
        system: [["Conference", "Recommend", "Choice", "1"], ["Conference", "Recommend", "acronym", "ACL"]] or None
        user: [["Conference", "Inform", "paperDue", "最近"]] or None
        revert: True means clear bs metadata and exist_slot
    }
    output: None
    function: input system and user, update system and user into dialogue, update rotate next user and system belief_state
'''
def update_bs(dialogue, belief_state, exist_slot, system, user, revert=False):
    assert (system is not None or user is not None)
    next_system_metadata = {}
    if system is None and user is not None:  # begin
        dialogue.append(user)
        belief_state.append({})  # user metadata is {}
        revert = True
    elif system is not None and user is None:  # end
        dialogue.append(system)
        return None  # without next turn metadata update
    else:
        dialogue.append(system)
        dialogue.append(user)
        next_system_metadata = deepcopy(
            belief_state[-1])  # inherit last belief_state
        belief_state.append({})

    if revert:  # revert the metadata and exist_slot
        exist_slot.clear()
        with open(belief_state_file_path, "r", encoding="utf-8") as fw:
            next_system_metadata = json.load(fw)

    # because of the list, everytime first clear then update
    for template in [system, user]:
        if not template:
            continue
        operated_slot = []
        for action in template:
            assert (len(action) == 4)
            domain, intent, slot, value = action
            if domain == "General" or intent == "Doubt":
                continue
            elif domain == "Paper" and intent == "Download":
                temp = next_system_metadata["Paper"]["download"]
            else:
                temp = next_system_metadata[domain]["semi"]
            # update metadata and exist_slot
            if slot != "?" and value != "?" and slot and value:
                # update metadata
                if slot == "Choice":
                    continue
                if slot in operated_slot:
                    temp[slot].append(value)
                else:
                    temp[slot] = [value]  # clear list
                    operated_slot.append(slot)
                # update exist_slot
                if domain == "Conference" and slot not in [
                        "acronym", "year"
                ] and slot != "Choice":
                    exist_slot.add(slot)
                elif domain != "Conference" and slot not in identify_dict.values(
                ) and slot != "Choice":
                    exist_slot.add(slot)
            # replace Confirm? into Confirm
            action[1] = action[1].replace("?", "")
    belief_state.append(next_system_metadata)
    # print("System: ", system)  # tips: this is template without replacing ?
    # print("User: ", user)
    # print("Exist_slot: ", exist_slot)


'''
    description: get undefined constraints
    input: {
        inform_slot: [["paperDue", "noticeDue", "heldDate"], "location", "category", "ccf"]
        exist_slot: {"paperDue", "location"}
        tips: ["paperDue", "noticeDue", "heldDate"] means they up to one
    }
    output: ["category", "ccf"]
    function: inform_slot - exist_slot
'''


def get_constraint_unused(inform_slot, exist_slot):
    unused_constraints = []
    for slot in inform_slot:
        if type(slot) is list:  # up to one
            temp = [i in exist_slot for i in slot]
            if True not in temp:
                unused_constraints.append(random.choice(slot))
        elif slot not in exist_slot:
            unused_constraints.append(slot)
    return unused_constraints


'''
    description: get defined constraints
    input: {
        inform_slot: [["paperDue", "noticeDue", "heldDate"], "location", "category", "ccf"]
        exist_slot: {"paperDue", "location", "finalDue"}
        tips: ["paperDue", "noticeDue", "heldDate"] means they up to one
    }
    output: ["paperDue", "location"]
    function: exist_slot - inform_slot
'''


def get_constraint_used(inform_slot, exist_slot):
    constraints = set()
    for temp in inform_slot:
        if type(temp) is list:
            constraints.update(set(temp))
        else:
            constraints.add(temp)
    used_constraints = list(exist_slot & constraints)
    return used_constraints


'''
    description: extract identifies from action
    input: {
        domain: "Conference",
        actions: [["Conference", "Inform", "acronym", "ACL"], ["Conference", "Inform", "year", "2023"], ["Conference", "Inform", "paperDue", "2023-01-20"]]
        needYear: whether need year when domain=Conference
    }
    output: {"acronym":"ACL", "year":"2023"}
'''


def extract_identify(domain, actions, needYear=False):
    identify = identify_dict[domain]
    output = dict([(slot, value) for _, _, slot, value in actions
                   if slot == identify])
    if needYear and domain == "Conference":
        output.update(
            dict([(slot, value) for _, _, slot, value in actions
                  if slot == "year"]))
        if "year" not in output:  # extract one defined year from db
            doc = find_one(domain, output)
            if doc is not None:
                output["year"] = doc["year"]
    return output


'''
    description: Recommend Conversation
    Start: the begin user utterance of dialogue
    User: user utterance of dialogue
    System: system utterance of dialogue
    Doubt: the turn focus on doubt
'''


class Recommend:

    def __init__(self,
                 domain,
                 dialogue=[],
                 belief_state=[],
                 exist_slot=set()) -> None:
        with open(action_file_path, "r", encoding="utf-8") as fw:
            action_slot = json.load(fw)
        self.inform_slot = action_slot["Recommend"][domain]
        self.random_slot = []  # random constraints with the number of 1~N
        for i in range(1, len(self.inform_slot) + 1):
            self.random_slot += list(combinations(self.inform_slot, i))
        self.domain = domain
        self.identify = identify_dict[domain]  # acronym
        self.dialogue = dialogue
        self.belief_state = belief_state
        self.exist_slot = exist_slot
        self.constraints = {}
        self.output = None
        self.result = None

    def Start(self):
        template = self.Inform()
        update_bs(self.dialogue,
                  self.belief_state,
                  self.exist_slot,
                  None,
                  template,
                  revert=True)
        self.System(template)

    '''
        description: random select 1~3 value of slot
        intent: Inform/Update/Add (not None)
        slot: paperDue (not None)
        exist_value: ["最近"]
        return: [["Conference", "Inform", "paperDue", "8月"], ["Conference", "Inform", "paperDue", "9月"]]
    '''

    def multiValue(self, intent, slot, exist_value=[]):
        chance = random.random()
        value = random_constraints(self.domain, slot, exist_value, count=3)
        assert (len(value) > 0)
        template = [[self.domain, intent, slot, value[0]]]
        if len(value) >= 2 and chance < 0.1:
            template.append([self.domain, intent, slot, value[1]])
        elif len(value) == 3 and chance > 0.99:
            template.append([self.domain, intent, slot, value[2]])
        return template

    '''
        intent: Inform
        constraints: externally define constraints
    '''

    def Inform(self, constraints=[]):
        if len(constraints
               ) == 0:  # random initial without external constraints
            slots = [
                random.choice(temp) if type(temp) is list else temp
                for temp in random.choice(self.random_slot)
            ]
        else:
            slots = constraints

        template = []
        for slot in slots:
            template.extend(self.multiValue("Inform", slot))
        return template

    # if len(exist_slot)==0, return []
    def Update(self, slot=None):
        exist_slot = get_constraint_used(self.inform_slot, self.exist_slot)
        if len(exist_slot) == 0:
            template = []
        else:
            select_slot = random.choice(
                exist_slot) if not slot else slot  # random update
            exist_value = self.belief_state[-1][
                self.domain]["semi"][select_slot]
            template = self.multiValue("Update", select_slot, exist_value)
        return template

    # if len(empty_slot)==0, return []
    def Add(self, slot=None):
        empty_slot = get_constraint_unused(self.inform_slot, self.exist_slot)
        if len(empty_slot) == 0:
            template = []
        else:
            select_slot = random.choice(
                empty_slot) if not slot else slot  # random add
            template = self.multiValue("Add", select_slot)
        return template

    '''
        intent: Confirm
        component: [("PaperDue", "最近"), ("location", "北京")]
    '''

    def Confirm(self, component):
        template = []
        for slot, value in component:
            template.append([self.domain, "Confirm", slot, value])
        # 一定概率随机修改一个值
        if random.random() < 0.2:
            index = random.randint(0, len(template) - 1)
            template[index][1] += "?"  # Confirm -> Confirm?
            slot = template[index][2]
            assert (len(self.belief_state[-1]) > 0)
            exist_value = self.belief_state[-1][self.domain]["semi"][slot]
            template[index][3] = random_constraints(self.domain,
                                                    slot,
                                                    exist_value,
                                                    count=1)[0]
        return template

    '''
        isStart: 当不是对话开始时进入此类，就置为True，表示按照给定的constraints做Inform
        constraints: 指定约束条件
    '''

    def User(self, system, isStart=False, constraints=[]):
        utterance = [[]]
        justConfirm = False  # avoid twice confirm
        toOutput = False  # when user give positive, system directly output
        if isStart:  # start recommend from other intent, receive imported constraints
            utterance = self.Inform(constraints)
        elif "Confirm" in system[0][1]:
            justConfirm = True
            temp = [i[1] == "Confirm" for i in system]
            if False in temp:  # with Confirm?
                index = temp.index(False)
                system[index][1] = "Confirm"
                utterance = self.Inform() + [[
                    "General", "Negative", None, None
                ]]
            else:
                utterance = [["General", "Positive", None, None]]
        elif system[0][1] == "Recommend":
            # inform or update or add
            inform, update, add = self.Inform(), self.Update(), self.Add()
            pre_action = [inform, inform, inform]
            if len(update) > 0:
                pre_action[1] = update
            if len(add) > 0:
                pre_action[2] = add
            # Choice
            if system[0][2] == "Choice" and system[0][3] == "0":
                if len(system) == 1:  # inform or update
                    utterance = random.choice(pre_action[:2])
                elif system[1][1] == "Recommend":  # update specific slot
                    utterance = [[
                        self.domain, "Update", system[1][2], system[1][3]
                    ]]
                elif "Confirm" in system[1][1]:
                    justConfirm = True
                    temp = [i[1] == "Confirm" for i in system[1:]]
                    if False in temp:  # update wrong slot
                        index = temp.index(False) + 1
                        system[index][1] = "Confirm"
                        utterance = self.Update(slot=system[index][2]) + [[
                            "General", "Negative", None, None
                        ]]
                    else:  # inform or update
                        utterance = random.choice(pre_action[:2]) + [[
                            "General", "Positive", None, None
                        ]]
            elif system[0][2] == "Choice" and system[0][
                    3] == "1":  # inform or update
                utterance = random.choice(pre_action[:2])
            elif system[0][2] == "Choice" and int(system[0][3]) >= 2 and int(
                    system[0][3]) <= 4:
                if system[1][1] == "Recommend" and system[1][
                        2] == self.identify:  # inform or update
                    utterance = random.choice(pre_action[0:2])
                elif system[1][1] == "Reqmore" and system[1][2] == "?":  # add
                    utterance = pre_action[2]
                elif system[1][1] == "Reqmore" and system[1][
                        2] != "?":  # add specific slot
                    utterance = self.Add(slot=system[1][2])
            elif system[0][2] == "Choice" and int(system[0][3]) > 4:
                if system[1][1] == "Confirm":
                    justConfirm = True
                    if random.random() <= 0.5:  # determine output
                        utterance = [["General", "Positive", None, None]]
                        toOutput = True
                    else:  # not output
                        utterance = pre_action[2] + [[
                            "General", "Negative", None, None
                        ]]
                elif system[1][1] == "Recommend":  # inform or update
                    utterance = random.choice(pre_action[0:2])
                elif system[1][1] == "Reqmore" and system[1][2] == "?":  # add
                    utterance = pre_action[2]
                elif system[1][1] == "Reqmore" and system[1][
                        2] != "?":  # add specific slot
                    utterance = self.Add(slot=system[1][2])

        update_bs(self.dialogue,
                  self.belief_state,
                  self.exist_slot,
                  system,
                  utterance,
                  revert=(utterance[0][1] == "Inform"))
        self.System(utterance, justConfirm, toOutput)

    '''
        justConfirm: avoid twice confirm
        toOutput: directly output
    '''

    def System(self, user, justConfirm=False, toOutput=False):
        empty_slot = get_constraint_unused(self.inform_slot, self.exist_slot)
        exist_slot = get_constraint_used(self.inform_slot, self.exist_slot)
        # inherit and update recommend conditions in multi-turn dialogue
        cx = 0
        for template in user:
            if template[0] == self.domain and template[1] == "Inform":
                if not cx:  # 重写一次
                    self.constraints = {}
                    cx = 1
                if template[2] not in self.constraints.keys():
                    self.constraints[template[2]] = [template[3]]
                else:
                    self.constraints[template[2]] += [template[3]]
            elif template[0] == self.domain and template[1] == "Update":
                if not cx:  # 重写一次
                    self.constraints[template[2]] = []
                    cx = 1
                self.constraints[template[2]] += [template[3]]
            elif template[0] == self.domain and template[1] == "Add":
                if not cx:  # 重写一次
                    assert (template[2] not in self.constraints.keys())
                    self.constraints[template[2]] = []
                    cx = 1
                self.constraints[template[2]] += [template[3]]

        choice, output = select_db[self.domain](self.constraints)
        # print("recommend", choice, self.constraints)

        if choice == 0:
            response = [[[self.domain, "Recommend", "Choice", str(choice)]]]
            if not justConfirm:
                response += [
                    [[self.domain, "Recommend", "Choice",
                      str(choice)]] + self.Confirm([(i[2], i[3])
                                                    for i in user])
                ]
            if len(exist_slot) > 0:
                slot = random.choice(exist_slot)
                exist_value = self.belief_state[-1][self.domain]["semi"][slot]
                value = random_constraints(self.domain,
                                           slot,
                                           exist_value,
                                           count=1)
                response += [[[
                    self.domain, "Recommend", "Choice",
                    str(choice)
                ], [self.domain, "Recommend", slot, value[0]]]]
        elif choice == 1:
            response = [[[self.domain, "Recommend", "Choice",
                          str(choice)],
                         [
                             self.domain, "Recommend", self.identify,
                             output[0][self.identify]
                         ]]]
        elif choice >= 2 and choice <= 4:
            response = [[[self.domain, "Recommend", "Choice",
                          str(choice)]] + [[
                              self.domain, "Recommend", self.identify,
                              value[self.identify]
                          ] for value in output]]
            if len(empty_slot) > 0:
                response += [
                    [[self.domain, "Recommend", "Choice",
                      str(choice)], [self.domain, "Reqmore", "?", "?"]],
                    [[self.domain, "Recommend", "Choice",
                      str(choice)],
                     [self.domain, "Reqmore",
                      random.choice(empty_slot), "?"]],
                ]
        else:
            if toOutput:
                response = [[[self.domain, "Recommend", "Choice",
                              str(choice)]] + [[
                                  self.domain, "Recommend", self.identify,
                                  value[self.identify]
                              ] for value in output[:3]]]
            else:
                response = [[[self.domain, "Recommend", "Choice",
                              str(choice)],
                             [self.domain, "Confirm", None, None]]]
                if len(empty_slot) > 0:
                    response += [
                        [[self.domain, "Recommend", "Choice",
                          str(choice)], [self.domain, "Reqmore", "?", "?"]],
                        [[self.domain, "Recommend", "Choice",
                          str(choice)],
                         [
                             self.domain, "Reqmore",
                             random.choice(empty_slot), "?"
                         ]],
                    ]

        if not justConfirm and not toOutput:
            response *= 2
            response.append(self.Confirm([(i[2], i[3]) for i in user]))

        respon = random.choice(response)
        # 结束条件判断
        if len(respon) > 1 and respon[1][2] == self.identify:
            # 结束、质疑、继续
            chance = random.random()
            if chance <= 0.55:  # 结束
                self.output = respon
                self.result = respon[1][3]
            elif chance <= 0.95:  # 质疑
                self.result = respon[1][3]
                if self.domain in ["Conference", "Journal"]:
                    self.Doubt(respon)
                else:
                    self.output = respon
            else:
                self.User(respon)
        else:
            self.User(respon)

    def Doubt(self, system):
        assert (len(self.constraints) > 0)
        if random.random() < 0.5:  # 系统出错时，质疑纠错
            error_slot = random.choice(list(self.constraints.keys()))
            correct_value = self.constraints[error_slot]
            error_value = random_constraints(self.domain, error_slot,
                                             correct_value, 1)
            # 修改belief_state, 将其改错
            self.belief_state[-1][
                self.domain]["semi"][error_slot] = error_value
            # 查数据库
            error_constraints = deepcopy(self.constraints)
            error_constraints[error_slot] = error_value
            choice, output = select_db[self.domain](error_constraints)
            if choice == 0:
                error_system = [[self.domain, "Recommend", "Choice", "0"]]
                utterance = [["General", "Doubt", None, None]]
            else:
                error_system = [[
                    self.domain, "Recommend", "Choice",
                    str(choice)
                ]] + [[
                    self.domain, "Recommend", self.identify,
                    value[self.identify]
                ] for value in output]
                utterance = [[
                    self.domain, "Doubt", self.identify, error_system[1][3]
                ], [self.domain, "Doubt", error_slot,
                    correct_value[0]]]  # 质疑该identify不满足某slot
            update_bs(self.dialogue, self.belief_state, self.exist_slot,
                      error_system, utterance)
            # 承认错误，重新推荐
            response = [["General", "Positive", None, None]] + system
            # correct_value = system[1][3]
            # system[1][3] = select_error_identify(self.domain, self.identify, correct_value=[i[3] for i in system[1:]])  # 改identify值
            # slot = random.choice(list(self.constraints.keys())) # 随机一个槽值作为错误槽值
            # utterance = [[self.domain, "Doubt", self.identify, system[1][3]], [self.domain, "Doubt", slot, self.constraints[slot][0]]] # 质疑该identify不满足某slot
            # update_bs(self.dialogue, self.belief_state, self.exist_slot, system, utterance)
            # copy = deepcopy(system)
            # copy[1][3] = correct_value
            # response = [["General", "Positive", None, None]] + copy # agent承认错误，并且重新推荐
        else:  # 系统没出错，瞎质疑
            error_slot = random.choice(list(self.constraints.keys()))
            utterance = [
                [["General", "Doubt", None, None]],
                # 质疑一个错误的约束条件
                [[self.domain, "Doubt", self.identify, system[1][3]],
                 [
                     self.domain, "Doubt", error_slot,
                     random_constraints(
                         self.domain,
                         error_slot,
                         exist_value=self.constraints[error_slot])[0]
                 ]]
            ]
            utterance = random.choice(utterance)
            update_bs(self.dialogue, self.belief_state, self.exist_slot,
                      system, utterance)
            response = [  # 检查一下 or 否认质疑
                [["General", "Negative", None, None]]
            ]
            if len(utterance) > 1:  # 如果质疑了一个具体的约束条件，可以告诉系统其正确槽值
                _, output = select_db[self.domain](self.constraints)
                for doc in output:
                    if doc[self.identify] == utterance[0][3]:
                        value = doc[error_slot]
                        if type(value) is list:
                            value = value[0]
                        if value == "":
                            continue
                        response += [[["General", "Negative", None, None],
                                      [
                                          self.domain, "Inform", self.identify,
                                          utterance[0][3]
                                      ],
                                      [
                                          self.domain, "Inform", error_slot,
                                          value
                                      ]]]
            response = random.choice(response)

        self.output = response


# User Request or Confirm
class Inform:

    def __init__(self,
                 domain,
                 dialogue=list(),
                 belief_state=list(),
                 exist_slot=set()):
        with open(action_file_path, "r", encoding="utf-8") as fw:
            data = json.load(fw)
        self.data = data
        self.domain = domain
        self.init_identify()
        self.dialogue = dialogue
        self.belief_state = belief_state
        self.exist_slot = exist_slot  # mentioned slot in dialogue
        self.output = None

    def init_identify(self):
        if self.domain == "Conference":
            identify = {
                identify_dict[self.domain]:
                random_value(self.domain, identify_dict[self.domain])
            }
            doc = find_one(self.domain, identify)
            if doc is not None and doc["year"] != "":
                identify["year"] = doc["year"]
            else:
                identify["year"] = "2022"
        else:
            identify = {
                identify_dict[self.domain]:
                random_value(self.domain, identify_dict[self.domain])
            }
        self.identify = identify

    def Ask(self, intent):
        inform_slot = self.data[intent][self.domain]
        empty_slot = get_constraint_unused(inform_slot, self.exist_slot)
        # two slot
        if intent == "Request":
            for i in two_slot_dict[self.domain]:
                if len(i) == 0:
                    continue
                elif i[0] in empty_slot and i[1] in empty_slot:
                    empty_slot.append(i[0] + ' ' + i[1])
        assert (len(empty_slot) > 0)
        # ASK
        select_slot = random.choice(empty_slot).split()
        if self.domain == "Conference" and select_slot[0] in Conference_no_year:
            identify = {"acronym": self.identify["acronym"]}
            utterance = [[
                self.domain, "Inform", "acronym", self.identify["acronym"]
            ]]
        else:
            identify = self.identify
            utterance = [[self.domain, "Inform", slot, value]
                         for slot, value in self.identify.items()]

        if intent == "Request":
            utterance += [[self.domain, intent, slot, "?"]
                          for slot in select_slot]
        else:
            for slot in select_slot:
                value, tag = confirm_candidate(self.domain, identify, slot)
                if tag:  # 真值
                    utterance += [[self.domain, intent, slot, value]]
                else:
                    utterance += [[self.domain, intent + "?", slot, value]]
        return utterance

    def Start(self):
        template = self.Ask("Request")
        update_bs(self.dialogue, self.belief_state, self.exist_slot, None,
                  template)
        self.System(template)

    '''
        inherit: when utterance identify isn't from system
        before: "ACL"
    
    '''

    def User(self, system, before=None):
        if random.random() <= 0.7 or self.domain == "Institution":
            intent = "Request"
        else:
            intent = "Confirm"

        inform_slot = self.data[intent][self.domain]
        empty_slot = get_constraint_unused(inform_slot, self.exist_slot)
        if len(empty_slot) == 0:
            self.output = system
            return None

        if before is not None:
            id = identify_dict[self.domain]
            action = [[self.domain, "Inform", id, before]]
            identify = extract_identify(self.domain, action, needYear=True)
            self.identify = identify
        template = self.Ask(intent)
        update_bs(self.dialogue, self.belief_state, self.exist_slot, system,
                  template)
        self.System(template)

    def System(self, user):
        response = []
        AllNoInform = True
        id = identify_dict[self.domain]
        for action in user:
            domain, intent, slot, value = action
            if slot == id:
                response += [[domain, "Inform", id, value]]
            elif domain == "Conference" and slot == "year":
                response += [[domain, "Inform", "year", value]]
            else:
                if intent == "Request":
                    doc = find_one(domain, self.identify)
                    if doc is None:
                        doc_value = []
                    elif slot == "bestPaper" and len(doc[slot]) > 0:
                        doc_value = doc[slot][0]["name"]
                        for conf in doc[slot]:
                            if conf["isSave"]:
                                doc_value = conf["name"]
                    elif slot == "confRelated" and len(doc[slot]) > 0:
                        doc_value = doc[slot][0]["acronym"]
                        for conf in doc[slot]:
                            if conf["isSave"]:
                                doc_value = conf["acronym"]
                    elif slot == "journalRelated" and len(doc[slot]) > 0:
                        doc_value = doc[slot][0]["name"]
                        for conf in doc[slot]:
                            if conf["isSave"]:
                                doc_value = conf["name"]
                    else:
                        doc_value = doc[slot]
                    # Inform or NoInform
                    if type(doc_value) is int or type(doc_value) is float:
                        if doc_value == 0:
                            response += [[self.domain, "NoInform", slot, None]]
                        else:
                            AllNoInform = False
                            response += [[
                                self.domain, "Inform", slot, doc_value
                            ]]
                    elif type(doc_value) is list:
                        if len(doc_value) == 0:
                            response += [[self.domain, "NoInform", slot, None]]
                        else:
                            AllNoInform = False
                            response += [[
                                self.domain, "Inform", slot,
                                random.choice(doc_value)
                            ]]
                    else:  # str
                        if len(doc_value) == 0:
                            response += [[self.domain, "NoInform", slot, None]]
                        else:
                            AllNoInform = False
                            response += [[
                                self.domain, "Inform", slot, doc_value
                            ]]
                elif intent == "Confirm":  # 正确的
                    response = [["General", "Positive", None, None]]
                elif intent == "Confirm?":
                    action[1] = "Confirm"
                    response = [["General", "Negative", None, None]] + response
                    doc = find_one(domain, self.identify)
                    doc_value = doc[slot] if doc is not None else []
                    # Inform or NoInform
                    if type(doc_value) is int or type(doc_value) is float:
                        if doc_value == 0:
                            response += [[self.domain, "NoInform", slot, None]]
                        else:
                            AllNoInform = False
                            response += [[
                                self.domain, "Inform", slot, doc_value
                            ]]
                    elif type(doc_value) is list:
                        if len(doc_value) == 0:
                            response += [[self.domain, "NoInform", slot, None]]
                        else:
                            AllNoInform = False
                            response += [[
                                self.domain, "Inform", slot,
                                random.choice(doc_value)
                            ]]
                    else:  # str
                        if len(doc_value) == 0:
                            response += [[self.domain, "NoInform", slot, None]]
                        else:
                            AllNoInform = False
                            response += [[
                                self.domain, "Inform", slot, doc_value
                            ]]
            if domain == "Conference" and slot not in ["acronym", "year"
                                                       ] and slot != "Choice":
                self.exist_slot.add(slot)
            elif domain != "Conference" and slot not in identify_dict.values(
            ) and slot != "Choice":
                self.exist_slot.add(slot)

        inform_slot = self.data["Request"][self.domain]
        empty_slot = get_constraint_unused(inform_slot, self.exist_slot)
        if user[-1][1] == "Request" and AllNoInform:
            if len(empty_slot) > 0 and random.random() <= 0.3:
                response.append(
                    [self.domain, "Recommend",
                     random.choice(empty_slot), "?"])
        # 结束条件判断
        if len(empty_slot) == 0:
            self.output = response
        elif random.random() <= 0.2:
            self.output = response
        else:
            self.User(response)


# Browse or Download
class Browse:

    def __init__(self,
                 domain,
                 dialogue=[],
                 belief_state=[],
                 exist_slot=set()) -> None:
        with open(action_file_path, "r", encoding="utf-8") as fw:
            data = json.load(fw)
        self.inform_slot = data["Browse"][domain]  # constraints in domain
        self.domain = domain
        self.identify = identify_dict[self.domain]
        self.dialogue = dialogue
        self.belief_state = belief_state
        self.exist_slot = exist_slot  # mentioned slot in dialogue
        self.output = None

    # identify: {"acronym": "ACL", "year": "2023"}
    def Run(self, system, identify=None):
        if not identify:
            identify = extract_identify(self.domain, system, needYear=True)
        else:
            action = [[self.domain, "Recommend", k, v] for k,v in identify.items()]
            identify = extract_identify(self.domain, action, needYear=True)
        prefix = ""
        if random.random() <= 0.5:
            prefix = "No"
        if self.domain == "Paper":
            if random.random() <= 0.4:  # Download
                user = [[self.domain, "Download", k, v]
                        for k, v in identify.items()]
                path = random.choice(["桌面", "C盘", "D盘", "E盘", "F盘"])
                if random.random() <= 0.4:  # without path
                    update_bs(self.dialogue, self.belief_state,
                              self.exist_slot, system, user)
                    output = [[self.domain, "Reqmore", "path", "?"]]
                    user = [[self.domain, "Inform", "path", path]]
                    update_bs(self.dialogue, self.belief_state,
                              self.exist_slot, output, user)
                else:
                    user.append([self.domain, "Download", "path", path])
                    update_bs(self.dialogue, self.belief_state,
                              self.exist_slot, system, user)
                output = [[self.domain, prefix + "Download", k, v]
                          for k, v in identify.items()] + [[
                              self.domain, prefix + "Download", "path", path
                          ]]
                self.output = output
                return None
        user = [[self.domain, "Browse", k, v]
                for k, v in identify.items()]
        update_bs(self.dialogue, self.belief_state, self.exist_slot, system,
                  user)
        output = [[self.domain, prefix + "Browse", k, v]
                  for k, v in identify.items()]
        self.output = output


def toMessage(template, agent=0):  # User 0; System 1
    if agent == 0:
        with open(user_template, "r", encoding="utf-8") as fw:
            data = json.load(fw)
    else:
        with open(system_template, "r", encoding="utf-8") as fw:
            data = json.load(fw)

    action = []
    required_slot = []
    requested_slot = []
    for domain, intent, slot, value in template:
        if intent == "Inform" and domain == "Paper" and slot == "title":
            pass
        elif intent == "Inform" and domain != "Paper" and slot in [
                "acronym", "name", "year"
        ]:
            pass
        elif domain + '-' + intent not in action:
            action.append(domain + '-' + intent)

        if slot != "?" and slot is not None:
            if slot == "Choice":
                if int(value) >= 2 and int(value) <= 4:
                    required_slot.append("choice-2")
                elif int(value) > 4:
                    required_slot.append("choice-50")
                else:
                    required_slot.append("choice-%s" % value)
            elif value == "?":
                if slot not in requested_slot:
                    requested_slot.append(slot)
            else:
                if slot not in required_slot:
                    required_slot.append(slot)

    if len(action) == 2 and "Positive" in action[0] and "Recommend" in action[1]:
        key1 = "General-Positive  "
        key2 = " ".join(action[1:]) + " " + " ".join(
            required_slot) + " " + " ".join(requested_slot)
        if key2 in data.keys():
            return data[key1]["description"] + "，" + data[key2][
                "description"], random.choice(
                    data[key1]["message"]) + "，" + random.choice(
                        data[key2]["message"])
        else:
            with open("exception.txt", "a", encoding="utf-8") as fw:
                fw.write(json.dumps(template) + ':\t\t' + key2 + "\n")
            return None, None
    elif len(action) == 2 and (
        ("Inform" in action[0] and "NoInform" in action[1]) or
        ("NoInform" in action[0] and "Inform" in action[1])):
        key1 = action[0] + " " + " ".join(required_slot[:-1]) + " "
        key2 = action[1] + " " + " ".join(required_slot[:-2]) + " " + required_slot[-1] + " "
        if key1 in data.keys() and key2 in data.keys():
            return data[key1]["description"] + "，" + data[key2][
                "description"], random.choice(
                    data[key1]["message"]) + "，但是" + random.choice(
                        data[key2]["message"])
        else:
            with open("exception.txt", "a", encoding="utf-8") as fw:
                fw.write(json.dumps(template) + ':\t\t' + key1 + "\n")
                fw.write(json.dumps(template) + ':\t\t' + key2 + "\n")

    key = " ".join(action) + " " + " ".join(required_slot) + " " + " ".join(
        requested_slot)

    if key in data.keys():
        return data[key]["description"], random.choice(data[key]["message"])
    else:
        with open("exception.txt", "a", encoding="utf-8") as fw:
            fw.write(
                json.dumps(template, ensure_ascii=False) + ':\t\t' + key +
                "\n")
        return None, None


def toSpan(message, action):
    slot_value = {}
    span_info = []
    for (domain, intent, slot, value) in action:
        if slot == "Choice":
            continue
        if value is not None and type(value) is str and value != "?":
            span_info += [[domain + '-' + intent, slot, value]]
            if slot in slot_value.keys():
                slot_value[slot].append(value)
            else:
                slot_value[slot] = [value]
    for slot, value in slot_value.items():
        temp = [
            x + "和" + y for x in annotate_db[slot] for y in annotate_db[slot]
        ] + annotate_db[slot]
        pattern = re.compile('|'.join(temp))
        # 这步会报错, 是因为论文title在爬虫过程中存在噪音，导致re解析错误
        message = re.sub(pattern, '和'.join(value), message)
    for span in span_info:
        span.append(message.find(span[2]))
        span.append(message.find(span[2]) + len(span[2]) - 1)
    return message, span_info


# count = 1
# count = 17001
count = 34001
lock = Lock()


def toDialogue(dialogue, belief_state, prefix):
    a, b, c = 'F', 'F', 'F'
    for bs in belief_state[1::2]:
        for _, i in bs.items():
            for _, j in i.items():
                for _, v in j.items():
                    if len(v) >= 2:
                        a = "T"
    for i in dialogue[2::2]:
        if i[-1][1] == "Inform":  # revert
            b = "T"
        if i[0][1] == "Doubt":  # doubt
            c = "T"

    with lock:
        global count
        id = prefix + a + b + c + '_%06d' % count
        count += 1
        # file_path = "z_test.json"
        file_path = "new_data/%s.json" % (id)
        print(count, end=" ")

    log = []
    description = []
    for i in range(len(dialogue)):
        da = {}
        des, message = toMessage(dialogue[i], agent=i % 2)
        for j in dialogue[i]:
            domain, intent, slot, value = j
            # 特殊处理
            if slot == "OA":
                if value is None:
                    pass
                elif "不可以" in value or "禁止" in value:
                    j[3] = False
                else:
                    j[3] = True

            if j[3] is not None and type(j[3]) not in (str,bool,int,float):
                print(dialogue[i])
                raise(Error)
            
            if intent == "Update" or intent == "Add":
                intent = "Inform"
            action = domain + '-' + intent
            if action in da.keys():
                da[action].append(j[2:])
            else:
                da[action] = [j[2:]]
        description.append(des)
        if message is None:
            return None
        message, span_info = toSpan(message, dialogue[i])
        turn = {
            "text": message,
            "metadata": belief_state[i],
            "dialog_act": da,
            "span_info": span_info
        }
        log.append(turn)
    goal = deepcopy(belief_state[-1])
    goal["description"] = description[::2]
    result = {id: {"goal": goal, "log": log}}
    with open(file_path, "w", encoding="utf-8") as fw:
        json.dump(result, fw, indent=4, ensure_ascii=False)


def thread_1():
    print("Start Thread 1", end="\n")
    # template 1: just Recommend
    domain_seed = ["Conference"] * 8 + ["Paper"] * 3 + ["Journal"
                                                        ] * 2 + ["Author"] * 1
    for i in range(2000):
        try:
            domain = random.choice(domain_seed)
            Dial = Recommend(domain,
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                      Dial.output, None)
            toDialogue(Dial.dialogue, Dial.belief_state, "S")
            del domain, Dial
        except Exception as e:
            print("模板1出错", e)
    # template 2: Recommend, then Browse
    domain_seed = ["Conference"] * 8 + ["Paper"] * 3 + ["Journal"] * 2
    for i in range(1000):
        try:
            domain = random.choice(domain_seed)
            Dial = Recommend(domain,
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Browse(domain, Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.Run(Dial.output, identify={Dial.identify: Dial.result})
            update_bs(Next.dialogue, Next.belief_state, Next.exist_slot,
                      Next.output, None)
            toDialogue(Next.dialogue, Next.belief_state, "S")
            del domain, Dial, Next
        except Exception as e:
            print("模板2出错", e)
    # template 3: just Request
    domain_seed = ["Conference"] * 8 + ["Paper"] * 3 + ["Journal"
                                                        ] * 2 + ["Author"] * 1
    for i in range(1000):
        try:
            domain = random.choice(domain_seed)
            Dial = Inform(domain,
                          dialogue=[],
                          belief_state=[],
                          exist_slot=set())
            Dial.Start()
            update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                      Dial.output, None)
            toDialogue(Dial.dialogue, Dial.belief_state, "S")
            del domain, Dial
        except Exception as e:
            print("模板3出错", e)
    # template 4: Request + Browse
    domain_seed = ["Conference"] * 8 + ["Paper"] * 3 + ["Journal"] * 2
    for i in range(1000):
        try:
            domain = random.choice(domain_seed)
            Dial = Inform(domain,
                          dialogue=[],
                          belief_state=[],
                          exist_slot=set())
            Dial.Start()
            Next = Browse(domain, Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.Run(Dial.output, Dial.identify)
            update_bs(Next.dialogue, Next.belief_state, Next.exist_slot,
                      Next.output, None)
            toDialogue(Next.dialogue, Next.belief_state, "S")
            del domain, Dial, Next
        except Exception as e:
            print("模板4出错", e)
    print("End Thread 1")


def thread_2():
    print("Start Thread 2", end="\n")
    # template 5: Recommend, find then request
    domain_seed = ["Conference"] * 8 + ["Paper"] * 3 + ["Journal"
                                                        ] * 2 + ["Author"] * 1
    for i in range(3000):
        try:
            domain = random.choice(domain_seed)
            Dial = Recommend(domain,
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Inform(domain, Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.User(Dial.output, before=Dial.result)
            update_bs(Next.dialogue, Next.belief_state, Next.exist_slot,
                      Next.output, None)
            toDialogue(Next.dialogue, Next.belief_state, "S")
            del domain, Dial, Next
        except Exception as e:
            print("模板5出错", e)
    # template 6: Recommend, find then request, suit then browse
    domain_seed = ["Conference"] * 8 + ["Paper"] * 3 + ["Journal"] * 2
    for i in range(2000):
        try:
            domain = random.choice(domain_seed)
            Dial = Recommend(domain,
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Inform(domain, Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.User(Dial.output, before=Dial.result)
            Dial = Browse(domain, Next.dialogue, Next.belief_state,
                          Next.exist_slot)
            Dial.Run(Next.output, Next.identify)
            update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                      Dial.output, None)
            toDialogue(Dial.dialogue, Dial.belief_state, "S")
            del domain, Dial, Next
        except Exception as e:
            print("模板6出错", e)
    # template 7: Recommend, find then request, suitless then recommend
    domain_seed = ["Conference"] * 8 + ["Paper"] * 3 + ["Journal"
                                                        ] * 2 + ["Author"] * 1
    for i in range(3000):
        try:
            domain = random.choice(domain_seed)
            Dial = Recommend(domain,
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Inform(domain, Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.User(Dial.output, before=Dial.result)
            Dial = Recommend(domain, Next.dialogue, Next.belief_state,
                             Next.exist_slot)
            Dial.User(Next.output, isStart=True)
            update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                      Dial.output, None)
            toDialogue(Dial.dialogue, Dial.belief_state, "S")
            del domain, Dial, Next
        except Exception as e:
            print("模板7出错", e)
    print("End Thread 2")


def thread_3():
    print("Start Thread 3", end="\n")
    # template 8: Conference/Journal Recommend, Paper Recommend
    domain_seed = ["Conference"] * 8 + ["Journal"]
    for i in range(2000):
        try:
            domain = random.choice(domain_seed)
            Next = Recommend(domain,
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Next.Start()
            Dial = Recommend("Paper", Next.dialogue, Next.belief_state,
                             Next.exist_slot)
            Dial.User(Next.output, isStart=True, constraints=["venue"])
            update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                      Dial.output, None)
            toDialogue(Dial.dialogue, Dial.belief_state, "M")
            del domain, Dial, Next
        except Exception as e:
            print("模板8出错", e)
    # template 9: Conference/Journal Recommend, Conferece/Journal Request, Paper Recommend
    domain_seed = ["Conference"] * 8 + ["Journal"]
    for i in range(2000):
        try:
            domain = random.choice(domain_seed)
            Dial = Recommend(domain,
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Inform(domain, Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.User(Dial.output, before=Dial.result)
            Dial = Recommend("Paper", Next.dialogue, Next.belief_state,
                             Next.exist_slot)
            Dial.User(Next.output, isStart=True, constraints=["venue"])
            update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                      Dial.output, None)
            toDialogue(Dial.dialogue, Dial.belief_state, "M")
            del domain, Dial, Next
        except Exception as e:
            print("模板9出错", e)
    # template 10: Conference Recommend, Conferece Request 最佳论文, Paper Request
    for i in range(3000):
        try:
            Dial = Recommend("Conference",
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Inform("Conference", Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.User(Dial.output, before=Dial.result)
            if Next.output[0][1] == "Inform" and Next.output[0][
                    2] == "bestPaper":
                Dial = Inform("Paper", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
            del Dial, Next
        except Exception as e:
            print("模板10出错", e)
    # template 11: Conference Recommend, Conferece Request 相似会议, Conferece Request
    for i in range(3000):
        try:
            Dial = Recommend("Conference",
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Inform("Conference", Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.User(Dial.output, before=Dial.result)
            if Next.output[0][1] == "Inform" and Next.output[0][
                    2] == "confRelated":
                Dial = Inform("Conference", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "S")
            del Dial, Next
        except Exception as e:
            print("模板11出错", e)
    # template 12: Conference Recommend, Conferece Request 相似期刊, Journal Request
    for i in range(3000):
        try:
            Dial = Recommend("Conference",
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Inform("Conference", Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.User(Dial.output, before=Dial.result)
            if Next.output[0][1] == "Inform" and Next.output[0][
                    2] == "journalRelated":
                Dial = Inform("Journal", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
            del Dial, Next
        except Exception as e:
            print("模板12出错", e)
    print("End Thread 3")


def thread_4():
    print("Start Thread 4", end="\n")
    # template 13: Conferece Request 最佳论文, Paper Request
    for i in range(3000):
        try:
            Next = Inform("Conference",
                          dialogue=[],
                          belief_state=[],
                          exist_slot=set())
            Next.Start()
            if Next.output[0][1] == "Inform" and Next.output[0][
                    2] == "bestPaper":
                Dial = Inform("Paper", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
                del Dial
            del Next
        except Exception as e:
            print("模板13出错", e)
    # template 14: Conferece Request 相似会议, Conferece Request
    for i in range(3000):
        try:
            Next = Inform("Conference",
                          dialogue=[],
                          belief_state=[],
                          exist_slot=set())
            Next.Start()
            if Next.output[0][1] == "Inform" and Next.output[0][
                    2] == "confRelated":
                Dial = Inform("Conference", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "S")
                del Dial
            del Next
        except Exception as e:
            print("模板14出错", e)
    # template 15: Conferece Request 相似期刊, Journal Request
    for i in range(3000):
        try:
            Next = Inform("Conference",
                          dialogue=[],
                          belief_state=[],
                          exist_slot=set())
            Next.Start()
            if Next.output[0][1] == "Inform" and Next.output[0][
                    2] == "journalRelated":
                Dial = Inform("Journal", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
                del Dial
            del Next
        except Exception as e:
            print("模板15出错", e)
    # template 16: Paper Recommend, Paper Request 作者, Author Request
    for i in range(3000):
        try:
            Dial = Recommend("Paper",
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Inform("Paper", Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.User(Dial.output, before=Dial.result)
            if Next.output[0][1] == "Inform" and Next.output[0][2] == "author":
                Dial = Inform("Author", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
            del Dial, Next
        except Exception as e:
            print("模板16出错", e)
    # template 17: Paper Recommend, Paper Request 机构, Institution Request
    for i in range(3000):
        try:
            Dial = Recommend("Paper",
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Inform("Paper", Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.User(Dial.output, before=Dial.result)
            if Next.output[0][1] == "Inform" and Next.output[0][
                    2] == "institution":
                Dial = Inform("Institution", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
            del Dial, Next
        except Exception as e:
            print("模板17出错", e)
    # template 18: Paper Request 作者, Author Request
    for i in range(3000):
        try:
            Next = Inform("Paper",
                          dialogue=[],
                          belief_state=[],
                          exist_slot=set())
            Next.Start()
            if Next.output[0][1] == "Inform" and Next.output[0][2] == "author":
                Dial = Inform("Author", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
                del Dial
            del Next
        except Exception as e:
            print("模板18出错", e)
    print("End Thread 4")


def thread_5():
    print("Start Thread 5", end="\n")
    # template 19: Paper Request 机构, Institution Request
    for i in range(3000):
        try:
            Next = Inform("Paper",
                          dialogue=[],
                          belief_state=[],
                          exist_slot=set())
            Next.Start()
            if Next.output[0][1] == "Inform" and Next.output[0][
                    2] == "institution":
                Dial = Inform("Institution", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
                del Dial
            del Next
        except Exception as e:
            print("模板19出错", e)
    # template 20: Author Recommend, Author Request 机构, Institution Request
    for i in range(2000):
        try:
            Dial = Recommend("Author",
                             dialogue=[],
                             belief_state=[],
                             exist_slot=set())
            Dial.Start()
            Next = Inform("Author", Dial.dialogue, Dial.belief_state,
                          Dial.exist_slot)
            Next.User(Dial.output, before=Dial.result)
            if Next.output[0][1] == "Inform" and Next.output[0][
                    2] == "institution":
                Dial = Inform("Institution", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
        except Exception as e:
            print("模板20出错", e)
    # template 21: Author Request 机构, Institution Request
    for i in range(2000):
        try:
            Next = Inform("Author",
                          dialogue=[],
                          belief_state=[],
                          exist_slot=set())
            Next.Start()
            if Next.output[0][1] == "Inform" and Next.output[0][
                    2] == "institution":
                Dial = Inform("Institution", Next.dialogue, Next.belief_state,
                              Next.exist_slot)
                Dial.User(Next.output)
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
                del Dial
            del Next
        except Exception as e:
            print("模板21出错", e)
    # template 22: Conference/Journal/Author Request 领域, Conference/Journal/Author Recommend
    domain_seed = ["Conference"] * 8 + ["Journal"] * 2 + ["Author"] * 1
    for i in range(3000):
        try:
            domain = random.choice(domain_seed)
            others = {"Conference", "Journal", "Author"} - {domain}
            Next = Inform(domain,
                          dialogue=[],
                          belief_state=[],
                          exist_slot=set())
            Next.Start()
            if Next.output[0][1] == "Inform" and (
                    Next.output[0][2] == "category"
                    or Next.output[0][2] == "field"):
                x = random.choice(list(others))
                Dial = Recommend(x, Next.dialogue, Next.belief_state,
                                 Next.exist_slot)
                if x == "Author":
                    Dial.User(Next.output, isStart=True, constraints=["field"])
                else:
                    Dial.User(Next.output,
                              isStart=True,
                              constraints=["category"])
                update_bs(Dial.dialogue, Dial.belief_state, Dial.exist_slot,
                          Dial.output, None)
                toDialogue(Dial.dialogue, Dial.belief_state, "M")
                del Dial
            del Next
        except Exception as e:
            print("模板22出错", e)
    print("End Thread 5")


def main():
    # create
    t1 = Thread(target=thread_1)
    t2 = Thread(target=thread_2)
    t3 = Thread(target=thread_3)
    t4 = Thread(target=thread_4)
    t5 = Thread(target=thread_5)
    # start
    t1.start()
    t2.start()
    t3.start()
    # t4.start()
    # t5.start()
    # free
    t1.join()
    t2.join()
    t3.join()
    # t4.join()
    # t5.join()


if __name__ == '__main__':
    main()
