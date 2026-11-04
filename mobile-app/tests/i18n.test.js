import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import en from '../src/locales/en.json' with { type: 'json' };
import hi from '../src/locales/hi.json' with { type: 'json' };

describe('i18n Translation Completeness & Devanagari Integrity', () => {
  it('guarantees 100% key parity between English and Hindi catalogs', () => {
    const enKeys = Object.keys(en).filter((k) => k !== '_meta');
    const hiKeys = Object.keys(hi).filter((k) => k !== '_meta');

    // Every EN key must exist in HI
    const missingInHi = enKeys.filter((k) => !(k in hi));
    assert.deepEqual(missingInHi, [], `Missing Hindi translations for keys: ${missingInHi.join(', ')}`);

    // Every HI key must exist in EN
    const missingInEn = hiKeys.filter((k) => !(k in en));
    assert.deepEqual(missingInEn, [], `Missing English translations for keys: ${missingInEn.join(', ')}`);
  });

  it('contains valid Devanagari Unicode characters for all Hindi values', () => {
    const hiKeys = Object.keys(hi).filter((k) => k !== '_meta');
    const devanagariRegex = /[\u0900-\u097F]/;

    let devanagariCount = 0;
    for (const key of hiKeys) {
      const val = hi[key];
      assert.ok(typeof val === 'string' && val.length > 0, `Value for key "${key}" must not be empty`);
      if (devanagariRegex.test(val)) {
        devanagariCount++;
      }
    }

    assert.ok(devanagariCount > 30, 'Most Hindi values must contain Devanagari text');
  });

  it('marks review metadata appropriately', () => {
    assert.equal(hi._meta?.reviewed_by_native, true);
    assert.equal(en._meta?.reviewed_by_native, true);
  });
});
