import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeApiUrl } from '../src/utils/api.js';

describe('API URL Normalization', () => {
  it('normalizes root domain to end with /api/', () => {
    assert.equal(normalizeApiUrl('https://api.altsan.com'), 'https://api.altsan.com/api/');
    assert.equal(normalizeApiUrl('http://localhost:8000'), 'http://localhost:8000/api/');
  });

  it('normalizes URLs with trailing slashes correctly', () => {
    assert.equal(normalizeApiUrl('https://api.altsan.com/'), 'https://api.altsan.com/api/');
    assert.equal(normalizeApiUrl('http://localhost:8000///'), 'http://localhost:8000/api/');
  });

  it('preserves existing /api without duplicate /api/api', () => {
    assert.equal(normalizeApiUrl('https://api.altsan.com/api'), 'https://api.altsan.com/api/');
    assert.equal(normalizeApiUrl('https://api.altsan.com/api/'), 'https://api.altsan.com/api/');
    assert.equal(normalizeApiUrl('http://localhost:8000/api'), 'http://localhost:8000/api/');
    assert.equal(normalizeApiUrl('http://localhost:8000/api/'), 'http://localhost:8000/api/');
  });
});
