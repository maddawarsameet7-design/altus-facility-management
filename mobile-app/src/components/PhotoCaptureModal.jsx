import React, { useState } from 'react';
import { captureCompressedPhoto } from '../services/nativePlugins.js';
import { enqueueMutation } from '../services/offlineQueue.js';
import { useI18n } from '../context/I18nContext.jsx';

const PhotoCaptureModal = ({ task, worker, onClose, onPhotoQueued }) => {
  const { t, getFriendlyError } = useI18n();
  const [kind, setKind] = useState('AFTER');
  const [capturedPhoto, setCapturedPhoto] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleTriggerCamera = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await captureCompressedPhoto({ type: 'TASK', kind });
      setCapturedPhoto(result);
    } catch (err) {
      setError(getFriendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAndEnqueue = async () => {
    if (!capturedPhoto || !worker?.id) return;
    setLoading(true);
    setError(null);

    try {
      await enqueueMutation({
        client_uuid: capturedPhoto.client_uuid,
        worker_id: worker.id,
        action_type: 'PHOTO_UPLOAD',
        endpoint: `/housekeeping/tasks/${task.id}/photos/`,
        method: 'POST',
        payload: {
          client_uuid: capturedPhoto.client_uuid,
          kind: capturedPhoto.kind,
          lat: capturedPhoto.lat,
          lng: capturedPhoto.lng,
          gps_accuracy_m: capturedPhoto.accuracy,
          captured_at: capturedPhoto.captured_at,
          task_id: task.id,
        },
        captured_at: capturedPhoto.captured_at,
        is_multipart: true,
        file_blob: capturedPhoto.blob,
      });

      onPhotoQueued?.(capturedPhoto);
      onClose();
    } catch (err) {
      setError(getFriendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.85)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '480px',
          background: '#10172a',
          borderTopLeftRadius: '24px',
          borderTopRightRadius: '24px',
          padding: '24px',
          borderTop: '1px solid rgba(255,255,255,0.2)',
          color: '#ffffff',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '18px', fontWeight: 800 }}>{t('task_add_photo')}</h3>
            <p style={{ fontSize: '13px', color: '#cbd5e1' }}>{task.name}</p>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: '24px', cursor: 'pointer' }}
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
              border: '1px solid rgba(239, 68, 68, 0.4)',
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {/* Kind Toggle */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              onClick={() => setKind('BEFORE')}
              style={{
                flex: 1,
                padding: '12px',
                borderRadius: '12px',
                background: kind === 'BEFORE' ? '#d97706' : '#17223b',
                color: '#ffffff',
                border: '1px solid rgba(255,255,255,0.1)',
                fontWeight: 800,
                fontSize: '14px',
                cursor: 'pointer',
              }}
            >
              {t('task_photo_before')}
            </button>
            <button
              type="button"
              onClick={() => setKind('AFTER')}
              style={{
                flex: 1,
                padding: '12px',
                borderRadius: '12px',
                background: kind === 'AFTER' ? '#059669' : '#17223b',
                color: '#ffffff',
                border: '1px solid rgba(255,255,255,0.1)',
                fontWeight: 800,
                fontSize: '14px',
                cursor: 'pointer',
              }}
            >
              {t('task_photo_after')}
            </button>
          </div>
        </div>

        {/* Shutter Camera Trigger / Preview */}
        <div style={{ marginBottom: '20px' }}>
          {capturedPhoto?.web_preview ? (
            <div style={{ position: 'relative', borderRadius: '16px', overflow: 'hidden', border: '2px solid #10b981' }}>
              <img
                src={capturedPhoto.web_preview}
                alt="Captured Evidence"
                style={{ width: '100%', height: '240px', objectFit: 'cover', display: 'block' }}
              />
              <button
                type="button"
                onClick={() => setCapturedPhoto(null)}
                style={{
                  position: 'absolute',
                  top: '12px',
                  right: '12px',
                  background: 'rgba(0,0,0,0.7)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '50%',
                  width: '36px',
                  height: '36px',
                  cursor: 'pointer',
                  fontSize: '16px',
                  fontWeight: 'bold',
                }}
              >
                ✕
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={handleTriggerCamera}
              disabled={loading}
              style={{
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '36px 16px',
                border: '2px dashed #3b82f6',
                borderRadius: '16px',
                background: '#17223b',
                cursor: 'pointer',
                color: '#ffffff',
              }}
            >
              <div style={{ fontSize: '42px', marginBottom: '8px' }}>📷</div>
              <span style={{ fontSize: '16px', fontWeight: 800, color: '#38bdf8' }}>
                {t('task_add_photo')}
              </span>
              <span style={{ fontSize: '12px', color: '#cbd5e1', marginTop: '4px' }}>
                (GPS Geotag at Shutter Time)
              </span>
            </button>
          )}
        </div>

        {capturedPhoto && (
          <div
            style={{
              background: 'rgba(59, 130, 246, 0.15)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              borderRadius: '12px',
              padding: '10px 14px',
              fontSize: '12px',
              color: '#93c5fd',
              marginBottom: '20px',
            }}
          >
            📍 GPS: {capturedPhoto.lat?.toFixed(4)}, {capturedPhoto.lng?.toFixed(4)} (±{Math.round(capturedPhoto.accuracy || 10)}m)
          </div>
        )}

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            style={{
              flex: 1,
              padding: '14px',
              borderRadius: '12px',
              background: '#1e293b',
              color: '#cbd5e1',
              border: 'none',
              fontWeight: 700,
              fontSize: '14px',
              cursor: 'pointer',
              minHeight: '48px',
            }}
          >
            रद्द करें / Cancel
          </button>
          <button
            type="button"
            onClick={handleSaveAndEnqueue}
            disabled={loading || !capturedPhoto}
            style={{
              flex: 2,
              padding: '14px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
              color: 'white',
              border: 'none',
              fontWeight: 800,
              fontSize: '15px',
              cursor: loading || !capturedPhoto ? 'not-allowed' : 'pointer',
              opacity: loading || !capturedPhoto ? 0.6 : 1,
              minHeight: '48px',
            }}
          >
            {loading ? 'सहेज रहे हैं…' : t('task_photo_upload_btn')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PhotoCaptureModal;
