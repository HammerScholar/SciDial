identify_dict = {
    "Conference": "acronym",
    "Paper": "title",
    "Journal": "name",
    "Author": "name",
    "Institution": "name"
}
Conference_no_year = ["category", "ccf", "bestPaper", "confRelated", "journalRelated"]
two_slot_dict = {
    "Conference": [
        ["paperDue", "abstractDue"],
        ["paperDue", "finalDue"],
        ["noticeDue", "heldDate"],
        ["heldDate", "location"]
    ],
    "Paper": [
        ["video", "blog"]
    ],
    "Journal": [
        ["website", "submit"]
    ],
    "Author": [[]],
    "Institution": [[]]
}