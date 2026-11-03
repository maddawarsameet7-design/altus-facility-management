/**
 * Formats API errors for the login interface into distinct, clear, user-friendly messages.
 * Prevents misleading "check your credentials" messages when the network or server is down.
 */
export function getLoginErrorMessage(err) {
  // 1. Network / unreachable server error
  if (!err || !err.response || err.code === 'ERR_NETWORK' || err.message === 'Network Error') {
    return 'Cannot reach the server. Please check your connection or try again later.';
  }

  const status = err.response.status;

  // 2. 429 Rate limited (Dual-throttle per-IP and per-username)
  if (status === 429) {
    const headers = err.response.headers || {};
    const retryHeader = headers['retry-after'] || headers['Retry-After'];
    let seconds = retryHeader ? parseInt(retryHeader, 10) : null;

    if (!seconds || isNaN(seconds)) {
      const detail = err.response.data?.detail || '';
      const match = String(detail).match(/(\d+)\s*seconds?/i);
      if (match) {
        seconds = parseInt(match[1], 10);
      }
    }

    if (seconds && !isNaN(seconds)) {
      return `Too many attempts. Try again in ${seconds} seconds.`;
    }
    return 'Too many attempts. Try again in 60 seconds.';
  }

  // 3. 401 / 400 Authentication or credential issues
  if (status === 401 || status === 400) {
    return 'Incorrect username or password.';
  }

  // 4. 5xx Server-side errors
  if (status >= 500 && status < 600) {
    return 'Something went wrong on our side. Please try again.';
  }

  // Fallback for other status codes
  return err.response.data?.detail || err.response.data?.error || 'Something went wrong on our side. Please try again.';
}
