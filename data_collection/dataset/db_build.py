from pymongo import MongoClient
import json
import random
import os

DataHammer = MongoClient("mongodb://crawler:HammerScholarCrawler@hammerscholar-pub.mongodb.zhangbei.rds.aliyuncs.com:3717,hammerscholarsecondary-pub.mongodb.zhangbei.rds.aliyuncs.com:3717/HammerScholar?replicaSet=mgset-505729903")
HammerScholar = DataHammer.HammerScholar
# author = HammerScholar.venue_researcher_test
author = HammerScholar.researcher
paper = HammerScholar.clean_papers
detail = HammerScholar.detail

base_path = "db"
author_db_path = base_path + "/author_db.json"
paper_db_path = base_path + "/paper_db.json"
conference_db_path = base_path + "/conference_db.json"
journal_db_path = base_path + "/journal_db.json"
institution_db_path = base_path + "/institution_db.json"
statistic_path = base_path + "/statistic.txt"

def extractAuthor():
    # 抽取作者
    projection = {
        "_id": 0,
        "name": 1,
        "name_zh": 1,
        "tags": 1,
        "tags_score": 1,
        "indices_citations": 1,
        "indices_hindex": 1,
        "indices_pubs": 1,
        "profile_affiliation": 1,
        "profile_position": 1,
        "profile_position_zh": 1
    }
    result = []
    for i in author.find(projection=projection):
        # if not ("name" in i.keys() and i["name"] is not None and len(i["name"])>0 and "name_zh" in i.keys() and i["name_zh"] is not None and len(i["name_zh"])>0):
        #     continue
        i.update({
            "field": i.pop("tags"),
            "field_score": i.pop("tags_score"),
            "affiliation": i.pop("profile_affiliation"),
            "position": i.pop("profile_position"),
            "position_zh": i.pop("profile_position_zh"),
            "citations": i.pop("indices_citations"),
            "h_index": i.pop("indices_hindex"),
            "pubs": i.pop("indices_pubs"),
        })
        result.append(i)

    print("Author size: %d" % len(result))
    # with open(author_db_path, "w", newline='\n', encoding="utf-8") as fw:
    #     fw.write(json.dumps(result, indent=1, ensure_ascii=False))
    Authors = [i["name"] for i in result if i["name"] != ""]
    Institutions = []
    for i in result:
        if i["affiliation"]is not None and len(i["affiliation"]) > 0:
            Institutions.extend([j.strip() for j in i["affiliation"].split("/")])
    Institutions = list(set(Institutions))
    print("Institution size: %d" % len(Institutions))

    return Authors, Institutions


def extractPaper(Authors):
    # 抽取论文
    projection = {
        "_id": 0,
        "*title": 1,
        "*abstract": 1,
        "abstract": 1,
        "*year": 1,
        "*type": 1,
        "*pdf": 1,
        "*doi": 1,
        "*venue": 1,
        "*authors.name": 1,
        "blog_urls": 1
    }
    result = []
    for i in paper.find({"*authors.name": {"$in": Authors}}, projection=projection):
        i.update({
            "title": i.pop("*title"),
            "year": i.pop("*year"),
            "type": i.pop("*type"),
            "pdf": i.pop("*pdf"),
            "doi": i.pop("*doi"),
            "venue": i.pop("*venue"),
            "author": i.pop("*authors")
        })
        if "blog_urls" not in i.keys():
            i["blog_urls"] = []
        i["permission"] = random.choice([True, False])
        result.append(i)
    # 数据库字段不统一，懒得让他们改了
    for i in result:
        if "*abstract" in i.keys():
            i.update({"abstract": i.pop("*abstract")})


    print("Paper size: %d" % len(result))
    with open(paper_db_path, "w", newline='\n', encoding="utf-8") as fw:
        fw.write(json.dumps(result, indent=1, ensure_ascii=False))
    Conferences = list(set([i["venue"] for i in result if i['type'] == "conference" and i["venue"] != ""]))
    Journals = list(set([i["venue"] for i in result if i['type'] == "journal" and i["venue"] != ""]))

    return Conferences, Journals


def extractConference(Conferences):
    # 抽取会议
    projection = {
        "_id": 0,
        "CCF": 1,
        "acronym": 1,
        "name": 1,
        "year": 1,
        "Deadline": 1,
        "Notice": 1,
        "Begin": 1,
        "Location": 1,
        "Link": 1,
        "AbstractRegistrationDue": 1,
        "FinalVersionDue": 1,
        "Categories": 1,
        "Papers": 1,
        "Conf_Related": 1,
        "Journal_Related": 1,
    }
    result = []
    for i in detail.find({"type":"conf","acronym": {"$in": Conferences}}, projection=projection):
        i.update({
            "ccf": i.pop("CCF"),
            "paperDue": i.pop("Deadline"),
            "noticeDue": i.pop("Notice"),
            "heldDate": i.pop("Begin"),
            "location": i.pop("Location"),
            "website": i.pop("Link"),
            "abstractDue": i.pop("AbstractRegistrationDue"),
            "finalDue": i.pop("FinalVersionDue"),
            "category": i.pop("Categories"),
            "bestPaper": i.pop("Papers"),
            "confRelated": i.pop("Conf_Related"),
            "journalRelated": i.pop("Journal_Related"),
        })
        i['acronym'] = i['acronym'].replace('\'', '').strip()
        result.append(i)

    print("Conference size: %d" % len(result))
    with open(conference_db_path, "w", newline='\n', encoding="utf-8") as fw:
        fw.write(json.dumps(result, indent=1, ensure_ascii=False))


