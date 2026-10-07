# Marathi translations - review list

All Marathi texts were written by the developers and **every entry needs review by a
native Marathi speaker** familiar with the shop floor. Status of every key below:
`needs_review`.

How to review
1. Check meaning, tone (simple words for operators) and spelling.
2. Keep every `{placeholder}` exactly as it is (a test checks this).
3. Keep product words the operators actually use (PCB, MAC, QR, firmware, Enter, F1-F4).
4. Edit `mr.json`; then change the status here to `ok`.
5. Look at the Marathi screenshots (`docs/screenshots/mr_*.png`) for length and layout.

Total keys: **689** - needs_review: **689**

## a11y (`a11y.*`, 1)

| Key | English | Marathi | Status |
|---|---|---|---|
| `a11y.language_switch` | Switch language to {language} | भाषा {language} करा | needs_review |

## Buttons (verbs) (`action.*`, 56)

| Key | English | Marathi | Status |
|---|---|---|---|
| `action.login` | Log in | लॉग इन करा | needs_review |
| `action.logout` | Log out | लॉग आउट करा | needs_review |
| `action.show_password` | Show | दाखवा | needs_review |
| `action.hide_password` | Hide | लपवा | needs_review |
| `action.connect_board` | Connect board | बोर्ड जोडा | needs_review |
| `action.refresh_ports` | Refresh ports | पोर्ट रिफ्रेश करा | needs_review |
| `action.upload_firmware` | Upload firmware | फर्मवेअर अपलोड करा | needs_review |
| `action.retry_upload` | Retry upload | पुन्हा अपलोड करा | needs_review |
| `action.retry_upload_n` | Retry upload ({n} of {total}) | पुन्हा अपलोड करा ({total} पैकी {n}) | needs_review |
| `action.load_firmware` | Load firmware | फर्मवेअर लोड करा | needs_review |
| `action.submit_next` | Submit and next | जमा करा आणि पुढे | needs_review |
| `action.reject_device` | Reject device | डिव्हाइस नाकारा | needs_review |
| `action.try_again` | Try again | पुन्हा प्रयत्न करा | needs_review |
| `action.test_again` | Test again | पुन्हा तपासा | needs_review |
| `action.read_sensor_n` | Read sensor ({n} of {total}) | सेन्सर वाचा ({total} पैकी {n}) | needs_review |
| `action.mark_success` | ✓ Success | ✓ यशस्वी | needs_review |
| `action.mark_failure` | ✕ Failure | ✕ अयशस्वी | needs_review |
| `action.measure` | Measure | मोजा | needs_review |
| `action.measure_again` | Measure again | पुन्हा मोजा | needs_review |
| `action.remeasure_ambient` | Re-measure ambient | वातावरण तापमान पुन्हा मोजा | needs_review |
| `action.scan_again` | Scan again | पुन्हा स्कॅन करा | needs_review |
| `action.type_id` | Type ID by hand | ID हाताने टाइप करा | needs_review |
| `action.confirm_id` | Confirm ID | ID निश्चित करा | needs_review |
| `action.complete_device` | Complete device | डिव्हाइस पूर्ण करा | needs_review |
| `action.device_placed` | Device placed in box | डिव्हाइस बॉक्समध्ये ठेवले | needs_review |
| `action.adjust_yes` | Yes, remove 1 failure | होय, 1 अपयश कमी करा | needs_review |
| `action.adjust_no` | No, keep it | नाही, तसेच ठेवा | needs_review |
| `action.confirm` | Yes, continue | होय, पुढे चला | needs_review |
| `action.cancel` | Cancel | रद्द करा | needs_review |
| `action.yes_failed` | Yes, it failed - reject | होय, अयशस्वी - नाकारा | needs_review |
| `action.close` | Close | बंद करा | needs_review |
| `action.close_app` | Close the application | ॲप्लिकेशन बंद करा | needs_review |
| `action.session` | Session | सत्र | needs_review |
| `action.admin` | Admin | ॲडमिन | needs_review |
| `action.end_session` | End session | सत्र संपवा | needs_review |
| `action.reset_counters` | Reset counters | काउंटर रीसेट करा | needs_review |
| `action.details_for_support` | Details for support | सपोर्टसाठी तपशील | needs_review |
| `action.back_to_production` | Back to production | उत्पादनाकडे परत | needs_review |
| `action.save_settings` | Save settings | सेटिंग्ज जतन करा | needs_review |
| `action.reload_settings` | Undo changes | बदल रद्द करा | needs_review |
| `action.store_secret` | Store in Credential Manager | Credential Manager मध्ये जतन करा | needs_review |
| `action.add_operator` | Add operator | ऑपरेटर जोडा | needs_review |
| `action.activate` | Activate | सक्रिय करा | needs_review |
| `action.deactivate` | Deactivate | निष्क्रिय करा | needs_review |
| `action.unlock` | Unlock | अनलॉक करा | needs_review |
| `action.make_admin` | Make supervisor | सुपरवायझर बनवा | needs_review |
| `action.make_operator` | Make operator | ऑपरेटर बनवा | needs_review |
| `action.reset_password` | Set new password | नवीन पासवर्ड सेट करा | needs_review |
| `action.export_excel` | Export Excel | Excel एक्सपोर्ट करा | needs_review |
| `action.export_csv` | Export CSV | CSV एक्सपोर्ट करा | needs_review |
| `action.export_range` | Export date range | तारीख-मर्यादा एक्सपोर्ट करा | needs_review |
| `action.export_device` | Export device report | डिव्हाइस अहवाल एक्सपोर्ट करा | needs_review |
| `action.open_reports_folder` | Open reports folder | अहवाल फोल्डर उघडा | needs_review |
| `action.resend` | Resend selected | निवडलेले पुन्हा पाठवा | needs_review |
| `action.send_pending` | Send waiting e-mails now | बाकी ई-मेल आत्ता पाठवा | needs_review |
| `action.refresh` | Refresh | रिफ्रेश करा | needs_review |

## Admin area (`admin.*`, 63)

| Key | English | Marathi | Status |
|---|---|---|---|
| `admin.title` | Admin | ॲडमिन | needs_review |
| `admin.tab.settings` | Settings | सेटिंग्ज | needs_review |
| `admin.tab.operators` | Operators | ऑपरेटर | needs_review |
| `admin.tab.reports` | Reports & e-mail | अहवाल व ई-मेल | needs_review |
| `admin.tab.counters` | Counters | काउंटर | needs_review |
| `admin.tab.errors` | Error log | त्रुटी लॉग | needs_review |
| `admin.op.code` | Operator ID | ऑपरेटर ID | needs_review |
| `admin.op.name` | Full name | पूर्ण नाव | needs_review |
| `admin.op.role` | Role | भूमिका | needs_review |
| `admin.op.active` | Active | सक्रिय | needs_review |
| `admin.op.locked` | Locked | लॉक | needs_review |
| `admin.op.add_title` | New operator | नवीन ऑपरेटर | needs_review |
| `admin.op.password` | Password | पासवर्ड | needs_review |
| `admin.op.password_again` | Password again | पासवर्ड पुन्हा | needs_review |
| `admin.op.new_password` | New password | नवीन पासवर्ड | needs_review |
| `admin.op.passwords_differ` | The two passwords are different | दोन्ही पासवर्ड वेगळे आहेत | needs_review |
| `admin.op.created` | Operator {code} added | ऑपरेटर {code} जोडला | needs_review |
| `admin.op.updated` | Operator {code} updated | ऑपरेटर {code} अपडेट केला | needs_review |
| `admin.op.unlocked` | Operator {code} unlocked | ऑपरेटर {code} अनलॉक केला | needs_review |
| `admin.op.password_reset` | New password set for {code} | {code} साठी नवीन पासवर्ड सेट केला | needs_review |
| `admin.rep.sessions_title` | Sessions (newest first) | सत्रे (नवीन प्रथम) | needs_review |
| `admin.rep.session` | Session | सत्र | needs_review |
| `admin.rep.operator` | Operator | ऑपरेटर | needs_review |
| `admin.rep.started` | Started | सुरुवात | needs_review |
| `admin.rep.ended` | Ended | समाप्त | needs_review |
| `admin.rep.devices` | Devices | डिव्हाइसेस | needs_review |
| `admin.rep.from` | From date | पासून तारीख | needs_review |
| `admin.rep.to` | To date | पर्यंत तारीख | needs_review |
| `admin.rep.format` | File format | फाइल प्रकार | needs_review |
| `admin.rep.format_xlsx` | Excel | Excel | needs_review |
| `admin.rep.format_csv` | CSV | CSV | needs_review |
| `admin.rep.format_both` | Excel + CSV | Excel + CSV | needs_review |
| `admin.rep.device_search` | Device ID or MAC | डिव्हाइस ID किंवा MAC | needs_review |
| `admin.rep.select_session` | Select one or more sessions first | आधी एक किंवा अधिक सत्रे निवडा | needs_review |
| `admin.rep.working` | Writing the report… | अहवाल लिहित आहे… | needs_review |
| `admin.rep.written` | Written: {files} | लिहिले: {files} | needs_review |
| `admin.rep.no_device` | No device found for "{text}" | "{text}" साठी डिव्हाइस सापडले नाही | needs_review |
| `admin.out.title` | E-mail outbox | ई-मेल आउटबॉक्स | needs_review |
| `admin.out.id` | No. | क्र. | needs_review |
| `admin.out.created` | Created | तयार | needs_review |
| `admin.out.subject` | Subject | विषय | needs_review |
| `admin.out.status` | Status | स्थिती | needs_review |
| `admin.out.attempts` | Attempts | प्रयत्न | needs_review |
| `admin.out.error` | Last error | शेवटची त्रुटी | needs_review |
| `admin.out.select_item` | Select an e-mail first | आधी ई-मेल निवडा | needs_review |
| `admin.out.sent` | E-mail sent ✓ | ई-मेल पाठवला ✓ | needs_review |
| `admin.out.not_sent` | Not sent - it stays in the outbox and will be retried | पाठवला नाही - आउटबॉक्समध्ये राहील आणि पुन्हा प्रयत्न होईल | needs_review |
| `admin.out.disabled` | E-mail is switched off in the settings | सेटिंग्जमध्ये ई-मेल बंद आहे | needs_review |
| `admin.out.result` | Sent {sent}, failed {failed} | पाठवले {sent}, अयशस्वी {failed} | needs_review |
| `admin.cnt.title` | Live counters of this session | या सत्राचे चालू काउंटर | needs_review |
| `admin.cnt.values` | Uploads ✓ {ok}  ✕ {fail}  (removed {adjusted})<br>Completed {done}   Rejected {rejected}<br>Counting since: {since} | अपलोड ✓ {ok}  ✕ {fail}  (कमी {adjusted})<br>पूर्ण {done}   नाकारलेले {rejected}<br>मोजणी सुरू: {since} | needs_review |
| `admin.cnt.since_start` | session start | सत्र सुरुवात | needs_review |
| `admin.cnt.help` | Resetting only restarts the live counters. Every event stays in the history and in the session report. | रीसेटमुळे फक्त चालू काउंटर पुन्हा सुरू होतात. प्रत्येक घटना इतिहासात आणि सत्र अहवालात राहते. | needs_review |
| `admin.cnt.no_session` | No open session | कोणतेही चालू सत्र नाही | needs_review |
| `admin.cnt.reset_done` | Counters reset | काउंटर रीसेट झाले | needs_review |
| `admin.log.time` | Time | वेळ | needs_review |
| `admin.log.level` | Level | स्तर | needs_review |
| `admin.log.code` | Code | कोड | needs_review |
| `admin.log.message` | Message | संदेश | needs_review |
| `admin.log.all_codes` | All error codes | सर्व त्रुटी कोड | needs_review |
| `admin.log.filter` | Filter by error code | त्रुटी कोडनुसार फिल्टर | needs_review |
| `admin.log.details` | Details of the selected entry | निवडलेल्या नोंदीचा तपशील | needs_review |
| `admin.log.empty` | No errors logged | कोणतीही त्रुटी नोंदलेली नाही | needs_review |

