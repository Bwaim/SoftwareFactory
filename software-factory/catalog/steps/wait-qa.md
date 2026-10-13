---
id: wait-qa
description: Wait until the user marks QA as done
category: qa
type: ai
done_when: QA is done.
wait_external: true
required: false
column: QA
---

Tell the user the task waits for QA. The user marks it done from the dashboard or the menu.
Then run `factory wait`.
