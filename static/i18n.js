/**
 * SCLM i18n — Translation engine
 * 
 * Usage in app.js:  t('key')  or  t('key', {items: 5, participants: 10})
 * Usage in HTML:    data-i18n="key"  (text content)
 *                   data-i18n-ph="key"  (placeholder)
 * 
 * Language files:  /static/lang/de.json  (default)
 *                  /static/lang/en.json  (fallback + English)
 * 
 * The active language is saved to localStorage as 'sclm_lang'.
 * English is always loaded as fallback; missing keys fall back to EN,
 * and if still missing, the key itself is returned.
 */

'use strict';

// ── State ────────────────────────────────────────────────────────────────────
let _lang = 'de';       // active language code
let _tr   = {};         // active translations
let _trEn = {};         // English fallback (always loaded)

// ── Core API ─────────────────────────────────────────────────────────────────

/** Translate a key, optionally interpolating {placeholder} values. */
function t(key, vars) {
  let val = _tr[key] ?? _trEn[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      val = val.replaceAll(`{${k}}`, v);
    }
  }
  return val;
}

/** Current language code ('de' or 'en'). */
function getLang() { return _lang; }

// ── Init & switching ──────────────────────────────────────────────────────────

async function _fetchLang(code) {
  try {
    const r = await fetch(`/static/lang/${code}.json?v=1`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    console.warn(`[i18n] Could not load ${code}.json:`, e.message);
    return {};
  }
}

/**
 * Load language files and apply translations.
 * Call once on page load — await it before rendering anything.
 */
async function initLang() {
  // Always load English as fallback
  _trEn = await _fetchLang('en');

  // Restore saved preference, default to 'de'
  let saved = 'de';
  try { saved = localStorage.getItem('sclm_lang') || 'de'; } catch (_) {}
  _lang = (saved === 'en') ? 'en' : 'de';

  _tr = (_lang === 'en') ? _trEn : await _fetchLang('de');

  _applyDOM();
  _updateButtons();
}

/**
 * Switch language at runtime.
 * @param {'de'|'en'} lang
 */
async function setLang(lang) {
  _lang = (lang === 'en') ? 'en' : 'de';
  try { localStorage.setItem('sclm_lang', _lang); } catch (_) {}

  _tr = (_lang === 'en') ? _trEn : await _fetchLang('de');

  _updateButtons();

  // Re-render dynamic content first, then re-apply DOM translations
  if (typeof onLangChange === 'function') {
    const result = onLangChange(_lang);
    // If onLangChange returns a Promise, wait for it before applying DOM
    if (result && typeof result.then === 'function') {
      result.then(() => _applyDOM());
    } else {
      // Small delay to let synchronous DOM mutations settle
      setTimeout(() => _applyDOM(), 0);
    }
  } else {
    _applyDOM();
  }
}

// ── DOM helpers ───────────────────────────────────────────────────────────────

/** Apply translations to all [data-i18n] and [data-i18n-ph] elements. */
function applyLangToDOM() { _applyDOM(); }

function _applyDOM() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPh);
  });
}

function _updateButtons() {
  const de = document.getElementById('lang-de');
  const en = document.getElementById('lang-en');
  if (de) de.className = 'btn btn-sm' + (_lang === 'de' ? ' btn-acc' : '');
  if (en) en.className = 'btn btn-sm' + (_lang === 'en' ? ' btn-acc' : '');
}