## ambient_reason (`ambient_reason.*`, 2)

| Key | English | Marathi | Status |
|---|---|---|---|
| `ambient_reason.session_start` | session start | सत्र सुरुवात | needs_review |
| `ambient_reason.remeasure` | re-measured | पुन्हा मोजले | needs_review |

## app (`app.*`, 3)

| Key | English | Marathi | Status |
|---|---|---|---|
| `app.brand` | Parkomate Station | Parkomate स्टेशन | needs_review |
| `app.window_title` | Parkomate Station - {station} | Parkomate स्टेशन - {station} | needs_review |
| `app.version` | Version {version} | आवृत्ती {version} | needs_review |

## camera (`camera.*`, 4)

| Key | English | Marathi | Status |
|---|---|---|---|
| `camera.preview` | Camera preview | कॅमेरा प्रिव्ह्यू | needs_review |
| `camera.simulated` | Simulated camera | सिम्युलेटेड कॅमेरा | needs_review |
| `camera.scanning` | Scanning… | स्कॅन करत आहे… | needs_review |
| `camera.idle` | Camera ready | कॅमेरा तयार | needs_review |

## Check names (`check.*`, 30)

| Key | English | Marathi | Status |
|---|---|---|---|
| `check.A_WHITELIST` | Device authorised (whitelist) | डिव्हाइस अधिकृत (व्हाइटलिस्ट) | needs_review |
| `check.A_UPLOAD` | Firmware upload | फर्मवेअर अपलोड | needs_review |
| `check.B1_COMM` | Communication test | कम्युनिकेशन चाचणी | needs_review |
| `check.B2_SENSOR_OK` | Sensor readings OK | सेन्सर रीडिंग्ज ठीक | needs_review |
| `check.B2_INDICATOR_OK` | Indicator light OK | इंडिकेटर लाइट ठीक | needs_review |
| `check.B3_V_A` | Point A voltage | पॉइंट A व्होल्टेज | needs_review |
| `check.B3_V_B` | Point B voltage | पॉइंट B व्होल्टेज | needs_review |
| `check.B3_V_C` | Point C voltage | पॉइंट C व्होल्टेज | needs_review |
| `check.B3_T_REG` | Regulator temperature | रेग्युलेटर तापमान | needs_review |
| `check.B3_T_AMB` | Ambient temperature (measuring device) | वातावरण तापमान (मापन उपकरण) | needs_review |
| `check.C1` | PCB fitted in casing | PCB केसिंगमध्ये बसवले | needs_review |
| `check.C2` | Screws fitted | स्क्रू लावले | needs_review |
| `check.C3` | Branding sticker applied | ब्रँडिंग स्टिकर लावले | needs_review |
| `check.C4` | QR sticker applied | QR स्टिकर लावले | needs_review |
| `check.C_QR_READ` | QR code read | QR कोड वाचला | needs_review |
| `check.C_ID_SYNC` | Device ID matches QR | डिव्हाइस ID QR शी जुळतो | needs_review |
| `check.D1` | Sensor packed | सेन्सर पॅक केला | needs_review |
| `check.D2` | Indicator packed | इंडिकेटर पॅक केला | needs_review |
| `check.D3` | Connectors packed | कनेक्टर पॅक केले | needs_review |
| `check.D4` | Screws and accessories packed | स्क्रू व ॲक्सेसरीज पॅक केल्या | needs_review |
| `check.B2_READING_1` | Sensor reading 1 | सेन्सर रीडिंग 1 | needs_review |
| `check.B2_READING_2` | Sensor reading 2 | सेन्सर रीडिंग 2 | needs_review |
| `check.B2_READING_3` | Sensor reading 3 | सेन्सर रीडिंग 3 | needs_review |
| `check.B2_READING_4` | Sensor reading 4 | सेन्सर रीडिंग 4 | needs_review |
| `check.B2_READING_5` | Sensor reading 5 | सेन्सर रीडिंग 5 | needs_review |
| `check.B2_READING_6` | Sensor reading 6 | सेन्सर रीडिंग 6 | needs_review |
| `check.B2_READING_7` | Sensor reading 7 | सेन्सर रीडिंग 7 | needs_review |
| `check.B2_READING_8` | Sensor reading 8 | सेन्सर रीडिंग 8 | needs_review |
| `check.B2_READING_9` | Sensor reading 9 | सेन्सर रीडिंग 9 | needs_review |
| `check.B2_READING_10` | Sensor reading 10 | सेन्सर रीडिंग 10 | needs_review |

## Command line (`cli.*`, 37)

| Key | English | Marathi | Status |
|---|---|---|---|
| `cli.description` | Parkomate production-line station. | Parkomate उत्पादन-लाइन स्टेशन. | needs_review |
| `cli.help.data_dir` | data folder (default: ProgramData\Parkomate) | डेटा फोल्डर (डीफॉल्ट: ProgramData\Parkomate) | needs_review |
| `cli.help.settings` | settings file to use | वापरायची सेटिंग्ज फाइल | needs_review |
| `cli.help.mock` | use the simulated (mock) hardware | सिम्युलेटेड (मॉक) हार्डवेअर वापरा | needs_review |
| `cli.help.scenario` | mock scenario to simulate | सिम्युलेट करायचा मॉक प्रसंग | needs_review |
| `cli.help.kiosk` | full-screen kiosk mode | पूर्ण-स्क्रीन किऑस्क मोड | needs_review |
| `cli.help.admin` | operator administration | ऑपरेटर व्यवस्थापन | needs_review |
| `cli.help.admin_create` | create the first administrator | पहिला ॲडमिन तयार करा | needs_review |
| `cli.help.password_stdin` | read the password from standard input | पासवर्ड standard input मधून वाचा | needs_review |
| `cli.help.admin_unlock` | unlock an operator | ऑपरेटर अनलॉक करा | needs_review |
| `cli.help.admin_reset` | set a new password for an operator | ऑपरेटरसाठी नवीन पासवर्ड सेट करा | needs_review |
| `cli.help.settings_cmd` | settings file tools | सेटिंग्ज फाइल साधने | needs_review |
| `cli.help.settings_check` | validate the settings file | सेटिंग्ज फाइल तपासा | needs_review |
| `cli.help.secrets` | store secrets in the Windows Credential Manager | गुप्त माहिती Windows Credential Manager मध्ये जतन करा | needs_review |
| `cli.help.secrets_set` | store a secret | गुप्त माहिती जतन करा | needs_review |
| `cli.help.secrets_delete` | remove a secret | गुप्त माहिती काढून टाका | needs_review |
| `cli.help.outbox` | e-mail outbox | ई-मेल आउटबॉक्स | needs_review |
| `cli.help.outbox_send` | send pending e-mails now | बाकी ई-मेल आत्ता पाठवा | needs_review |
| `cli.help.report` | export a session report | सत्र अहवाल एक्सपोर्ट करा | needs_review |
| `cli.prompt.password` | New password:  | नवीन पासवर्ड:  | needs_review |
| `cli.prompt.password_again` | Repeat password:  | पासवर्ड पुन्हा टाका:  | needs_review |
| `cli.prompt.code` | Operator ID:  | ऑपरेटर ID:  | needs_review |
| `cli.prompt.name` | Full name:  | पूर्ण नाव:  | needs_review |
| `cli.prompt.secret` | Value for {name}:  | {name} साठी मूल्य:  | needs_review |
| `cli.password_mismatch` | The two passwords are different. Nothing was changed. | दोन्ही पासवर्ड वेगळे आहेत. काहीही बदलले नाही. | needs_review |
| `cli.settings_invalid` | The settings file has problems: | सेटिंग्ज फाइलमध्ये समस्या आहेत: | needs_review |
| `cli.settings_ok` | Settings file is valid: {path} | सेटिंग्ज फाइल बरोबर आहे: {path} | needs_review |
| `cli.admin_exists` | An administrator already exists. Add more operators in the admin area. | ॲडमिन आधीच आहे. आणखी ऑपरेटर ॲडमिन विभागात जोडा. | needs_review |
| `cli.admin_created` | Administrator {code} created. | ॲडमिन {code} तयार केला. | needs_review |
| `cli.operator_not_found` | No operator with ID {code}. | {code} ID असलेला ऑपरेटर नाही. | needs_review |
| `cli.no_admin` | No active administrator exists. Run: python -m parkomate admin create | कोणताही सक्रिय ॲडमिन नाही. हे चालवा: python -m parkomate admin create | needs_review |
| `cli.operator_unlocked` | Operator {code} unlocked. | ऑपरेटर {code} अनलॉक केला. | needs_review |
| `cli.password_reset_done` | New password set for {code}. | {code} साठी नवीन पासवर्ड सेट केला. | needs_review |
| `cli.secret_saved` | Secret {name} stored in the Credential Manager. | गुप्त माहिती {name} Credential Manager मध्ये जतन केली. | needs_review |
| `cli.secret_deleted` | Secret {name} removed. | गुप्त माहिती {name} काढून टाकली. | needs_review |
| `cli.outbox_disabled` | E-mail is switched off in the settings; nothing was sent. | सेटिंग्जमध्ये ई-मेल बंद आहे; काहीही पाठवले नाही. | needs_review |
| `cli.outbox_result` | E-mails sent: {sent}, failed: {failed}. | पाठवलेले ई-मेल: {sent}, अयशस्वी: {failed}. | needs_review |

