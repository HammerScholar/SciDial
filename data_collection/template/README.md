# Dialogue Auto-generate Module

## Template Form
```
template = {
    "action": [],
    "required_slot": [],
    "requested_slot": [],
    "description": "",
    "message": []
}
```

## File
pre_process.py: auto-generate template


## Intent
User often uses the Sci-Chatbot for **finding resources with sprcific constraints** or **asking for some details of the resource**. Besides, we add the **Browse and Download** function for API scaling. Considering possible error of system response, we bring in the **Confirm and Doubt** to make chatbot have correction capability.

#### Recommend
##### User
1. give the positive response
2. *just inform some constraints for search
3. positive + inform
4. negative + inform
5. update a constraints
6. positive + update
7. negative + update
8. add a constraints
9. negative + add
> * indicates this sentence can be used as the start of the dialogue

##### System
1. just confirm the user's constraints
2. *search dataset and choice=0
3. search dataset and choice=0, then system recommend a slot to update
4. search dataset and choice=0, then confirm user's constraints
5. *search dataset and choice=1, return result
6. *search dataset and choice=2~3, return result
7. search dataset and choice=2~3, just reqmore
8. search dataset and choice=2~3, reqmore a slot
9. search dataset and choice>=4, confirm whether output
9. *search dataset and choice>=4, return result
10. search dataset and choice>=4, just reqmore
11. search dataset and choice>=4, reqmore a slot
> * indicates this sentence can be used as the end of the dialogue

##### Connection
User -> every System except S10 have to behind S9 and U1
System -> User
- S1 -> U1,U4,U7
- S2,S5,S6 -> U2,U5
- S3 -> U5
- S4 -> U3,U4,U6,U7
- S7,S8,S11,S12 -> U8
- S9 -> U1,U9
- S10 -> U2


#### Request or Confirm
##### User
1. request a slot
2. confirm a slot

##### System
1. *find the value of slot
2. *cannot find the value of slot
3. cannot find the value of slot and recommend other slot
4. *positive
5. *negative + inform true value

##### Connection
U1 -> S1,S2,S3
U2 -> S4,S5


#### Doubt
##### User
1. just doubt
2. doubt specific slot

##### System
1. *check
2. *positive + return new result 同上
3. *just negative
4. *negative + inform doubted slot

##### Connection
U1 -> S2,S3
U2 -> S1,S2,S3,S4

#### Browse or Download
##### User
1. request browse
2. request download with path
3. request download without path
4. tell path

##### System
1. *can browse and succeed browse
2. *cannot browse
3. req download path
4. *can download and succeed download
5. *cannot download

##### Connection
U1 -> S1,S2
U2 -> S4,S5
U3 -> S3 -> U4 -> S4,S5

#### General
##### User
1. greeting
2. Bye
3. depression without finding what he wants
4. thanks with finding what he wants

##### System
1. greeting
2. Bye
3. Welcome