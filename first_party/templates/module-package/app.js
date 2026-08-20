// Copyright 2026 The Sunshine OS contributors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// A package has no browser capability, no network and no file access, and this
// is what that leaves: the DOM, and storage belonging to its own origin. It is
// enough for a real module, which is the point of the example.

const STORAGE_KEY = 'scratchpad.note';

const note = document.querySelector('#note');
const saved = document.querySelector('#saved');

note.value = localStorage.getItem(STORAGE_KEY) ?? '';

// textContent, never innerHTML: SEC-14 forbids turning data into markup, and a
// package's assets are held to it by scripts/module_package.py at install time.
function report(message) {
  saved.textContent = message;
}

note.addEventListener('input', () => {
  localStorage.setItem(STORAGE_KEY, note.value);
  report(`${note.value.length} characters kept in this profile`);
});

report('Ready.');