## common (`common.*`, 2)

| Key | English | Marathi | Status |
|---|---|---|---|
| `common.yes` | Yes | होय | needs_review |
| `common.no` | No | नाही | needs_review |

## confirm (`confirm.*`, 6)

| Key | English | Marathi | Status |
|---|---|---|---|
| `confirm.end_session` | End the session and send the report? | सत्र संपवून अहवाल पाठवायचा? | needs_review |
| `confirm.end_session_device` | A device is still in progress. It will be marked ABANDONED. End the session? | एक डिव्हाइस अजून चालू आहे. ते 'अपूर्ण सोडले' म्हणून नोंदवले जाईल. सत्र संपवायचे? | needs_review |
| `confirm.reject_device` | Reject this device? It must go to the reject box. | हे डिव्हाइस नाकारायचे? ते रिजेक्ट बॉक्समध्ये जाईल. | needs_review |
| `confirm.reject_for` | Reject this device because of: {check}? | या कारणाने डिव्हाइस नाकारायचे: {check}? | needs_review |
| `confirm.mark_failed` | Mark "{check}" as FAILED? The device will be rejected. | "{check}" अयशस्वी नोंदवायचे? डिव्हाइस नाकारले जाईल. | needs_review |
| `confirm.reset_counters` | Reset the live counters to zero? The history is kept. | चालू काउंटर शून्य करायचे? इतिहास जतन राहील. | needs_review |

## counter (`counter.*`, 5)

| Key | English | Marathi | Status |
|---|---|---|---|
| `counter.uploads_ok` | Uploads ✓ | अपलोड ✓ | needs_review |
| `counter.uploads_fail` | Uploads ✕ | अपलोड ✕ | needs_review |
| `counter.completed` | Completed | पूर्ण | needs_review |
| `counter.rejected` | Rejected | नाकारलेले | needs_review |
| `counter.failures_adjusted` | Failures removed | कमी केलेले अपयश | needs_review |

## device_status (`device_status.*`, 4)

| Key | English | Marathi | Status |
|---|---|---|---|
| `device_status.in_progress` | In progress | चालू आहे | needs_review |
| `device_status.complete` | Complete | पूर्ण | needs_review |
| `device_status.rejected` | Rejected | नाकारले | needs_review |
| `device_status.abandoned` | Abandoned | अपूर्ण सोडले | needs_review |

## drawer (`drawer.*`, 7)

| Key | English | Marathi | Status |
|---|---|---|---|
| `drawer.title` | This session | हे सत्र | needs_review |
| `drawer.devices` | Devices this session | या सत्रातील डिव्हाइसेस | needs_review |
| `drawer.no_devices` | No devices yet | अजून डिव्हाइस नाही | needs_review |
| `drawer.counters` | Uploads ✓ {ok}   ✕ {fail}<br>Completed {done}   Rejected {rejected} | अपलोड ✓ {ok}   ✕ {fail}<br>पूर्ण {done}   नाकारलेले {rejected} | needs_review |
| `drawer.ambient` | Ambient {value} °C | वातावरण {value} °C | needs_review |
| `drawer.ambient_unknown` | Ambient not measured yet | वातावरण तापमान अजून मोजले नाही | needs_review |
| `drawer.rejected_at` | {status} (box {box}) | {status} (बॉक्स {box}) | needs_review |

## Session summary (`end.*`, 20)

| Key | English | Marathi | Status |
|---|---|---|---|
| `end.title` | Session summary | सत्र सारांश | needs_review |
| `end.subtitle` | {operator} · session {session} · station {station} | {operator} · सत्र {session} · स्टेशन {station} | needs_review |
| `end.devices` | Devices started | सुरू केलेली डिव्हाइसेस | needs_review |
| `end.complete` | Completed | पूर्ण | needs_review |
| `end.rejected` | Rejected (total) | नाकारलेली (एकूण) | needs_review |
| `end.rejected_stage` | Rejected at {letter} - {stage} | {letter} - {stage} येथे नाकारलेली | needs_review |
| `end.abandoned` | Abandoned | अपूर्ण सोडलेली | needs_review |
| `end.uploads_ok` | Uploads succeeded | यशस्वी अपलोड | needs_review |
| `end.uploads_fail` | Uploads failed | अयशस्वी अपलोड | needs_review |
| `end.failures_adjusted` | Failures removed | कमी केलेले अपयश | needs_review |
| `end.yield` | First-pass yield | पहिल्याच प्रयत्नात यश | needs_review |
| `end.yield_value` | {value} % | {value} % | needs_review |
| `end.yield_none` | - | - | needs_review |
| `end.closing` | Closing the session and writing the report… | सत्र बंद करून अहवाल लिहित आहे… | needs_review |
| `end.sending` | Sending the report e-mail… | अहवाल ई-मेल पाठवत आहे… | needs_review |
| `end.sent` | Report sent ✓ | अहवाल पाठवला ✓ | needs_review |
| `end.saved_retry` | No connection - report saved, it will be sent automatically later | कनेक्शन नाही - अहवाल जतन केला, नंतर आपोआप पाठवला जाईल | needs_review |
| `end.saved_local` | Report saved on this PC (e-mail is switched off) | अहवाल या PC वर जतन केला (ई-मेल बंद आहे) | needs_review |
| `end.report_error` | The report file could not be written - tell the supervisor (data is safe) | अहवाल फाइल लिहिता आली नाही - सुपरवायझरला सांगा (माहिती सुरक्षित आहे) | needs_review |
| `end.report_files` | Report: {files} | अहवाल: {files} | needs_review |

## Error messages (title / cause / fix steps) (`error.*`, 109)

