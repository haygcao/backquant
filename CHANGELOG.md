# Changelog

## [v0.4.0] - 2026-02-28

### 🎉 Major Features

#### Data Management UI Overhaul
- **New Navigation Structure**: Added 4 tabs with icons - Data Overview, Download Config, Python Packages, Runtime Logs
- **Integrated Download Controls**: Moved manual download into Download Config page with clear scheduling info
- **Independent Logs Page**: Separated runtime logs into dedicated tab with pagination (10 items per page)
- **Python Package Management**: New page for managing Python packages in the environment

#### Enhanced Download Experience
- **Three-Phase Progress**: Download tasks now show 3 distinct phases (Download → Extract → Copy) instead of 2
- **Modal Progress Dialog**: Task progress displayed in flat, rectangular modal dialogs
- **Phase-Specific UI**: Download tasks show stage info; Analysis tasks show progress only
- **No More Freezing**: Added phase 3 "Copy files" at 98% to prevent UI freeze between extract and completion

#### Improved Logging System
- **Simplified Logs**: Only key events logged (task start, phase transitions, completion, errors)
- **Correct Source Attribution**: Auto-triggered analysis now correctly shows "auto" instead of "manual"
- **Pagination Support**: Runtime logs support page navigation with clear page indicators
- **Removed Verbose Output**: No more file counts, data counts, or line-by-line progress logs

### 🐛 Bug Fixes
- Fixed concurrent task conflict when download auto-triggers analysis
- Fixed "task already running" error after download completion
- Fixed first-time analysis showing incorrect "manual" source
- Resolved task progress UI issues with proper modal styling

### 🎨 UI/UX Improvements
- Unified all dialog styles to flat rectangular design (border-radius: 0)
- Added icons to all data management navigation tabs
- Compact layout with inline description text
- Disabled form inputs during task execution to prevent conflicts
- Success/completion notifications via proper dialogs instead of alerts

### 🔧 Technical Improvements
- Backend now accepts `source` parameter in analyze endpoint
- Task manager allows auto tasks to bypass running task check
- Optimized log recording to reduce database writes
- Better progress monitoring with phase-specific updates

### 📝 Documentation
- Updated README with latest screenshots
- Synced English README with Chinese version

### 🗂️ File Changes
- **Added**: `frontend/src/pages/MarketData/Logs.vue` - New logs page
- **Added**: `frontend/src/components/MarketData/SuccessDialog.vue` - Success notification dialog
- **Modified**: 15+ files across backend and frontend for feature improvements
- **Removed**: Standalone manual download page (integrated into config)

---

## Previous Versions

See git history for earlier releases.
