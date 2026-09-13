// Copyright 2026 The Sunshine Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef SUNSHINE_INSTALLER_RESOURCE_H_
#define SUNSHINE_INSTALLER_RESOURCE_H_

// The embedded engine. `mini_installer.exe`, exactly as upstream built it,
// carried as an opaque blob. IU-2: the front-end runs it and never replaces it.
#define IDR_ENGINE 101

#define IDI_SETUP 103

#define IDD_SETUP 200
#define IDC_HEADLINE 1002
#define IDC_LOCATION_EDIT 1003
#define IDC_SCOPE_USER 1004
#define IDC_SCOPE_MACHINE 1005
#define IDC_DESKTOP_SHORTCUT 1006
#define IDC_TASKBAR_SHORTCUT 1007
#define IDC_QUICK_LAUNCH_SHORTCUT 1008
#define IDC_MAKE_DEFAULT 1009
#define IDC_LAUNCH_WHEN_DONE 1010
#define IDC_INSTALL 1011
#define IDC_STATUS 1012

// The install root a person chooses, and what is made inside it. IU-4 as the
// owner revised it: the location is typed, and the note under the box is the
// only thing on screen that says what will actually exist afterwards.
#define IDC_BROWSE 1013
#define IDC_LOCATION_NOTE 1014

// The three pages. IU-20: one window, shown once, whose contents change --
// rather than three dialogs, which would make "was the dialog shown" have
// three answers and IU-15 unenforceable.
//
// IDC_PROGRESS is a marquee and cannot be anything else: `mini_installer.exe`
// reports no progress to anybody, so a bar that filled would be reporting a
// number this program invented. IU-21.
#define IDC_PROGRESS 1015
#define IDC_RESULT 1016
#define IDC_CLOSE 1017

#endif  // SUNSHINE_INSTALLER_RESOURCE_H_