| Key | English | Marathi | Status |
|---|---|---|---|
| `error.hw_com_disconnected.title` | Board not connected | बोर्ड जोडलेला नाही | needs_review |
| `error.hw_com_disconnected.cause` | The USB connection to the board was lost. | बोर्डचे USB कनेक्शन तुटले. | needs_review |
| `error.hw_com_disconnected.action` | Check the USB cable at both ends.<br>Press Refresh ports.<br>Select the board's port and press Try again. | USB केबल दोन्ही बाजूंनी तपासा.<br>'पोर्ट रिफ्रेश करा' दाबा.<br>बोर्डचा पोर्ट निवडा आणि 'पुन्हा प्रयत्न करा' दाबा. | needs_review |
| `error.hw_no_port.title` | No board found | बोर्ड सापडला नाही | needs_review |
| `error.hw_no_port.cause` | No serial port for the board was found. | बोर्डसाठी सिरियल पोर्ट सापडला नाही. | needs_review |
| `error.hw_no_port.action` | Plug in the board's USB cable.<br>Press Refresh ports. | बोर्डची USB केबल लावा.<br>'पोर्ट रिफ्रेश करा' दाबा. | needs_review |
| `error.hw_port_busy.title` | Port in use | पोर्ट वापरात आहे | needs_review |
| `error.hw_port_busy.cause` | Another program is using the board's port. | दुसरा प्रोग्राम बोर्डचा पोर्ट वापरत आहे. | needs_review |
| `error.hw_port_busy.action` | Close other programs that use the port (for example a serial monitor).<br>Press Try again. | पोर्ट वापरणारे इतर प्रोग्राम बंद करा (उदा. सिरियल मॉनिटर).<br>'पुन्हा प्रयत्न करा' दाबा. | needs_review |
| `error.hw_timeout.title` | Board did not answer | बोर्डने उत्तर दिले नाही | needs_review |
| `error.hw_timeout.cause` | The board did not reply in time. | बोर्डने वेळेत उत्तर दिले नाही. | needs_review |
| `error.hw_timeout.action` | Check the cable and that the board has power.<br>Press Try again. | केबल आणि बोर्डला वीज मिळत आहे का ते तपासा.<br>'पुन्हा प्रयत्न करा' दाबा. | needs_review |
| `error.hw_device_error.title` | Board error | बोर्ड त्रुटी | needs_review |
| `error.hw_device_error.cause` | The board reported an error. | बोर्डने त्रुटी कळवली. | needs_review |
| `error.hw_device_error.action` | Unplug the board and plug it in again.<br>Press Try again.<br>If it keeps failing, reject the device. | बोर्ड काढून पुन्हा लावा.<br>'पुन्हा प्रयत्न करा' दाबा.<br>वारंवार अयशस्वी झाल्यास डिव्हाइस नाकारा. | needs_review |
| `error.hw_flash_failed.title` | Upload failed | अपलोड अयशस्वी | needs_review |
| `error.hw_flash_failed.cause` | The firmware could not be written to the board. | फर्मवेअर बोर्डवर लिहिता आले नाही. | needs_review |
| `error.hw_flash_failed.action` | Keep the board connected.<br>Press Retry upload. | बोर्ड जोडलेला ठेवा.<br>'पुन्हा अपलोड करा' दाबा. | needs_review |
| `error.hw_hold_boot.title` | Hold the BOOT button | BOOT बटण दाबून ठेवा | needs_review |
| `error.hw_hold_boot.cause` | This board needs the BOOT button to start programming. | प्रोग्रामिंग सुरू करण्यासाठी या बोर्डला BOOT बटण लागते. | needs_review |
| `error.hw_hold_boot.action` | Press and hold the BOOT button on the board.<br>Press Try again.<br>Release BOOT when the progress bar starts. | बोर्डवरील BOOT बटण दाबून ठेवा.<br>'पुन्हा प्रयत्न करा' दाबा.<br>प्रगती पट्टी सुरू झाल्यावर BOOT सोडा. | needs_review |
| `error.api_unreachable.title` | Server not reachable | सर्व्हरशी संपर्क होत नाही | needs_review |
| `error.api_unreachable.cause` | The Parkomate server could not be reached. | Parkomate सर्व्हरशी संपर्क झाला नाही. | needs_review |
| `error.api_unreachable.action` | Check the network cable or Wi-Fi of this PC.<br>Press Try again.<br>If it continues, call the supervisor. | या PC ची नेटवर्क केबल किंवा Wi-Fi तपासा.<br>'पुन्हा प्रयत्न करा' दाबा.<br>तरीही चालू राहिल्यास सुपरवायझरला बोलवा. | needs_review |
| `error.api_unauthorised.title` | Server refused this station | सर्व्हरने हे स्टेशन नाकारले | needs_review |
| `error.api_unauthorised.cause` | The station's access key was rejected. | स्टेशनची ॲक्सेस की नाकारली गेली. | needs_review |
| `error.api_unauthorised.action` | Call the supervisor: the server access key must be renewed. | सुपरवायझरला बोलवा: सर्व्हर ॲक्सेस की नवीन करावी लागेल. | needs_review |
| `error.api_bad_response.title` | Unexpected server reply | सर्व्हरकडून अनपेक्षित उत्तर | needs_review |
| `error.api_bad_response.cause` | The server sent data the station does not understand. | सर्व्हरने स्टेशनला न समजणारी माहिती पाठवली. | needs_review |
| `error.api_bad_response.action` | Press Try again.<br>If it continues, call the supervisor. | 'पुन्हा प्रयत्न करा' दाबा.<br>तरीही चालू राहिल्यास सुपरवायझरला बोलवा. | needs_review |
| `error.whitelist_denied.title` | Device not authorised | डिव्हाइस अधिकृत नाही | needs_review |
| `error.whitelist_denied.cause` | This board's MAC address is not on the server list. | या बोर्डचा MAC पत्ता सर्व्हर यादीत नाही. | needs_review |
| `error.whitelist_denied.action` | Reject the device.<br>Give it to the supervisor. | डिव्हाइस नाकारा.<br>ते सुपरवायझरकडे द्या. | needs_review |
| `error.fw_hash_mismatch.title` | Firmware damaged | फर्मवेअर खराब आहे | needs_review |
| `error.fw_hash_mismatch.cause` | The downloaded firmware failed its integrity check. | डाउनलोड केलेले फर्मवेअर तपासणीत अयशस्वी झाले. | needs_review |
| `error.fw_hash_mismatch.action` | Press Try again to download it again.<br>If it continues, call the supervisor. | पुन्हा डाउनलोड करण्यासाठी 'पुन्हा प्रयत्न करा' दाबा.<br>तरीही चालू राहिल्यास सुपरवायझरला बोलवा. | needs_review |
| `error.fw_not_loaded.title` | Firmware not ready | फर्मवेअर तयार नाही | needs_review |
| `error.fw_not_loaded.cause` | The firmware has not been downloaded yet. | फर्मवेअर अजून डाउनलोड झालेले नाही. | needs_review |
| `error.fw_not_loaded.action` | Wait until the firmware is loaded.<br>Press Try again. | फर्मवेअर लोड होईपर्यंत थांबा.<br>'पुन्हा प्रयत्न करा' दाबा. | needs_review |
| `error.meas_timeout.title` | No measurement received | मापन मिळाले नाही | needs_review |
| `error.meas_timeout.cause` | The measuring device did not send values within {seconds} seconds. | मापन उपकरणाने {seconds} सेकंदांत मूल्ये पाठवली नाहीत. | needs_review |
| `error.meas_timeout.action` | Check that the measuring device is switched on and connected to Wi-Fi.<br>Check the test clips on the board.<br>Press Measure again. | मापन उपकरण चालू आहे आणि Wi-Fi ला जोडलेले आहे का ते तपासा.<br>बोर्डवरील टेस्ट क्लिप्स तपासा.<br>'पुन्हा मोजा' दाबा. | needs_review |
| `error.meas_bad_data.title` | Measurement unreadable | मापन वाचता आले नाही | needs_review |
| `error.meas_bad_data.cause` | The measuring device sent incomplete or invalid data. | मापन उपकरणाने अपूर्ण किंवा चुकीची माहिती पाठवली. | needs_review |
| `error.meas_bad_data.action` | Press Measure again.<br>If it continues, restart the measuring device. | 'पुन्हा मोजा' दाबा.<br>तरीही चालू राहिल्यास मापन उपकरण पुन्हा सुरू करा. | needs_review |
| `error.cam_not_found.title` | Camera not found | कॅमेरा सापडला नाही | needs_review |
| `error.cam_not_found.cause` | The QR camera is not connected or is used by another program. | QR कॅमेरा जोडलेला नाही किंवा दुसरा प्रोग्राम तो वापरत आहे. | needs_review |
| `error.cam_not_found.action` | Check the camera's USB cable.<br>Press Try again. | कॅमेऱ्याची USB केबल तपासा.<br>'पुन्हा प्रयत्न करा' दाबा. | needs_review |
| `error.qr_unreadable.title` | QR code not readable | QR कोड वाचता आला नाही | needs_review |
| `error.qr_unreadable.cause` | The camera could not read the QR sticker. | कॅमेऱ्याला QR स्टिकर वाचता आला नाही. | needs_review |
| `error.qr_unreadable.action` | Hold the sticker flat inside the frame, about 10 cm from the camera.<br>Avoid glare from lights.<br>Press Scan again. | स्टिकर फ्रेममध्ये सपाट, कॅमेऱ्यापासून सुमारे 10 सेमी अंतरावर धरा.<br>दिव्यांची चमक टाळा.<br>'पुन्हा स्कॅन करा' दाबा. | needs_review |
| `error.qr_bad_format.title` | Wrong QR code | चुकीचा QR कोड | needs_review |
| `error.qr_bad_format.cause` | The code read is not a valid device ID. | वाचलेला कोड वैध डिव्हाइस ID नाही. | needs_review |
| `error.qr_bad_format.action` | Check that the correct QR sticker is used.<br>Press Scan again. | योग्य QR स्टिकर वापरला आहे का ते तपासा.<br>'पुन्हा स्कॅन करा' दाबा. | needs_review |
| `error.id_write_failed.title` | Could not set device ID | डिव्हाइस ID सेट करता आला नाही | needs_review |
| `error.id_write_failed.cause` | The board did not accept the new ID. | बोर्डने नवीन ID स्वीकारला नाही. | needs_review |
| `error.id_write_failed.action` | Keep the board connected.<br>Press Try again.<br>If it continues, reject the device. | बोर्ड जोडलेला ठेवा.<br>'पुन्हा प्रयत्न करा' दाबा.<br>तरीही चालू राहिल्यास डिव्हाइस नाकारा. | needs_review |
| `error.mail_failed.title` | E-mail not sent | ई-मेल पाठवला नाही | needs_review |
| `error.mail_failed.cause` | The report e-mail could not be sent. It is saved and will be sent later. | अहवाल ई-मेल पाठवता आला नाही. तो जतन केला आहे आणि नंतर पाठवला जाईल. | needs_review |
| `error.mail_failed.action` | No action is needed now.<br>If this repeats, tell the supervisor. | आत्ता काही करण्याची गरज नाही.<br>हे वारंवार होत असल्यास सुपरवायझरला सांगा. | needs_review |
| `error.mail_not_configured.title` | E-mail not set up | ई-मेल सेट केलेला नाही | needs_review |
| `error.mail_not_configured.cause` | Report e-mail is switched off or incomplete in the settings. | सेटिंग्जमध्ये अहवाल ई-मेल बंद आहे किंवा अपूर्ण आहे. | needs_review |
| `error.mail_not_configured.action` | Reports are saved on this PC.<br>Ask the supervisor to set up e-mail. | अहवाल या PC वर जतन केले आहेत.<br>ई-मेल सेट करण्यासाठी सुपरवायझरला सांगा. | needs_review |
| `error.db_error.title` | Data could not be saved | माहिती जतन करता आली नाही | needs_review |
| `error.db_error.cause` | The station's database reported an error. | स्टेशनच्या डेटाबेसने त्रुटी कळवली. | needs_review |
| `error.db_error.action` | Do not continue with this device.<br>Restart the application.<br>If it continues, call the supervisor. | या डिव्हाइसचे काम पुढे चालू ठेवू नका.<br>ॲप्लिकेशन पुन्हा सुरू करा.<br>तरीही चालू राहिल्यास सुपरवायझरला बोलवा. | needs_review |
| `error.settings_invalid.title` | Settings problem | सेटिंग्जमध्ये समस्या | needs_review |
| `error.settings_invalid.cause` | The settings contain an error. | सेटिंग्जमध्ये त्रुटी आहे. | needs_review |
| `error.settings_invalid.action` | Call the supervisor to correct the settings. | सेटिंग्ज दुरुस्त करण्यासाठी सुपरवायझरला बोलवा. | needs_review |
| `error.secret_missing.title` | Password not stored | पासवर्ड जतन केलेला नाही | needs_review |
| `error.secret_missing.cause` | A required password or key ({name}) is missing on this PC. | आवश्यक पासवर्ड किंवा की ({name}) या PC वर नाही. | needs_review |
| `error.secret_missing.action` | Ask the supervisor to store it with: python -m parkomate secrets set {name} | सुपरवायझरला हे वापरून जतन करायला सांगा: python -m parkomate secrets set {name} | needs_review |
| `error.report_failed.title` | Report not created | अहवाल तयार झाला नाही | needs_review |
| `error.report_failed.cause` | The report file could not be written. | अहवाल फाइल लिहिता आली नाही. | needs_review |
| `error.report_failed.action` | Check that the disk is not full.<br>Export the report again from the admin area. | डिस्क भरलेली नाही ना ते तपासा.<br>ॲडमिन विभागातून अहवाल पुन्हा एक्सपोर्ट करा. | needs_review |
| `error.auth_invalid_credentials.title` | Login failed | लॉगिन अयशस्वी | needs_review |
| `error.auth_invalid_credentials.cause` | Operator ID or password is wrong. | ऑपरेटर ID किंवा पासवर्ड चुकीचा आहे. | needs_review |
| `error.auth_invalid_credentials.action` | Check your operator ID.<br>Type the password again. | तुमचा ऑपरेटर ID तपासा.<br>पासवर्ड पुन्हा टाइप करा. | needs_review |
| `error.auth_locked.title` | Account locked | खाते लॉक झाले | needs_review |
| `error.auth_locked.cause` | Too many wrong passwords. Locked for {minutes} more minute(s). | खूप वेळा चुकीचा पासवर्ड. अजून {minutes} मिनिटे लॉक. | needs_review |
| `error.auth_locked.action` | Wait {minutes} minute(s) and try again.<br>Or ask the supervisor to unlock your account. | {minutes} मिनिटे थांबा आणि पुन्हा प्रयत्न करा.<br>किंवा खाते अनलॉक करण्यासाठी सुपरवायझरला सांगा. | needs_review |
| `error.auth_inactive.title` | Account switched off | खाते बंद आहे | needs_review |
| `error.auth_inactive.cause` | This operator account is deactivated. | हे ऑपरेटर खाते निष्क्रिय केले आहे. | needs_review |
| `error.auth_inactive.action` | Ask the supervisor. | सुपरवायझरला विचारा. | needs_review |
| `error.auth_weak_password.title` | Password too short | पासवर्ड खूप लहान आहे | needs_review |
| `error.auth_weak_password.cause` | The password must have at least {min} characters. | पासवर्डमध्ये किमान {min} अक्षरे हवीत. | needs_review |
| `error.auth_weak_password.action` | Choose a longer password. | जास्त लांब पासवर्ड निवडा. | needs_review |
| `error.auth_duplicate_operator.title` | Operator ID already used | ऑपरेटर ID आधीच वापरात आहे | needs_review |
| `error.auth_duplicate_operator.cause` | Another operator already has the ID {code}. | {code} हा ID आधीच दुसऱ्या ऑपरेटरकडे आहे. | needs_review |
| `error.auth_duplicate_operator.action` | Choose a different operator ID. | वेगळा ऑपरेटर ID निवडा. | needs_review |
| `error.permission_denied.title` | Not allowed | परवानगी नाही | needs_review |
| `error.permission_denied.cause` | Only a supervisor (admin) can do this. | हे फक्त सुपरवायझर (ॲडमिन) करू शकतात. | needs_review |
| `error.permission_denied.action` | Ask the supervisor. | सुपरवायझरला विचारा. | needs_review |
| `error.invalid_state.title` | Action not possible now | ही कृती आत्ता शक्य नाही | needs_review |
| `error.invalid_state.cause` | This step cannot be done at this point of the process. | प्रक्रियेच्या या टप्प्यावर ही पायरी करता येत नाही. | needs_review |
| `error.invalid_state.action` | Follow the steps on the screen.<br>If the screen looks wrong, call the supervisor. | स्क्रीनवरील पायऱ्या पाळा.<br>स्क्रीन चुकीची वाटल्यास सुपरवायझरला बोलवा. | needs_review |
| `error.invalid_input.title` | Invalid value | चुकीचे मूल्य | needs_review |
| `error.invalid_input.cause` | The value entered has the wrong format. | टाकलेल्या मूल्याचे स्वरूप चुकीचे आहे. | needs_review |
| `error.invalid_input.action` | Check the value and enter it again. | मूल्य तपासा आणि पुन्हा टाका. | needs_review |
| `error.not_found.title` | Not found | सापडले नाही | needs_review |
| `error.not_found.cause` | The requested record does not exist. | मागितलेली नोंद अस्तित्वात नाही. | needs_review |
| `error.not_found.action` | Refresh the screen and try again. | स्क्रीन रिफ्रेश करा आणि पुन्हा प्रयत्न करा. | needs_review |
| `error.unexpected.title` | Unexpected problem | अनपेक्षित समस्या | needs_review |
| `error.unexpected.cause` | Something went wrong in the application. | ॲप्लिकेशनमध्ये काहीतरी चुकले. | needs_review |
| `error.unexpected.action` | Press Try again.<br>If it continues, restart the application and tell the supervisor. | 'पुन्हा प्रयत्न करा' दाबा.<br>तरीही चालू राहिल्यास ॲप्लिकेशन पुन्हा सुरू करा आणि सुपरवायझरला सांगा. | needs_review |
| `error.details` | Code: {code}<br>Details: {message} | कोड: {code}<br>तपशील: {message} | needs_review |
| `error.already_running.title` | Already running | आधीच चालू आहे | needs_review |
| `error.already_running.cause` | Parkomate Station is already open on this PC. | या PC वर Parkomate स्टेशन आधीच उघडे आहे. | needs_review |
| `error.already_running.action` | Close this message.<br>Use the station window that is already open (check the taskbar). | हा संदेश बंद करा.<br>आधीच उघडलेली स्टेशन विंडो वापरा (टास्कबार तपासा). | needs_review |

