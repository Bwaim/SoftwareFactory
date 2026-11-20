---
id: get-user-request
description: Ask the user what to do and save the request
category: factory
type: ai
outputs:
  request:
    type: file
    description: The request of the user
done_when: The request file is written and its path is saved.
required: false
---

1. Run `factory block "What do you want to do?"`, ask the user what they want to do, then run `factory unblock` when the user answers.
2. Write the request of the user to the path printed by `factory artifact path request.md`.
