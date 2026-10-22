# Manual check: Cancel in the dashboard

Open the dashboard with at least one task not in Done and one task in Done.

1. Look at the cards. Expected: each card not in Done has a red `Cancel` button. Cards in Done have no `Cancel` button.
2. Click `Cancel` on a task. Expected: a dialog opens with the title `Cancel task <name>` and the text `Loading…`.
3. Wait for the dry run. Expected: the dry run text replaces `Loading…`. Before that, `Cancel task` is disabled. After that, it is enabled.
4. Click `Keep task`. Expected: the dialog closes. The card stays.
5. Open the dialog again and press Escape. Expected: the dialog closes. The card stays.
6. Open the dialog again and click outside the dialog. Expected: the dialog closes. The card stays.
7. Open the dialog again and click `Cancel task`. Expected: the button shows `Cancelling…` and both buttons are disabled. Escape and a click outside do nothing until it ends.
8. When the cancel ends. Expected: the dialog closes and the card disappears at once.
9. Wait 5 seconds. Expected: the card does not come back.
10. Reload the page. Expected: the card is still gone.
11. Stop Herdr. Click `Cancel` on another task, then `Cancel task`. Expected: the dialog shows the error. Both buttons work again. The card stays.
12. If a part is left after the archive (for example a branch that cannot be deleted). Expected: the card disappears. The dialog stays open and shows the restore lines and the left parts. Only a `Close` button is shown.