## fatal (`fatal.*`, 1)

| Key | English | Marathi | Status |
|---|---|---|---|
| `fatal.location` | Location: {path} | ठिकाण: {path} | needs_review |

## Why a button is disabled (`gate.*`, 15)

| Key | English | Marathi | Status |
|---|---|---|---|
| `gate.plug_board` | Plug in the board, then press Refresh ports | बोर्ड लावा, मग 'पोर्ट रिफ्रेश करा' दाबा | needs_review |
| `gate.select_port` | Choose the board's port in step 1 | पायरी 1 मध्ये बोर्डचा पोर्ट निवडा | needs_review |
| `gate.connecting` | Connecting to the board… | बोर्डशी जोडत आहे… | needs_review |
| `gate.checking_whitelist` | Checking the device with the server… | सर्व्हरकडे डिव्हाइस तपासत आहे… | needs_review |
| `gate.firmware_loading` | Waiting for the firmware to load… | फर्मवेअर लोड होण्याची वाट पाहत आहे… | needs_review |
| `gate.uploading` | Uploading - keep the board connected | अपलोड चालू आहे - बोर्ड जोडलेला ठेवा | needs_review |
| `gate.testing_comm` | Testing communication… | कम्युनिकेशन तपासत आहे… | needs_review |
| `gate.reading_sensor` | Reading the sensor… | सेन्सर वाचत आहे… | needs_review |
| `gate.mark_sensor_indicator` | Mark the sensor readings and the indicator light | सेन्सर रीडिंग्ज आणि इंडिकेटर लाइट नोंदवा | needs_review |
| `gate.waiting_measurement` | Waiting for the measuring device… {s} s | मापन उपकरणाची वाट पाहत आहे… {s} से. | needs_review |
| `gate.scanning` | Reading the QR code… | QR कोड वाचत आहे… | needs_review |
| `gate.configuring_device` | Configuring the device ID… | डिव्हाइस ID सेट करत आहे… | needs_review |
| `gate.tick_all` | Tick all {n} checks to continue | पुढे जाण्यासाठी सर्व {n} तपासण्या टिक करा | needs_review |
| `gate.tick_more` | Tick {n} more check(s) to continue | पुढे जाण्यासाठी आणखी {n} तपासणी टिक करा | needs_review |
| `gate.admin_device_busy` | Finish or reject the device on the bench first | आधी बेंचवरील डिव्हाइस पूर्ण करा किंवा नाकारा | needs_review |

## id_method (`id_method.*`, 2)

| Key | English | Marathi | Status |
|---|---|---|---|
| `id_method.camera` | Camera | कॅमेरा | needs_review |
| `id_method.manual` | Typed by hand | हाताने टाइप केले | needs_review |

## identity (`identity.*`, 5)

| Key | English | Marathi | Status |
|---|---|---|---|
| `identity.match` | Match ✓ | जुळते ✓ | needs_review |
| `identity.write_required` | Configuring device… | डिव्हाइस सेट करत आहे… | needs_review |
| `identity.confirmed` | Updated and confirmed ✓ | अपडेट करून खात्री केली ✓ | needs_review |
| `identity.failed` | Failed ✕ | अयशस्वी ✕ | needs_review |
| `identity.qr_bad_format` | Code {value} is not a valid device ID | कोड {value} हा वैध डिव्हाइस ID नाही | needs_review |

## info (`info.*`, 7)

| Key | English | Marathi | Status |
|---|---|---|---|
| `info.device_none` | No device on the bench | बेंचवर डिव्हाइस नाही | needs_review |
| `info.device_mac` | Device {mac} | डिव्हाइस {mac} | needs_review |
| `info.device_id` | Device {id}  ({mac}) | डिव्हाइस {id}  ({mac}) | needs_review |
| `info.operator` | {name} ({code}) | {name} ({code}) | needs_review |
| `info.session_time` | Session {time} | सत्र {time} | needs_review |
| `info.operator_time` | {name} ({code})  ·  session {time} | {name} ({code})  ·  सत्र {time} | needs_review |
| `info.counters` | Uploads ✓ {ok}  ✕ {fail}   ·   Completed {done}   ·   Rejected {rejected} | अपलोड ✓ {ok}  ✕ {fail}   ·   पूर्ण {done}   ·   नाकारलेले {rejected} | needs_review |

## key (`key.*`, 8)

| Key | English | Marathi | Status |
|---|---|---|---|
| `key.enter` | Enter | Enter | needs_review |
| `key.esc` | Esc | Esc | needs_review |
| `key.f1` | F1 | F1 | needs_review |
| `key.f2` | F2 | F2 | needs_review |
| `key.f3` | F3 | F3 | needs_review |
| `key.f4` | F4 | F4 | needs_review |
| `key.f5` | F5 | F5 | needs_review |
| `key.f9` | F9 | F9 | needs_review |

## Labeling screen (`label.*`, 8)

| Key | English | Marathi | Status |
|---|---|---|---|
| `label.checklist_title` | C - Labeling checklist | C - लेबलिंग यादी | needs_review |
| `label.qr_title` | QR code | QR कोड | needs_review |
| `label.decoded` | Read: | वाचले: | needs_review |
| `label.manual_flag` | typed by hand | हाताने टाइप केले | needs_review |
| `label.identity_title` | Device identity | डिव्हाइस ओळख | needs_review |
| `label.board_id` | ID in the board | बोर्डमधील ID | needs_review |
| `label.qr_id` | ID on the QR sticker | QR स्टिकरवरील ID | needs_review |
| `label.reading_board` | Reading board… | बोर्ड वाचत आहे… | needs_review |

## language (`language.*`, 2)

| Key | English | Marathi | Status |
|---|---|---|---|
| `language.en` | English | English | needs_review |
| `language.mr` | मराठी | मराठी | needs_review |

## Login (`login.*`, 8)

| Key | English | Marathi | Status |
|---|---|---|---|
| `login.station` | Station {station} | स्टेशन {station} | needs_review |
| `login.operator_id` | Operator ID | ऑपरेटर ID | needs_review |
| `login.operator_id_hint` | e.g. OP12 | उदा. OP12 | needs_review |
| `login.password` | Password | पासवर्ड | needs_review |
| `login.password_hint` | Your password | तुमचा पासवर्ड | needs_review |
| `login.checking` | Checking… | तपासत आहे… | needs_review |
| `login.measuring_ambient` | Measuring ambient temperature… | वातावरण तापमान मोजत आहे… | needs_review |
| `login.ambient_result` | Ambient temperature {value} °C ✓ | वातावरण तापमान {value} °C ✓ | needs_review |

## E-mail (`mail.*`, 3)

| Key | English | Marathi | Status |
|---|---|---|---|
| `mail.subject` | Station {station} - session {session} report ({date}) | स्टेशन {station} - सत्र {session} अहवाल ({date}) | needs_review |
| `mail.intro` | Production summary for station {station}, session {session}. The full report is attached. | स्टेशन {station}, सत्र {session} चा उत्पादन सारांश. संपूर्ण अहवाल सोबत जोडला आहे. | needs_review |
| `mail.footer` | Sent automatically by Parkomate Station. | Parkomate Station कडून आपोआप पाठवले. | needs_review |

## manual (`manual.*`, 5)

