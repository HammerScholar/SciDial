# SciDial
## Introduction

SciDial is a **Chinese Academic Task-Oriented Dialogue Dataset**. It consists of 5 domains, 49 slots, 1,423,870 messages and 50,458 dialogues on the application of intelligent recommendation, inquiry, confirmation, browse, download on academic information as well as some chit-chat conversations. This represents the complete set of training an Intelligent Academic Dialogue Robot. It mainly involves 5 areas, which are Conference, Paper, Journal, Author and Institution. These academic data was crawled from the official websites and open-source websites.  

The data collection process includes manual annotation and machine generation. A lot of dialogue logs show that difference utterances usually indicates the same purpose and they can replace each other, which are named the Template. Researchers collected the whole related templates and build the **Template Relationship Graph**. Then these templates were annotated by many scientific personnel. The annotation method can significantly improve data scale and ensure smooth dialogue, which helps to build a high-quality dialogue system.

The goal of the collection was to build an academic dialogue system and support the whole task-oriented dialogue tasks, including Natural Language Understanding, Dialogue State Tracking, Policy Learning, Natural Language Generation and End-to-End Task-Oriented Dialogue. Besides, comparing to previous task-oriented dialogue dataset, three more complicated problems were designed: (i) multi-value slot; (ii) discontinuous conversation; (iii) doubt to system. For more description on these three problems, see the Specification.

## Specification

Below is the information about the amount of data and its annotation status. Besides raw_data, the dataset contains the data of three kinds of complicated problems, which can be used to prove the model trained on additional data has better performance on these problems. The raw_data includes all data and scenarios.

These are the description of the four scenarios:

- raw_data: the whole data used for train a complete task-oriented dialogue system

- multi_value: each slot consists of several values from utterance or dialogue history

- revert: user opens another topic in one conversation and revert belief state

- doubt: user doubts on the system response and system could correct error if it made a mistake.

The statistics for each kind of data are as follow:

|             | dialogues | utterance | utterance per dialogue | total unique token | slot values |
| ----------- | --------- | --------- | ---------------------- | ------------------ | ----------- |
| raw_data    | 50,458    | 1,400,436 | 27.75                  | 34,179             | 28,248      |
| multi-value | 30,411    | 1,088,672 | 35.80                  | 29,534             | 25,241      |
| revert      | 30,963    | 1,156,076 | 37.34                  | 30,296             | 25,931      |
| doubt       | 16,756    | 531,258   | 31.71                  | 13,226             | 15,402      |

## Download

Download Link is [here](https://drive.google.com/file/d/1irE16Y3-sTAEM93dgCTUP4rS59X3H_E5/view?usp=share_link)

#### File Structure

The directory tree structure is as follow:

```bash
data
├── doubt
│   ├── train.zip
│   ├── dev.zip
│   ├── test.zip
├── multi_value
│   ├── train.zip
│   ├── dev.zip
│   ├── test.zip
├── raw_data
│   ├── train.zip
│   ├── dev.zip
│   ├── test.zip
├── revert
│   ├── train.zip
│   ├── dev.zip
│   ├── test.zip
```

The whole data is stored in `raw_data` including multi-value slot, revert and doubt. Other dictionaries store special data related with the problem scenario.

#### Data Format

File: data/raw_data/[ID].json

A dialogue is stored as a file. For each conversation, we provide its dialogue purpose and conversation process, as well as the belief state and dialogue act, used for DST and Policy Learning.  

```
{
    "MTTT_006310": {
        "goal": {
            "Conference": {
                "semi": {
                    "paperDue": [”下个月],
                    "category": [“NLP]
                }
            },
            "Paper": {},
            "Journal": {},
            "Author": {},
            "Institution": {},
            "description": [
                "Given paperDue,category; Recommend Conference",
                ...
            ]
        },
        "log": [
            {
                "text": "下个月有没有要截稿的NLP会议呢",
                "metadata": {},
                "dialog_act": {
                    "Conference-Inform": [
                        [
                            "paperDue",
                            "下个月"
                        ],
                        [
                            "category",
                            "NLP"
                        ]
                    ]
                },
                "span_info": [
                    [
                        "Conference-Inform",
                        "paperDue",
                        "下个月",
                        0,
                        2
                    ],
                    [
                        "Conference-Inform",
                        "category",
                        "NLP",
                        10,
                        12
                    ]
                ]
            },
            ...
        ]
    }
}
```

