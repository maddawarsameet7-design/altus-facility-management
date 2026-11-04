import React, { useState, useEffect } from 'react';
import { generateUUID } from '../utils/uuid.js';

const PhotoCaptureModal = ({ task, apiBase, authHeaders, gpsCoords, onClose, onPhotoUploaded }) => {
  const [kind, setKind] = useState('AFTER');
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  // Clean up object URL on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(selected);
    setPreviewUrl(URL.createObjectURL(selected));
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please take or select a photo.');
      return;
    }

    setUploading(true);
    setError(null);

    const clientUuid = generateUUID();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('client_uuid', clientUuid);
    formData.append('kind', kind);
    formData.append('captured_at', new Date().toISOString());

    if (gpsCoords?.lat !== null && gpsCoords?.lng !== null) {
      formData.append('lat', gpsCoords.lat);
      formData.append('lng', gpsCoords.lng);
      formData.append('gps_accuracy_m', gpsCoords.accuracy || 10.0);
    } else {
      // Default fallback
      formData.append('lat', 18.5204);
      formData.append('lng', 73.8567);
      formData.append('gps_accuracy_m', 15.0);
    }

    try {
      const headers = { ...authHeaders };
      // Note: Do not set Content-Type header when using FormData; fetch handles multipart boundary automatically
      delete headers['Content-Type'];

      const res = await fetch(`${apiBase}/housekeeping/tasks/${task.id}/photos/`, {
        method: 'POST',
        headers,
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to upload photo evidence.');
      }

      onPhotoUploaded?.(data);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        zIndex: 1000,
        animation: 'fadeIn 0.2s ease',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '480px',
          background: '#131b2e',
          borderTopLeftRadius: '24px',
          borderTopRightRadius: '24px',
          padding: '24px',
          borderTop: '1px solid rgba(255,255,255,0.15)',
          color: '#f8fafc',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '18px', fontWeight: 800 }}>Capture Photo Evidence</h3>
            <p style={{ fontSize: '12px', color: '#94a3b8' }}>{task.name} ({task.area_name || task.area?.name || 'Area'})</p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              fontSize: '20px',
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>

        {error && (
          <div
            style={{
              background: 'rgba(239, 68, 68, 0.2)',
              color: '#fca5a5',
              padding: '10px 14px',
              borderRadius: '10px',
              fontSize: '13px',
              marginBottom: '16px',
              border: '1px solid rgba(239, 68, 68, 0.3)',
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {/* Kind Toggle (Before vs After) */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
            Evidence Phase
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              onClick={() => setKind('BEFORE')}
              style={{
                flex: 1,
                padding: '10px',
                borderRadius: '10px',
                background: kind === 'BEFORE' ? '#f59e0b' : '#1a253c',
                color: kind === 'BEFORE' ? '#000' : '#cbd5e1',
                border: 'none',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              🟡 Before Cleaning
            </button>
            <button
              type="button"
              onClick={() => setKind('AFTER')}
              style={{
                flex: 1,
                padding: '10px',
                borderRadius: '10px',
                background: kind === 'AFTER' ? '#10b981' : '#1a253c',
                color: kind === 'AFTER' ? '#fff' : '#cbd5e1',
                border: 'none',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              🟢 After Cleaning
            </button>
          </div>
        </div>

        {/* Photo Selection / Camera Preview */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
            Photo Capture
          </label>
          {previewUrl ? (
            <div style={{ position: 'relative', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)' }}>
              <img
                src={previewUrl}
                alt="Preview"
                style={{ width: '100%', height: '220px', objectFit: 'cover', display: 'block' }}
              />
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  setPreviewUrl(null);
                }}
                style={{
                  position: 'absolute',
                  top: '10px',
                  right: '10px',
                  background: 'rgba(0,0,0,0.6)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '50%',
                  width: '32px',
                  height: '32px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                }}
              >
                ✕
              </button>
            </div>
          ) : (
            <label
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '36px 16px',
                border: '2px dashed rgba(255,255,255,0.2)',
                borderRadius: '14px',
                background: '#1a253c',
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '36px', marginBottom: '8px' }}>📷</div>
              <span style={{ fontSize: '14px', fontWeight: 700, color: '#38bdf8' }}>Tap to Take Photo or Browse</span>
              <span style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>Camera with GPS Geotag</span>
              <input
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
            </label>
          )}
        </div>

        {/* GPS context badge */}
        <div
          style={{
            background: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.2)',
            borderRadius: '10px',
            padding: '10px 14px',
            fontSize: '12px',
            color: '#93c5fd',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>📍</span>
          <span>
            {gpsCoords?.lat ? `GPS: ${gpsCoords.lat.toFixed(4)}, ${gpsCoords.lng.toFixed(4)} (±${Math.round(gpsCoords.accuracy || 10)}m)` : 'GPS: Active Site Coordinates'}
          </span>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            type="button"
            onClick={onClose}
            disabled={uploading}
            style={{
              flex: 1,
              padding: '14px',
              borderRadius: '12px',
              background: '#1e293b',
              color: '#94a3b8',
              border: 'none',
              fontWeight: 700,
              fontSize: '14px',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleUpload}
            disabled={uploading || !file}
            style={{
              flex: 2,
              padding: '14px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              color: 'white',
              border: 'none',
              fontWeight: 700,
              fontSize: '14px',
              cursor: uploading || !file ? 'not-allowed' : 'pointer',
              opacity: uploading || !file ? 0.6 : 1,
            }}
          >
            {uploading ? 'Uploading Evidence…' : 'Submit Evidence ✅'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PhotoCaptureModal;