| Key | English | Marathi | Status |
|---|---|---|---|
| `manual.title` | Type the ID printed under the QR code - twice | QR कोडखाली छापलेला ID टाइप करा - दोन वेळा | needs_review |
| `manual.first` | Device ID | डिव्हाइस ID | needs_review |
| `manual.second` | Device ID again | डिव्हाइस ID पुन्हा | needs_review |
| `manual.mismatch` | The two entries are different - type them again | दोन्ही नोंदी वेगळ्या आहेत - पुन्हा टाइप करा | needs_review |
| `manual.bad_format` | This is not a valid device ID | हा वैध डिव्हाइस ID नाही | needs_review |

## mock (`mock.*`, 1)

| Key | English | Marathi | Status |
|---|---|---|---|
| `mock.badge` | SIMULATED · {scenario} | सिम्युलेटेड · {scenario} | needs_review |

## notice (`notice.*`, 3)

| Key | English | Marathi | Status |
|---|---|---|---|
| `notice.abandoned_title` | Last device was not finished - it has been marked abandoned | मागील डिव्हाइस पूर्ण झाले नव्हते - ते 'अपूर्ण सोडले' म्हणून नोंदवले आहे | needs_review |
| `notice.abandoned_body` | The station stopped unexpectedly. {n} unfinished device(s) were recorded as abandoned and the session report was saved. Put such a board aside for re-testing. | स्टेशन अचानक बंद झाले. {n} अपूर्ण डिव्हाइस 'अपूर्ण सोडले' म्हणून नोंदवले आणि सत्र अहवाल जतन केला. असा बोर्ड पुन्हा चाचणीसाठी बाजूला ठेवा. | needs_review |
| `notice.recovered_title` | The last session was closed automatically after an unexpected stop | अचानक बंद झाल्यानंतर मागील सत्र आपोआप बंद केले | needs_review |

## outbox_status (`outbox_status.*`, 3)

| Key | English | Marathi | Status |
|---|---|---|---|
| `outbox_status.pending` | Waiting to send | पाठवणे बाकी | needs_review |
| `outbox_status.sent` | Sent | पाठवले | needs_review |
| `outbox_status.failed` | Failed | अयशस्वी | needs_review |

## Packaging screen (`pack.*`, 2)

| Key | English | Marathi | Status |
|---|---|---|---|
| `pack.checklist_title` | D - Packaging checklist | D - पॅकेजिंग यादी | needs_review |
| `pack.device_title` | Device | डिव्हाइस | needs_review |

## Programming screen (`prog.*`, 27)

| Key | English | Marathi | Status |
|---|---|---|---|
| `prog.steps_title` | A - Programming | A - प्रोग्रामिंग | needs_review |
| `prog.step.connect` | Connect board | बोर्ड जोडा | needs_review |
| `prog.step.authorised` | Device authorised | डिव्हाइस अधिकृत | needs_review |
| `prog.step.firmware` | Firmware ready | फर्मवेअर तयार | needs_review |
| `prog.step.upload` | Upload | अपलोड | needs_review |
| `prog.choose_port` | - choose port - | - पोर्ट निवडा - | needs_review |
| `prog.chip` | Chip: {chip} | चिप: {chip} | needs_review |
| `prog.mac` | MAC {mac} | MAC {mac} | needs_review |
| `prog.mac_unknown` | MAC - (connect the board) | MAC - (बोर्ड जोडा) | needs_review |
| `prog.whitelist.checking` | Asking the server… | सर्व्हरला विचारत आहे… | needs_review |
| `prog.whitelist.allowed` | Allowed by the server ✓ | सर्व्हरने परवानगी दिली ✓ | needs_review |
| `prog.whitelist.denied` | NOT allowed by the server ✕ | सर्व्हरने परवानगी दिली नाही ✕ | needs_review |
| `prog.whitelist.error` | Server could not be asked | सर्व्हरला विचारता आले नाही | needs_review |
| `prog.firmware.loading` | Downloading firmware… | फर्मवेअर डाउनलोड होत आहे… | needs_review |
| `prog.firmware.error` | Firmware could not be loaded | फर्मवेअर लोड झाले नाही | needs_review |
| `prog.firmware.info` | {name}  version {version} | {name}  आवृत्ती {version} | needs_review |
| `prog.firmware.hash_ok` | ✓ Hash verified | ✓ हॅश तपासला | needs_review |
| `prog.elapsed` | Time {s} s | वेळ {s} से. | needs_review |
| `prog.attempt` | Attempt {n} of {total} | प्रयत्न {total} पैकी {n} | needs_review |
| `prog.result_title` | Result | निकाल | needs_review |
| `prog.result.waiting` | Not uploaded yet | अजून अपलोड केले नाही | needs_review |
| `prog.result.uploading` | Uploading… {pct} % | अपलोड होत आहे… {pct} % | needs_review |
| `prog.result.pass` | Firmware uploaded and verified | फर्मवेअर अपलोड आणि तपासले | needs_review |
| `prog.result.fail` | {reason} - attempt {n} of {total} | {reason} - प्रयत्न {total} पैकी {n} | needs_review |
| `prog.adjust.question` | Remove 1 failure from count for this device? | या डिव्हाइससाठी अपयशाची संख्या 1 ने कमी करायची? | needs_review |
| `prog.adjust.help` | The retry succeeded. Answer once - this cannot be changed later. | पुनर्प्रयत्न यशस्वी झाला. एकदाच उत्तर द्या - नंतर बदलता येणार नाही. | needs_review |
| `prog.counters_title` | Upload counters | अपलोड काउंटर | needs_review |

## Reject screen and reasons (`reject.*`, 16)

| Key | English | Marathi | Status |
|---|---|---|---|
| `reject.place_in_box` | Place device in the {stage} reject box ({box}) | डिव्हाइस {stage} रिजेक्ट बॉक्समध्ये ({box}) ठेवा | needs_review |
| `reject.reason.manual` | {check}: rejected by operator | {check}: ऑपरेटरने नाकारले | needs_review |
| `reject.reason.item_missing` | {check}: not done or part missing | {check}: झाले नाही किंवा भाग गहाळ | needs_review |
| `reject.reason.whitelist_denied` | MAC {mac} is not authorised by the server | MAC {mac} ला सर्व्हरची परवानगी नाही | needs_review |
| `reject.reason.upload_failed` | Firmware upload failed | फर्मवेअर अपलोड अयशस्वी | needs_review |
| `reject.reason.upload_failed_max` | Firmware upload failed {attempts} times | फर्मवेअर अपलोड {attempts} वेळा अयशस्वी | needs_review |
| `reject.reason.comm_failed` | Board did not answer the communication test | बोर्डने कम्युनिकेशन चाचणीला उत्तर दिले नाही | needs_review |
| `reject.reason.operator_marked_fail` | {check} marked as failed by the operator | ऑपरेटरने {check} अयशस्वी म्हणून नोंदवले | needs_review |
| `reject.reason.out_of_range` | {check} {value} {unit} - allowed {low}-{high} {unit} | {check} {value} {unit} - परवानगी {low}-{high} {unit} | needs_review |
| `reject.reason.value_missing` | {check}: no value received | {check}: मूल्य मिळाले नाही | needs_review |
| `reject.reason.ambient_missing` | {check}: ambient temperature was not measured | {check}: वातावरण तापमान मोजले नाही | needs_review |
| `reject.reason.temp_too_high` | {check} {value} °C - max {limit} °C (ambient {ambient} °C + {margin} °C) | {check} {value} °C - कमाल {limit} °C (वातावरण {ambient} °C + {margin} °C) | needs_review |
| `reject.reason.id_sync_failed` | Device ID could not be set: QR {qr}, device {device} | डिव्हाइस ID सेट झाला नाही: QR {qr}, डिव्हाइस {device} | needs_review |
| `reject.choose_item` | Which item failed? | कोणती गोष्ट अयशस्वी झाली? | needs_review |
| `reject.headline` | REJECT | नाकारले | needs_review |
| `reject.box_caption` | Box | बॉक्स | needs_review |

## Report headings (`report.*`, 62)

| Key | English | Marathi | Status |
|---|---|---|---|
| `report.sheet.summary` | Summary | सारांश | needs_review |
| `report.sheet.devices` | Devices | डिव्हाइसेस | needs_review |
| `report.sheet.checks` | Checks | तपासण्या | needs_review |
| `report.sheet.rejections` | Rejections | नाकारलेली | needs_review |
| `report.sheet.device` | Device | डिव्हाइस | needs_review |
| `report.col.field` | Field | तपशील | needs_review |
| `report.col.value` | Value | मूल्य | needs_review |
| `report.col.session_n` | Session {id} | सत्र {id} | needs_review |
| `report.col.row_id` | Row | क्रमांक | needs_review |
| `report.col.session_id` | Session | सत्र | needs_review |
| `report.col.device_id` | Device ID (QR) | डिव्हाइस ID (QR) | needs_review |
| `report.col.mac` | MAC address | MAC पत्ता | needs_review |
| `report.col.firmware_version` | Firmware | फर्मवेअर | needs_review |
| `report.col.started` | Started | सुरुवात | needs_review |
| `report.col.finished` | Finished | समाप्त | needs_review |
| `report.col.duration_s` | Duration (s) | कालावधी (से.) | needs_review |
| `report.col.status` | Status | स्थिती | needs_review |
| `report.col.programming_attempts` | Upload attempts | अपलोड प्रयत्न | needs_review |
| `report.col.upload_failures` | Upload failures | अपलोड अपयश | needs_review |
| `report.col.id_method` | ID entry | ID नोंद पद्धत | needs_review |
| `report.col.reject_stage` | Reject stage | नाकारण्याचा टप्पा | needs_review |
| `report.col.reject_check` | Failed check | अयशस्वी तपासणी | needs_review |
| `report.col.reject_reason` | Reason | कारण | needs_review |
| `report.col.reject_box` | Box | बॉक्स | needs_review |
| `report.col.check_value` | {check} - value | {check} - मूल्य | needs_review |
| `report.col.check_limits` | {check} - limits | {check} - मर्यादा | needs_review |
| `report.col.check_result` | {check} - result | {check} - निकाल | needs_review |
| `report.col.stage` | Stage | टप्पा | needs_review |
| `report.col.check_code` | Check code | तपासणी कोड | needs_review |
| `report.col.check_name` | Check | तपासणी | needs_review |
| `report.col.unit` | Unit | एकक | needs_review |
| `report.col.limit_low` | Low limit | किमान मर्यादा | needs_review |
| `report.col.limit_high` | High limit | कमाल मर्यादा | needs_review |
| `report.col.limits` | Limits | मर्यादा | needs_review |
| `report.col.result` | Result | निकाल | needs_review |
| `report.col.operator_marked` | Marked by operator | ऑपरेटरने नोंदवले | needs_review |
| `report.col.time` | Time | वेळ | needs_review |
| `report.summary.session_id` | Session | सत्र | needs_review |
| `report.summary.station` | Station | स्टेशन | needs_review |
| `report.summary.operator` | Operator | ऑपरेटर | needs_review |
| `report.summary.started` | Started | सुरुवात | needs_review |
| `report.summary.ended` | Ended | समाप्त | needs_review |
| `report.summary.end_reason` | End reason | समाप्तीचे कारण | needs_review |
| `report.summary.firmware_name` | Firmware name | फर्मवेअरचे नाव | needs_review |
| `report.summary.firmware_version` | Firmware version | फर्मवेअर आवृत्ती | needs_review |
| `report.summary.firmware_sha256` | Firmware SHA-256 | फर्मवेअर SHA-256 | needs_review |
| `report.summary.ambient_initial` | Ambient at start (°C) | सुरुवातीचे वातावरण तापमान (°C) | needs_review |
| `report.summary.ambient_readings` | Ambient readings | वातावरण तापमान नोंदी | needs_review |
| `report.summary.total_devices` | Devices started | सुरू केलेली डिव्हाइसेस | needs_review |
| `report.summary.complete` | Completed | पूर्ण | needs_review |
| `report.summary.rejected_total` | Rejected (total) | नाकारलेली (एकूण) | needs_review |
| `report.summary.rejected_stage` | Rejected at {letter} - {stage} | {letter} - {stage} येथे नाकारलेली | needs_review |
| `report.summary.abandoned` | Abandoned | अपूर्ण सोडलेली | needs_review |
| `report.summary.in_progress` | Still in progress | अजून चालू | needs_review |
| `report.summary.upload_success` | Uploads succeeded | यशस्वी अपलोड | needs_review |
| `report.summary.upload_failure` | Uploads failed | अयशस्वी अपलोड | needs_review |
| `report.summary.failures_adjusted` | Failures removed after a successful retry | यशस्वी पुनर्प्रयत्नानंतर कमी केलेले अपयश | needs_review |
| `report.summary.net_upload_failure` | Upload failures (counted) | अपलोड अपयश (मोजलेले) | needs_review |
| `report.summary.counter_resets` | Counter resets | काउंटर रीसेट | needs_review |
| `report.summary.first_pass_yield` | First-pass yield (%) | पहिल्याच प्रयत्नात यश (%) | needs_review |
| `report.result.pass` | PASS | पास | needs_review |
| `report.result.fail` | FAIL | फेल | needs_review |

