# Full-Stack Notification Pipeline & Dev Tools

## PHASE 0: Setup
- [x] Create implementation ledger
- [ ] Verify existing notification code (DeviceToken table, /notifications/* routes)

## PHASE 1: iOS Permissions & Dev Tools
- [ ] Create `NotificationManager.swift` — UNUserNotificationCenter singleton
- [ ] Request authorization on app launch
- [ ] Handle foreground notification delegate callbacks
- [ ] Add Developer Tools section to SettingsView
- [ ] Add `@AppStorage("dev_welcome_notification")` toggle
- [ ] Wire welcome trigger in stockmeApp.swift onAppear
- [ ] Error display for failed token registration

## PHASE 2: Backend Telemetry & Mock Routes
- [ ] Add `NotificationErrorLog` table to database.py
- [ ] Create `routers/notifications.py`
- [ ] POST /api/v1/notifications/register — store device token
- [ ] POST /api/v1/dev/push-mock — fire mock push notification
- [ ] GET /api/v1/admin/notification-errors — stream error log
- [ ] Wrap dispatch in try-except, log to NotificationErrorLog
- [ ] Register router in main.py

## PHASE 3: Full-Stack Integration
- [ ] iOS sends device token to backend on successful APNs registration
- [ ] do-catch blocks for token sync failures
- [ ] ErrorDiagnoserView for notification errors

## PHASE 4: State Retention
- [ ] Verify Python syntax + imports
- [ ] Git add + commit
