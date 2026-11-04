// Generate RFC4122 v4 UUID
export const generateUUID = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

// Get or generate persistent device ID
export const getDeviceId = () => {
  let deviceId = localStorage.getItem('altsan_device_id');
  if (!deviceId) {
    deviceId = `dev_${generateUUID().replace(/-/g, '').slice(0, 16)}`;
    localStorage.setItem('altsan_device_id', deviceId);
  }
  return deviceId;
};