## role (`role.*`, 2)

| Key | English | Marathi | Status |
|---|---|---|---|
| `role.operator` | Operator | ऑपरेटर | needs_review |
| `role.admin` | Supervisor (admin) | सुपरवायझर (ॲडमिन) | needs_review |

## session_end (`session_end.*`, 3)

| Key | English | Marathi | Status |
|---|---|---|---|
| `session_end.logout` | Logged out | लॉगआउट | needs_review |
| `session_end.close` | Application closed | ॲप्लिकेशन बंद | needs_review |
| `session_end.crash_recovered` | Recovered after unexpected stop | अचानक बंद झाल्यानंतर पुनर्प्राप्त | needs_review |

## Admin settings editor (`settings.*`, 98)

| Key | English | Marathi | Status |
|---|---|---|---|
| `settings.saved` | Saved - {n} change(s), recorded in the audit log | जतन केले - {n} बदल, ऑडिट लॉगमध्ये नोंदले | needs_review |
| `settings.no_changes` | Nothing changed | काहीही बदलले नाही | needs_review |
| `settings.secrets_help` | Passwords and tokens are stored in the Windows Credential Manager, never in the settings file. | पासवर्ड आणि टोकन Windows Credential Manager मध्ये ठेवले जातात, सेटिंग्ज फाइलमध्ये कधीच नाही. | needs_review |
| `settings.secret_value` | Secret value | गुप्त मूल्य | needs_review |
| `settings.secret_state` | {name}: {state} | {name}: {state} | needs_review |
| `settings.secret_stored` | stored ✓ | जतन ✓ | needs_review |
| `settings.secret_missing` | not stored | जतन नाही | needs_review |
| `settings.secret_saved` | {name} stored in the Credential Manager | {name} Credential Manager मध्ये जतन केले | needs_review |
| `settings.err.generic` | Invalid value: {detail} | चुकीचे मूल्य: {detail} | needs_review |
| `settings.err.range_order` | {low_key} must be smaller than {high_key} | {low_key} हे {high_key} पेक्षा लहान हवे | needs_review |
| `settings.err.https_required` | Must start with https:// | https:// ने सुरू व्हायला हवे | needs_review |
| `settings.err.path_slash` | Must start with / | / ने सुरू व्हायला हवे | needs_review |
| `settings.err.ip_invalid` | Not a valid IP address | वैध IP पत्ता नाही | needs_review |
| `settings.err.regex_invalid` | Not a valid pattern: {error} | वैध पॅटर्न नाही: {error} | needs_review |
| `settings.err.email_invalid` | Invalid e-mail address: {values} | चुकीचा ई-मेल पत्ता: {values} | needs_review |
| `settings.err.email_incomplete` | Required when e-mail is switched on | ई-मेल चालू असताना आवश्यक | needs_review |
| `settings.err.greater_than_equal` | Must be at least {ge} | किमान {ge} हवे | needs_review |
| `settings.err.less_than_equal` | Must be at most {le} | जास्तीत जास्त {le} हवे | needs_review |
| `settings.err.greater_than` | Must be more than {gt} | {gt} पेक्षा जास्त हवे | needs_review |
| `settings.err.less_than` | Must be less than {lt} | {lt} पेक्षा कमी हवे | needs_review |
| `settings.err.int_parsing` | Must be a whole number | पूर्ण संख्या हवी | needs_review |
| `settings.err.float_parsing` | Must be a number | संख्या हवी | needs_review |
| `settings.err.bool_parsing` | Must be true or false | true किंवा false हवे | needs_review |
| `settings.err.literal_error` | Must be one of: {expected} | यापैकी एक हवे: {expected} | needs_review |
| `settings.err.string_pattern_mismatch` | Wrong format | चुकीचे स्वरूप | needs_review |
| `settings.err.extra_forbidden` | Unknown key (misspelt, or a secret that belongs in the Credential Manager) | अनोळखी की (चुकीचे स्पेलिंग, किंवा Credential Manager मध्ये ठेवायची गुप्त माहिती) | needs_review |
| `settings.err.missing` | Required | आवश्यक | needs_review |
| `settings.section.general` | General | सामान्य | needs_review |
| `settings.section.station` | Station | स्टेशन | needs_review |
| `settings.section.limits` | Test limits | चाचणी मर्यादा | needs_review |
| `settings.section.timeouts` | Timeouts | वेळ मर्यादा | needs_review |
| `settings.section.programming` | Programming | प्रोग्रामिंग | needs_review |
| `settings.section.server` | Parkomate server | Parkomate सर्व्हर | needs_review |
| `settings.section.measurement` | Measuring device | मापन उपकरण | needs_review |
| `settings.section.camera` | QR camera | QR कॅमेरा | needs_review |
| `settings.section.email` | Report e-mail | अहवाल ई-मेल | needs_review |
| `settings.section.reports` | Reports | अहवाल | needs_review |
| `settings.section.auth` | Login security | लॉगिन सुरक्षा | needs_review |
| `settings.section.ui` | Screen | स्क्रीन | needs_review |
| `settings.section.logging` | Logs | लॉग | needs_review |
| `settings.section.dev` | Simulation (development) | सिम्युलेशन (डेव्हलपमेंट) | needs_review |
| `settings.section.secrets` | Passwords and tokens | पासवर्ड आणि टोकन | needs_review |
| `settings.f.retention_days` | Keep sent e-mail files (days) | पाठवलेल्या ई-मेल फाइल्स ठेवा (दिवस) | needs_review |
| `settings.f.station.station_id` | Station name | स्टेशनचे नाव | needs_review |
| `settings.f.station.language` | Default language | डीफॉल्ट भाषा | needs_review |
| `settings.f.limits.v_a_low` | Point A minimum (V) | पॉइंट A किमान (V) | needs_review |
| `settings.f.limits.v_a_high` | Point A maximum (V) | पॉइंट A कमाल (V) | needs_review |
| `settings.f.limits.v_b_low` | Point B minimum (V) | पॉइंट B किमान (V) | needs_review |
| `settings.f.limits.v_b_high` | Point B maximum (V) | पॉइंट B कमाल (V) | needs_review |
| `settings.f.limits.v_c_low` | Point C minimum (V) | पॉइंट C किमान (V) | needs_review |
| `settings.f.limits.v_c_high` | Point C maximum (V) | पॉइंट C कमाल (V) | needs_review |
| `settings.f.limits.temp_margin_c` | Regulator: max °C above ambient | रेग्युलेटर: वातावरणापेक्षा कमाल °C | needs_review |
| `settings.f.limits.sensor_reading_count` | Number of sensor readings | सेन्सर रीडिंग्जची संख्या | needs_review |
| `settings.f.limits.decimals` | Decimals used for comparison | तुलनेसाठी दशांश | needs_review |
| `settings.f.timeouts.ping_s` | Communication test (s) | कम्युनिकेशन चाचणी (से.) | needs_review |
| `settings.f.timeouts.measurement_s` | Wait for measurement (s) | मोजमापाची वाट (से.) | needs_review |
| `settings.f.timeouts.api_s` | Server request (s) | सर्व्हर विनंती (से.) | needs_review |
| `settings.f.timeouts.qr_scan_s` | One QR scan (s) | एक QR स्कॅन (से.) | needs_review |
| `settings.f.programming.max_retries` | Upload attempts per device | प्रति डिव्हाइस अपलोड प्रयत्न | needs_review |
| `settings.f.server.base_url` | Server address | सर्व्हर पत्ता | needs_review |
| `settings.f.server.whitelist_path` | Whitelist path | व्हाइटलिस्ट पाथ | needs_review |
| `settings.f.server.firmware_path` | Firmware path | फर्मवेअर पाथ | needs_review |
| `settings.f.server.api_token_ref` | API token (Credential Manager name) | API टोकन (Credential Manager नाव) | needs_review |
| `settings.f.measurement.listen_host` | Listen on address | ऐकण्याचा पत्ता | needs_review |
| `settings.f.measurement.listen_port` | Listen on port | ऐकण्याचा पोर्ट | needs_review |
| `settings.f.measurement.allowed_ip` | Measuring device IP | मापन उपकरणाचा IP | needs_review |
| `settings.f.camera.index` | Camera number | कॅमेरा क्रमांक | needs_review |
| `settings.f.camera.allow_manual_entry` | Allow typing the ID by hand | ID हाताने टाइप करण्यास परवानगी | needs_review |
| `settings.f.camera.id_pattern` | Device ID pattern (regular expression) | डिव्हाइस ID पॅटर्न (regular expression) | needs_review |
| `settings.f.email.enabled` | Send report e-mail | अहवाल ई-मेल पाठवा | needs_review |
| `settings.f.email.recipients` | Recipients (comma separated) | प्राप्तकर्ते (स्वल्पविरामाने वेगळे) | needs_review |
| `settings.f.email.sender` | Sender address | पाठवणाऱ्याचा पत्ता | needs_review |
| `settings.f.email.host` | SMTP server | SMTP सर्व्हर | needs_review |
| `settings.f.email.port` | SMTP port | SMTP पोर्ट | needs_review |
| `settings.f.email.security` | Connection security | कनेक्शन सुरक्षा | needs_review |
| `settings.f.email.auth_method` | Sign-in method | साइन-इन पद्धत | needs_review |
| `settings.f.email.username` | User name (empty = sender) | वापरकर्ता नाव (रिकामे = पाठवणारा) | needs_review |
| `settings.f.email.password_ref` | Password (Credential Manager name) | पासवर्ड (Credential Manager नाव) | needs_review |
| `settings.f.email.oauth_token_ref` | OAuth token (Credential Manager name) | OAuth टोकन (Credential Manager नाव) | needs_review |
| `settings.f.email.timeout_s` | Server timeout (s) | सर्व्हर वेळ मर्यादा (से.) | needs_review |
| `settings.f.email.max_attempts` | Give up after attempts | इतक्या प्रयत्नांनंतर थांबा | needs_review |
| `settings.f.email.retry_base_s` | First retry after (s) | पहिला पुनर्प्रयत्न (से.) नंतर | needs_review |
| `settings.f.email.retry_max_s` | Longest wait between retries (s) | पुनर्प्रयत्नांमधील कमाल वेळ (से.) | needs_review |
| `settings.f.email.subject_prefix` | Subject prefix | विषयाचा उपसर्ग | needs_review |
| `settings.f.reports.format` | Report file format | अहवाल फाइल प्रकार | needs_review |
| `settings.f.reports.language` | Report language | अहवालाची भाषा | needs_review |
| `settings.f.auth.max_failed_attempts` | Wrong passwords before lock | लॉकपूर्वी चुकीचे पासवर्ड | needs_review |
| `settings.f.auth.lockout_minutes` | Lock duration (minutes) | लॉक कालावधी (मिनिटे) | needs_review |
| `settings.f.auth.min_password_length` | Minimum password length | पासवर्डची किमान लांबी | needs_review |
| `settings.f.ui.kiosk` | Full-screen kiosk mode | पूर्ण-स्क्रीन किऑस्क मोड | needs_review |
| `settings.f.ui.sound` | Sound on reject / complete | नाकारणे / पूर्ण झाल्यावर आवाज | needs_review |
| `settings.f.ui.success_toast_s` | Green banner time (s) | हिरव्या बॅनरचा वेळ (से.) | needs_review |
| `settings.f.logging.level` | Log detail level | लॉग तपशील स्तर | needs_review |
| `settings.f.logging.max_bytes` | Log file size (bytes) | लॉग फाइल आकार (बाइट्स) | needs_review |
| `settings.f.logging.backup_count` | Old log files kept | ठेवलेल्या जुन्या लॉग फाइल्स | needs_review |
| `settings.f.dev.use_mock_hardware` | Use simulated bench | सिम्युलेटेड बेंच वापरा | needs_review |
| `settings.f.dev.mock_scenario` | Simulation scenario | सिम्युलेशन प्रसंग | needs_review |
| `settings.f.dev.mock_delay_scale` | Simulation speed factor | सिम्युलेशन वेग घटक | needs_review |

