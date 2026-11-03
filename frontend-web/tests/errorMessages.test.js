import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { getLoginErrorMessage } from '../src/utils/errorMessages.js';

describe('Login Error Message Formatting', () => {

  it('handles server unreachable / network failure without blaming credentials', () => {
    // Case 1: No response object (network drop / ECONNREFUSED)
    const errNetwork1 = new Error('Network Error');
    errNetwork1.code = 'ERR_NETWORK';
    assert.equal(
      getLoginErrorMessage(errNetwork1),
      'Cannot reach the server. Please check your connection or try again later.'
    );

    // Case 2: err without response
    const errNetwork2 = { message: 'Failed to fetch' };
    assert.equal(
      getLoginErrorMessage(errNetwork2),
      'Cannot reach the server. Please check your connection or try again later.'
    );

    // Negative assertion: Never blame credentials
    assert.doesNotMatch(getLoginErrorMessage(errNetwork1), /credential/i);
    assert.doesNotMatch(getLoginErrorMessage(errNetwork2), /credential/i);
  });

  it('handles 429 Too Many Requests using Retry-After header', () => {
    const err429WithHeader = {
      response: {
        status: 429,
        headers: {
          'retry-after': '35',
        },
        data: {
          detail: 'Request was throttled. Expected available in 35 seconds.',
        },
      },
    };
    assert.equal(
      getLoginErrorMessage(err429WithHeader),
      'Too many attempts. Try again in 35 seconds.'
    );
  });

  it('handles 429 Too Many Requests fallback from detail regex when header missing', () => {
    const err429FromDetail = {
      response: {
        status: 429,
        headers: {},
        data: {
          detail: 'Request was throttled. Expected available in 18 seconds.',
        },
      },
    };
    assert.equal(
      getLoginErrorMessage(err429FromDetail),
      'Too many attempts. Try again in 18 seconds.'
    );
  });

  it('handles 401 and 400 with "Incorrect username or password."', () => {
    const err401 = {
      response: {
        status: 401,
        data: { detail: 'No active account found with the given credentials' },
      },
    };
    assert.equal(
      getLoginErrorMessage(err401),
      'Incorrect username or password.'
    );

    const err400 = {
      response: {
        status: 400,
        data: { error: 'Username and password required' },
      },
    };
    assert.equal(
      getLoginErrorMessage(err400),
      'Incorrect username or password.'
    );
  });

  it('handles 5xx server errors with "Something went wrong on our side. Please try again."', () => {
    const err500 = {
      response: {
        status: 500,
        data: 'Internal Server Error',
      },
    };
    assert.equal(
      getLoginErrorMessage(err500),
      'Something went wrong on our side. Please try again.'
    );

    const err502 = {
      response: {
        status: 502,
        data: 'Bad Gateway',
      },
    };
    assert.equal(
      getLoginErrorMessage(err502),
      'Something went wrong on our side. Please try again.'
    );
  });
});