def extractJournal(Journals):
    # 抽取期刊
    projection = {
        "_id": 0,
        "CCF": 1,
        "acronym": 1,
        "name": 1,
        "ISSN": 1,
        "E_ISSN": 1,
        "IF": 1,
        "self_citing": 1,
        "h_index": 1,
        "fenqu": 1,
        "website": 1,
        "submit": 1,
        "OA": 1,
        "large_area": 1,
        "speed": 1,
        "rate": 1,
    }
    result = []
    for i in detail.find({"type":"journal","acronym": {"$in": Journals}}, projection=projection):
        i.update({
            "name": i.pop("acronym"),
            "ccf": i.pop("CCF"),
            "sci": i.pop("fenqu"),
            "category": i.pop("large_area"),
        })
        result.append(i)
    for i in detail.find({"type":"journal","name": {"$in": Journals}}, projection=projection):
        i.update({
            "ccf": i.pop("CCF"),
            "sci": i.pop("fenqu"),
            "category": i.pop("large_area"),
        })
        i.pop("acronym")
        result.append(i)

    print("Journal size: %d" % len(result))
    with open(journal_db_path, "w", newline='\n', encoding="utf-8") as fw:
        fw.write(json.dumps(result, indent=1, ensure_ascii=False))

def extractInstitution(Institutions):
    data = []
    for i in Institutions:
        data.append({
            "name": i,
            "name_zh": "",
            "address": "",
            "website": ""
        })
    print("Institution size: %d" % len(data))
    with open(institution_db_path, "w", newline='\n', encoding="utf-8") as fw:
        fw.write(json.dumps(data, indent=1, ensure_ascii=False))

def pattern():
    # 统一数据格式
    z_str = ["ISSN", "E_ISSN", "OA", "category", "speed", "rate", "sci", "title", "type", "pdf", "doi", "abstract", "venue", "name", "name_zh", "acronym", "affiliation", "position", "position_zh", "year", "ccf", "paperDue", "noticeDue", "heldDate", "location", "website", "submit", "abstractDue", "finalDue", ]
    z_number = ["citations", "pubs",  "IF", "self_citing", "h_index"]
    z_list = ["field", "field_score", "confRelated", "bestPaper", "journalRelated", "author", "blog_urls"]
    for file in [author_db_path, conference_db_path, paper_db_path, journal_db_path, institution_db_path]:
        with open(file, "r", encoding="utf-8") as fw:
            data = json.load(fw)
        result = []
        for i in data:
            for k,v in i.items():
                if k in z_str and v is None:
                    i[k] = ""
                elif k in z_number and v is None:
                    i[k] = 0
                elif k in z_list and v is None:
                    i[k] = []
                        
            result.append(i)
        with open(file, "w", newline='\n', encoding="utf-8") as fw:
            fw.write(json.dumps(result, indent=1, ensure_ascii=False))

def analysis():
    if os.path.exists(statistic_path):
        os.remove(statistic_path)
    # 字段覆盖率
    for file in [author_db_path, paper_db_path, conference_db_path, journal_db_path]:
        with open(file, "r", encoding="utf-8") as fw:
            data = json.load(fw)
        size = len(data)
        dict = data[-1]
        for i in dict.keys():
            dict[i] = 0
        for i in data:
            for k,v in i.items():
                if v is not None:
                    if type(v) is str or type(v) is list:
                        if len(v) == 0:
                            continue
                    else:
                        if v == 0:
                            continue
                    dict[k] += 1
        with open(statistic_path, "a", encoding="utf-8") as fw:
            fw.write(file + "\n")
            for k,v in dict.items():
                fw.write("\t%s:\t\t%.6f\n" % (k, v/size))
            fw.write("\ttotal:\t\t%d\n\n" % size)
    
    # 机构出场率前20
    with open(author_db_path, 'r', encoding='utf-8') as fw:
        data=json.load(fw)
    count={}
    for i in data:
        if i["affiliation"] is None:
            continue
        for j in i["affiliation"].split("/"):
            k = j.strip()
            if len(k) == 0:
                continue
            if k in count.keys():
                count[k] += 1
            else:
                count[k] = 1
    t = sorted(count.items(), key=lambda x:x[1], reverse=True)[:30]
    with open(statistic_path, "a", encoding="utf-8") as fw:
        fw.write("前30出场的机构:\n")
        for i in t:
            fw.write(i[0]+ "\t\t"+ str(i[1])+"\n")
    extractInstitution([i[0] for i in t])


if __name__ == "__main__":
    Authors, Institutions = extractAuthor()
    # Conferences, Journals = extractPaper(Authors)
    # extractConference(Conferences)
    # extractJournal(Journals)
    # pattern()
    # analysis()

    # with open(journal_db_path, "r", encoding="utf-8") as fw:
    #     data=json.load(fw)
    # names = [i["name"] for i in data]
    # K = []
    # for i in data:
    #     name = i["name"]
    #     result = detail.find({"type": "journal", "name": {"$regex": name}}, projection={"_id":0})
    #     for j in result:
    #         if j["name"] in names or j["acronym"] in names or j["ISSN"] is None:
    #             continue
    #         if "." not in name:
    #             continue
    #         j["asource"] = name
    #         K.append(j)
    # print(len(K))
    # with open("db/z.json", "w", newline='\n', encoding="utf-8") as fw:
    #     fw.write(json.dumps(K, indent=1, ensure_ascii=False))