## Stage names (`stage.*`, 6)

| Key | English | Marathi | Status |
|---|---|---|---|
| `stage.programming` | Programming | प्रोग्रामिंग | needs_review |
| `stage.testing` | Testing | चाचणी | needs_review |
| `stage.labeling` | Labeling | लेबलिंग | needs_review |
| `stage.packaging` | Packaging | पॅकेजिंग | needs_review |
| `stage.complete` | Complete | पूर्ण | needs_review |
| `stage.rejected` | Rejected | नाकारले | needs_review |

## starting (`starting.*`, 1)

| Key | English | Marathi | Status |
|---|---|---|---|
| `starting.text` | Starting… checking the last session | सुरू होत आहे… मागील सत्र तपासत आहे | needs_review |

## Status line (`status.*`, 25)

| Key | English | Marathi | Status |
|---|---|---|---|
| `status.word.pass` | PASS | पास | needs_review |
| `status.word.fail` | FAIL | फेल | needs_review |
| `status.word.warn` | CHECK | तपासा | needs_review |
| `status.word.working` | Working… | काम चालू… | needs_review |
| `status.word.pending` | Waiting | प्रतीक्षा | needs_review |
| `status.word.info` | Info | माहिती | needs_review |
| `status.word.done` | Done ✓ | झाले ✓ | needs_review |
| `status.word.uploading` | Uploading… | अपलोड होत आहे… | needs_review |
| `status.all_checks_done` | All checks done - press Submit and next | सर्व तपासण्या झाल्या - 'जमा करा आणि पुढे' दाबा | needs_review |
| `status.still_needed` | Still needed: {items} | अजून बाकी: {items} | needs_review |
| `status.and_more` | and {n} more | आणि आणखी {n} | needs_review |
| `status.item.readings` | sensor readings ({n} of {total}) | सेन्सर रीडिंग्ज ({total} पैकी {n}) | needs_review |
| `status.prog.looking_for_ports` | Looking for the board… | बोर्ड शोधत आहे… | needs_review |
| `status.prog.no_ports` | No board found - plug in the USB cable and press Refresh ports | बोर्ड सापडला नाही - USB केबल लावा आणि 'पोर्ट रिफ्रेश करा' दाबा | needs_review |
| `status.prog.choose_port` | More than one port found - choose the board's port | एकापेक्षा जास्त पोर्ट सापडले - बोर्डचा पोर्ट निवडा | needs_review |
| `status.prog.ready_to_connect` | Board found on {port} - press Connect board | {port} वर बोर्ड सापडला - 'बोर्ड जोडा' दाबा | needs_review |
| `status.prog.ready_to_upload` | Device authorised - press Upload firmware | डिव्हाइस अधिकृत - 'फर्मवेअर अपलोड करा' दाबा | needs_review |
| `status.prog.uploading` | Uploading firmware… {pct} % | फर्मवेअर अपलोड होत आहे… {pct} % | needs_review |
| `status.prog.upload_ok` | Firmware uploaded - press Submit and next | फर्मवेअर अपलोड झाले - 'जमा करा आणि पुढे' दाबा | needs_review |
| `status.prog.upload_failed` | Upload failed (attempt {n} of {total}) | अपलोड अयशस्वी (प्रयत्न {total} पैकी {n}) | needs_review |
| `status.test.waiting` | Measuring… {s} s left | मोजमाप चालू… {s} से. बाकी | needs_review |
| `status.label.scanning` | Hold the QR sticker in the frame | QR स्टिकर फ्रेममध्ये धरा | needs_review |
| `status.label.identity_ok` | Device ID confirmed - now finish the checklist | डिव्हाइस ID निश्चित झाला - आता यादी पूर्ण करा | needs_review |
| `status.pack.checklist` | Put each item in the box, then tick it | प्रत्येक वस्तू बॉक्समध्ये ठेवा, मग टिक करा | needs_review |
| `status.pack.ready` | All items packed - press Complete device | सर्व वस्तू पॅक झाल्या - 'डिव्हाइस पूर्ण करा' दाबा | needs_review |

## stepper (`stepper.*`, 4)

| Key | English | Marathi | Status |
|---|---|---|---|
| `stepper.done` | done | झाले | needs_review |
| `stepper.current` | current step | चालू पायरी | needs_review |
| `stepper.todo` | not started | सुरू नाही | needs_review |
| `stepper.rejected` | rejected | नाकारले | needs_review |

## Testing screen (`test.*`, 22)

| Key | English | Marathi | Status |
|---|---|---|---|
| `test.step.comm` | Communication | कम्युनिकेशन | needs_review |
| `test.step.sensor` | Sensor | सेन्सर | needs_review |
| `test.step.electrical` | Electrical | इलेक्ट्रिकल | needs_review |
| `test.comm.working` | Talking to the board… | बोर्डशी संवाद चालू… | needs_review |
| `test.comm.ok` | Board answers ✓ | बोर्ड उत्तर देतो ✓ | needs_review |
| `test.comm.fail` | Board does not answer ✕ | बोर्ड उत्तर देत नाही ✕ | needs_review |
| `test.comm.error` | Test could not run | चाचणी चालू झाली नाही | needs_review |
| `test.reading_progress` | Reading {n} of {total} | रीडिंग {total} पैकी {n} | needs_review |
| `test.mark.sensor` | Sensor readings | सेन्सर रीडिंग्ज | needs_review |
| `test.mark.sensor_help` | Do readings change when a hand moves over the sensor? | सेन्सरवर हात हलवल्यावर रीडिंग्ज बदलतात का? | needs_review |
| `test.mark.indicator` | Indicator light | इंडिकेटर लाइट | needs_review |
| `test.mark.indicator_help` | Does it light up in every colour? | तो प्रत्येक रंगात उजळतो का? | needs_review |
| `test.col.check` | Check | तपासणी | needs_review |
| `test.col.measured` | Measured | मोजलेले | needs_review |
| `test.col.allowed` | Allowed range | परवानगी मर्यादा | needs_review |
| `test.col.result` | Result | निकाल | needs_review |
| `test.allowed_range` | {low} - {high} {unit} | {low} - {high} {unit} | needs_review |
| `test.allowed_temp` | max {limit} °C (ambient + {margin}) | कमाल {limit} °C (वातावरण + {margin}) | needs_review |
| `test.allowed_temp_unknown` | max ambient + {margin} °C | कमाल वातावरण + {margin} °C | needs_review |
| `test.waiting` | Waiting for the measuring device… {s} s | मापन उपकरणाची वाट पाहत आहे… {s} से. | needs_review |
| `test.measure_error` | No valid measurement - see the message above | वैध मोजमाप मिळाले नाही - वरचा संदेश पहा | needs_review |
| `test.ambient` | Ambient {value} °C | वातावरण {value} °C | needs_review |

## toast (`toast.*`, 1)

| Key | English | Marathi | Status |
|---|---|---|---|
| `toast.device_complete` | Device {device} complete | डिव्हाइस {device} पूर्ण | needs_review |
