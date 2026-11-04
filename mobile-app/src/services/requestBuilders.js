/**
 * requestBuilders.js
 * Centralized mapping layer resolving backend field-name inconsistencies.
 * Ensures the mobile app produces 100% compliant payloads matching Django backend serializers.
 */

/**
 * Builds payload for POST /api/roster/clock-in/
 * Fields expected by backend:
 * - clock_in_uuid (uuid)
 * - roster_entry_id (uuid, optional)
 * - lat, lng (float)
 * - accuracy (float, mapped to gps_accuracy_m)
 * - client_timestamp (ISO datetime)
 * - selfie (multipart file key)
 * NOTE: is_mock is intentionally OMITTED (Amendment 3) so server records 'unknown'.
 */
export const buildClockInPayload = ({
  clockInUuid,
  rosterEntryId = null,
  lat,
  lng,
  accuracy = 10.0,
  clientTimestamp = new Date().toISOString(),
}) => {
  const payload = {
    clock_in_uuid: clockInUuid,
    lat: Number(lat),
    lng: Number(lng),
    accuracy: Number(accuracy),
    client_timestamp: clientTimestamp,
  };
  if (rosterEntryId) {
    payload.roster_entry_id = rosterEntryId;
  }
  return payload;
};

/**
 * Builds payload for POST /api/roster/clock-out/
 * Fields expected by backend:
 * - clock_out_uuid (uuid)
 * - roster_entry_id (uuid, optional)
 * - client_timestamp (ISO datetime)
 */
export const buildClockOutPayload = ({
  clockOutUuid,
  rosterEntryId = null,
  clientTimestamp = new Date().toISOString(),
}) => {
  const payload = {
    clock_out_uuid: clockOutUuid,
    client_timestamp: clientTimestamp,
  };
  if (rosterEntryId) {
    payload.roster_entry_id = rosterEntryId;
  }
  return payload;
};

/**
 * Builds payload for POST /api/housekeeping/tasks/{id}/claim/
 * Note: /claim/ performs ATOMIC conditional update.
 */
export const buildTaskClaimPayload = ({
  actionTimestamp = new Date().toISOString(),
} = {}) => ({
  action_timestamp: actionTimestamp,
});

/**
 * Builds payload for POST /api/housekeeping/tasks/{id}/photos/
 * Backend fields:
 * - client_uuid (uuid)
 * - kind ('BEFORE' | 'AFTER')
 * - captured_at (ISO datetime)
 * - lat, lng (float)
 * - gps_accuracy_m (float - Note: Backend strictly requires gps_accuracy_m, not accuracy)
 * - file (multipart file key)
 * NOTE: is_mock_location is intentionally OMITTED (Amendment 3).
 */
export const buildTaskPhotoPayload = ({
  clientUuid,
  kind = 'AFTER',
  capturedAt = new Date().toISOString(),
  lat,
  lng,
  accuracy = 10.0,
}) => ({
  client_uuid: clientUuid,
  kind: String(kind).toUpperCase(),
  captured_at: capturedAt,
  lat: Number(lat),
  lng: Number(lng),
  gps_accuracy_m: Number(accuracy),
});

/**
 * Builds payload for POST /api/housekeeping/tasks/{id}/complete/
 * Backend fields:
 * - action_timestamp (ISO datetime)
 * - expected_photo_uuids (list of UUID strings)
 */
export const buildTaskCompletePayload = ({
  actionTimestamp = new Date().toISOString(),
  expectedPhotoUuids = [],
} = {}) => {
  const payload = {
    action_timestamp: actionTimestamp,
  };
  if (expectedPhotoUuids && expectedPhotoUuids.length > 0) {
    payload.expected_photo_uuids = expectedPhotoUuids;
  }
  return payload;
};
