# 每个domain的标识符
identify_dict = {
    "Conference": "acronym",
    "Paper": "title",
    "Journal": "name",
    "Author": "name",
    "Institution": "name"
}
# 不涉及年份的会议槽值
Conference_no_year = ["category", "ccf", "bestPaper", "confRelated", "journalRelated"]
# 同时请求两个槽值的集合
two_slot_dict = {
    "Conference": [
        ["paperDue", "abstractDue"],
        ["paperDue", "finalDue"],
        ["noticeDue", "heldDate"],
        ["heldDate", "location"]
    ],
    "Paper": [[]],
    "Journal": [
        ["website", "submit"]
    ],
    "Author": [[]],
    "Institution": [[]]
}
# 人工标注的默认值
annotate_db = {
    "acronym": ["ACL", "EMNLP"],
    "year": ["今年", "2022", "去年", "近两年"],
    "fullName": ["XXX"],
    "paperDue": ["XXX", "最近一个月", "最近", "快要", "下周", "下下个月", "下个月", "下一个月", "这几天", "11月份", "已经"],
    "noticeDue": ["XXX", "最近一个月", "最近", "快要", "下周", "下下个月", "下个月", "下一个月", "这几天", "11月份", "已经"],
    "heldDate": ["XXX", "最近一个月", "最近", "快要", "下周", "下下个月", "下个月", "下一个月", "这几天", "11月份", "已经"],
    "abstractDue": ["XXX", "11月份", "马上要", "最近要", "下个月", "已经"],
    "finalDue": ["XXX", "11月份", "马上要", "最近要", "最近", "下个月", "已经"],
    "location": ["XXX", "北京", "线上", "线下", "网上"],
    "category": ["XXX", "NLP", "人工智能"],
    "ccf": ["XXX", "A类", "B类"],
    "website": ["XXX", "https://www.2022.aclweb.org/", "https://www.nature.com/"],
    "bestPaper": ["XXX"],
    "confRelated": ["XXX"],
    "journalRelated": ["XXX"],
    "doi": ["XXX"],
    "title": ["这篇论文", "Attention is all you need", "Generative Adversarial Nets"],
    "author": ["李航", "黄河燕", "毛先领"],
    "venue": ["ACL", "EMNLP"],
    "institution": ["北京大学", "清华大学"],
    "abstract": ["XXX"],
    "pdf": ["XXX", "https://aclanthology.org/2020.lrec-1.53.pdf", "https://arxiv.org/pdf/2110.07679.pdf"],
    "blog": ["XXX"],
    "path": ["XXX", "桌面"],
    "name": ["TOIS", "TKDE", "NATURE", "李航", "黄河燕", "北京大学"],
    "ISSN": ["XXX"],
    "E_ISSN": ["XXX"],
    "IF": ["XXX", "IF>10", "IF>15", "IF大于10", "IF最高", "IF指标最高", "IF指标不是最高"],
    "h_index": ["XXX", "h5>10", "h5>15", "h5最高", "h5大于10", "h5指标最高", "h5指标不是最高", "h5指标好像不是最高"],
    "self_citing": ["XXX", "自引率最高"],
    "sci": ["XXX", "SCI一区", "sci一区"],
    "submit": ["XXX"],
    # "OA": 只有True or False
    "speed": ["XXX"],
    "rate": ["XXX"],
    "field": ["XXX", "NLP", "人工智能", "自然语言处理", "机器翻译"],
    "affiliation": ["北京大学", "清华大学", "北京理工大学"],
    "position": ["XXX", "副教授", "教授"],
    "citations": ["XXX"],
    "pubs": ["XXX"],
    "address": ["XXX"]
}