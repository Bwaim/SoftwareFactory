# Update from the dashboard, manual tests

These tests need a person at a Mac. Use a script install (`install.sh`) of an older release, for example 0.2.0 or the first release with this feature. Make sure that a newer GitHub release exists, with `install.sh` attached. Do not use a git checkout. The update check is off for installs without the file `.installed-by-script`.

| # | Test | Expected | Result |
| --- | --- | --- | --- |
| 1 | Open the dashboard in a browser tab while a newer release exists | The banner shows `New version <latest> is available (you have <installed>).` with `Update` and `Later`. | |
| 2 | Click `Later`, then reload the page | The banner does not show. | |
| 3 | After test 2, publish a release that is newer again (or wait for the next check) and reload the page | The banner shows again with the new version. | |
| 4 | Open the dashboard in a browser tab with no running task. Click `Update` | The banner shows `Updating…` and the buttons are disabled. After the install, the tab goes to the new URL. The page shows `CAPTN is updated to <latest>.` for 10 seconds. | |
| 5 | Open the dashboard in the Dock app. Click `Update` | The dashboard window goes to the new server. It does not show `Server stopped`. The page shows `CAPTN is updated to <latest>.` for 10 seconds. | |
| 6 | Open an editor window in the Dock app. Click `Update` in the dashboard window | The editor window also goes to the new server. It does not show `Server stopped`. | |
| 7 | Start a task so that an agent session is live. Click `Update` | The page shows `<n> tasks are running. They continue, and their next steps use the new version. Update now?` The update starts only after you confirm. | |
| 8 | Make the download fail (for example turn off the network, or set `FACTORY_UPDATE_INSTALL_URL` to a bad URL before the server starts). Click `Update` | The banner shows `The update failed.` and the output of `install.sh`, with `Close`. The old version is still in place. | |
| 9 | Start a task that waits on a done check. Do test 8 | After the failure, the done checks run again. The task moves on. | |
| 10 | Open the dashboard in two browser tabs. Click `Update` in the first tab | The first tab goes to the new URL. The second tab shows `Offline`. | |
| 11 | Set the terminal choice (`~/.config/software-factory/terminal`, for example `herdr`). Note the file content. Do an update | The file content is the same after the update. No question is asked. | |
| 12 | In the Dock app, make the new server fail to start (for example make `bin/factory` not executable in the installed folder after the swap, or block the port start). Click `Update` | The page shows `The update is installed, but the new server did not start.` with the path of `server.log`. The error stays until you click `Close`. | |
| 13 | After test 12, click `Close`. Then click `Start` in the Dock app | `Close` stops the old server. The Dock app shows `Server stopped` and `Start`. `Start` starts the new server and the dashboard comes back. | |
| 14 | Open the dashboard in two browser tabs. Click `Update` in the first tab. Click `Update` in the second tab while the update runs | The second tab shows `Updating…` for the same job. No second install starts. | |
| 15 | During an update, run `curl -X POST` on `/api/tasks/<id>/check` of the old server (use the URL and token of the old page) | The old server answers `An update is running.` | |
| 16 | After a successful update, read the file `VERSION` in the install folder | The version is the latest version of the banner. | |
| 17 | Start the dashboard with `FACTORY_NO_UPDATE_CHECK=1` | The banner does not show, also when a newer release exists. | |
