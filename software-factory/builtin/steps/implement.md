---
id: implement
description: Implement a request in the task folder
category: code
type: ai
done_when: The implementation is finished in the task folder.
config:
  request:
    description: What to implement. With `none`, the step asks the user.
    default: none
required: false
---

Request: {{config.request}}

1. If the request is `none`, run `factory block "<question>"`, ask the user what to implement, then run `factory unblock` when the user answers.
2. If you need more information, ask the user the same way.
3. Implement the request in this task folder.
