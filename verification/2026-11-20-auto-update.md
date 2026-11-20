# Update from the dashboard, manual tests

These tests need a person at a Mac. Use a script install (`install.sh`) of an older release, for example 0.2.0 or the first release with this feature. Make sure that a newer GitHub release exists, with `install.sh` attached. Do not use a git checkout. The update check is off for installs without the file `.installed-by-script`.

Tests 12, 18 and 19 use a fake `install.sh` that changes the file `VERSION`. After each of these tests, write the old version back to `VERSION` in the install folder. If you do not, a later failed install counts as an installed update.

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
| 10 | Open the dashboard in two browser tabs. Click `Update` in the first tab | The first tab goes to the new URL. The old server stops up to 30 seconds after the first tab reads the result. Then the second tab shows `Offline`. | |
| 11 | Set the terminal choice (`~/.config/software-factory/terminal`, for example `herdr`). Note the file content. Do an update | The file content is the same after the update. No question is asked. | |
| 12 | Make a fake `install.sh` that writes the latest version of the banner to `$FACTORY_INSTALL_DIR/VERSION` and runs `chmod -x "$FACTORY_INSTALL_DIR/bin/factory"`. Serve it from a local folder with `python3 -m http.server 8765`. Stop the server. Set `FACTORY_UPDATE_INSTALL_URL=http://127.0.0.1:8765/install.sh` in the shell profile and open the Dock app again. Click `Update` | The page shows `The update is installed, but the new server did not start.` with the path of `server.log`. The error stays until you click `Close`. | |
| 13 | After test 12, run `chmod +x bin/factory` in the install folder. Click `Close`. Then click `Start` in the Dock app | The old server stops up to 30 seconds after `Close`. The Dock app shows `Server stopped` and `Start`. `Start` starts the new server and the dashboard comes back. Remove `FACTORY_UPDATE_INSTALL_URL` from the shell profile after this test. | |
| 14 | Open the dashboard in two browser tabs. Click `Update` in the first tab. Click `Update` in the second tab while the update runs | The second tab shows `Updating…` for the same job. No second install starts. | |
| 15 | During an update, run `curl -X POST` on `/api/tasks/<id>/check` of the old server (use the URL and token of the old page) | The old server answers `An update is running.` | |
| 16 | After a successful update, read the file `VERSION` in the install folder | The version is the latest version of the banner. | |
| 17 | Start the dashboard with `FACTORY_NO_UPDATE_CHECK=1` | The banner does not show, also when a newer release exists. | |
| 18 | Make a fake `install.sh` that writes the latest version of the banner to `$FACTORY_INSTALL_DIR/VERSION`, writes `link failed` to the output, and exits with status 1. Serve it as in test 12 and click `Update` | The page goes to the new server. It shows `CAPTN is updated to <latest>. install.sh reported an error. See <path>/update.log.` The file `update.log` contains `link failed`. | |
| 19 | Do test 12 again, but do not click `Close` | The error shows. The old server stops by itself not more than 60 seconds plus 30 seconds after the error shows. The Dock app then shows `Server stopped` and `Start`. | |
| 20 | Turn off the network, or set `FACTORY_UPDATE_URL` to a bad URL before the server starts. Open the dashboard | The banner does not show. No error shows. The dashboard opens as fast as without the check. | |
| 21 | Start the dashboard from a git checkout (no file `.installed-by-script`) while a newer release exists | The banner does not show. | |
| 22 | After test 4, wait 10 seconds | The text `CAPTN is updated to <latest>.` goes away. No banner comes back, also after you reload the page. | |
