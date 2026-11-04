import React, { useState, useEffect, useCallback } from 'react';
import PhotoCaptureModal from './PhotoCaptureModal.jsx';
import { apiClient } from '../services/apiClient.js';
import { enqueueMutation, getItemsForWorker } from '../services/offlineQueue.js';
import { generateUUID } from '../utils/uuid.js';
import { useI18n } from '../context/I18nContext.jsx';

const TaskChecklist = ({ worker, isClockedIn, activeSlot, onNotice }) => {
  const { t, getFriendlyError } = useI18n();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [selectedTaskForPhoto, setSelectedTaskForPhoto] = useState(null);
  const [skipModalTask, setSkipModalTask] = useState(null);
  const [skipReason, setSkipReason] = useState('AREA_LOCKED');
  const [skipNotes, setSkipNotes] = useState('');
  const [actionLoading, setActionLoading] = useState(null);
  const [queuedTaskIds, setQueuedTaskIds] = useState(new Set());

  // Check which tasks currently have pending unconfirmed mutations in the queue
  const refreshQueuedActions = useCallback(async () => {
    if (!worker?.id) return;
    const items = await getItemsForWorker(worker.id);
    const pendingIds = new Set();
    items.forEach((item) => {
      if (item.status === 'PENDING' || item.status === 'IN_FLIGHT' || item.status === 'RETRYABLE_ERROR') {
        if (item.payload?.task_id) pendingIds.add(item.payload.task_id);
      }
    });
    setQueuedTaskIds(pendingIds);
  }, [worker?.id]);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient('/housekeeping/tasks/my-tasks/');
      if (!res.ok) {
        // Fallback to general housekeeping tasks
        const fbRes = await apiClient('/housekeeping/tasks/');
        if (fbRes.ok) {
          const fbData = await fbRes.json();
          const list = Array.isArray(fbData) ? fbData : fbData.results || [];
          setTasks(list);
          return;
        }
        throw new Error('Failed to load tasks');
      }
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.results || [];
      setTasks(list);
      await refreshQueuedActions();
    } catch (err) {
      console.warn('[TaskChecklist] Task fetch warning:', err.message);
    } finally {
      setLoading(false);
    }
  }, [refreshQueuedActions]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // ── Action: Claim or Start Task (Enqueued) ───────────────────
  const handleStartTask = async (task) => {
    if (!isClockedIn) {
      onNotice?.(t('shift_clock_in_btn') + ' - ' + t('error_contact_supervisor'), 'error');
      return;
    }
    setActionLoading(task.id);
    const clientUuid = generateUUID();

    try {
      await enqueueMutation({
        client_uuid: clientUuid,
        worker_id: worker.id,
        action_type: 'TASK_START',
        endpoint: `/housekeeping/tasks/${task.id}/claim/`,
        roster_entry_id: activeSlot?.roster_entry_id,
        payload: {
          task_id: task.id,
          action_timestamp: new Date().toISOString(),
        },
      });

      // Optimistic local UI update
      setTasks((prev) =>
        prev.map((t) => (t.id === task.id ? { ...t, status: 'IN_PROGRESS', isOptimistic: true } : t))
      );
      setQueuedTaskIds((prev) => new Set([...prev, task.id]));
      onNotice?.(t('task_status_saved_unconfirmed'), 'info');
    } catch (err) {
      onNotice?.(getFriendlyError(err), 'error');
    } finally {
      setActionLoading(null);
    }
  };

  // ── Action: Complete Task (Enqueued) ─────────────────────────
  const handleCompleteTask = async (task) => {
    if (!isClockedIn) {
      onNotice?.(t('shift_clock_in_btn'), 'error');
      return;
    }
    setActionLoading(task.id);
    const clientUuid = generateUUID();

    try {
      await enqueueMutation({
        client_uuid: clientUuid,
        worker_id: worker.id,
        action_type: 'TASK_COMPLETE',
        endpoint: `/housekeeping/tasks/${task.id}/complete/`,
        roster_entry_id: activeSlot?.roster_entry_id,
        payload: {
          task_id: task.id,
          action_timestamp: new Date().toISOString(),
        },
      });

      setTasks((prev) =>
        prev.map((t) => (t.id === task.id ? { ...t, status: 'DONE', isOptimistic: true } : t))
      );
      setQueuedTaskIds((prev) => new Set([...prev, task.id]));
      onNotice?.(t('task_status_saved_unconfirmed'), 'info');
    } catch (err) {
      onNotice?.(getFriendlyError(err), 'error');
    } finally {
      setActionLoading(null);
    }
  };

  // ── Action: Skip Task (Enqueued) ─────────────────────────────
  const handleSkipSubmit = async (e) => {
    e?.preventDefault();
    if (!skipModalTask || !worker?.id) return;
    setActionLoading(skipModalTask.id);
    const clientUuid = generateUUID();

    try {
      await enqueueMutation({
        client_uuid: clientUuid,
        worker_id: worker.id,
        action_type: 'TASK_SKIP',
        endpoint: `/housekeeping/tasks/${skipModalTask.id}/skip/`,
        roster_entry_id: activeSlot?.roster_entry_id,
        payload: {
          task_id: skipModalTask.id,
          skip_reason: skipReason,
          notes: skipNotes.trim(),
        },
      });

      setTasks((prev) =>
        prev.map((t) => (t.id === skipModalTask.id ? { ...t, status: 'SKIPPED', isOptimistic: true } : t))
      );
      setQueuedTaskIds((prev) => new Set([...prev, skipModalTask.id]));
      onNotice?.(t('task_status_saved_unconfirmed'), 'info');
      setSkipModalTask(null);
      setSkipNotes('');
    } catch (err) {
      onNotice?.(getFriendlyError(err), 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const filteredTasks = tasks.filter((t) => {
    if (activeFilter === 'ALL') return true;
    if (activeFilter === 'PENDING') return t.status === 'PENDING';
    if (activeFilter === 'IN_PROGRESS') return t.status === 'IN_PROGRESS' || t.status === 'AWAITING_EVIDENCE';
    if (activeFilter === 'DONE') return t.status === 'DONE' || t.status === 'SKIPPED';
    return true;
  });

  const getStatusBadge = (status, isQueued) => {
    if (isQueued) {
      return (
        <span className="badge-unconfirmed">
          ⏳ {t('task_status_saved_unconfirmed')}
        </span>
      );
    }
    switch (status) {
      case 'PENDING':
        return <span style={{ background: '#334155', color: '#f8fafc', padding: '4px 10px', borderRadius: '8px', fontSize: '12px', fontWeight: 800 }}>{t('task_status_pending')}</span>;
      case 'IN_PROGRESS':
        return <span style={{ background: '#1d4ed8', color: '#bfdbfe', padding: '4px 10px', borderRadius: '8px', fontSize: '12px', fontWeight: 800 }}>{t('task_status_in_progress')}</span>;
      case 'AWAITING_EVIDENCE':
        return <span style={{ background: '#b45309', color: '#fef3c7', padding: '4px 10px', borderRadius: '8px', fontSize: '12px', fontWeight: 800 }}>{t('task_status_awaiting_photo')}</span>;
      case 'DONE':
        return <span style={{ background: '#065f46', color: '#a7f3d0', padding: '4px 10px', borderRadius: '8px', fontSize: '12px', fontWeight: 800 }}>{t('task_status_done')}</span>;
      case 'SKIPPED':
        return <span style={{ background: '#581c87', color: '#e9d5ff', padding: '4px 10px', borderRadius: '8px', fontSize: '12px', fontWeight: 800 }}>{t('task_status_skipped')}</span>;
      default:
        return <span style={{ background: '#1e293b', color: '#94a3b8', padding: '4px 10px', borderRadius: '8px', fontSize: '12px' }}>{status}</span>;
    }
  };

  const getPhotoRequirementText = (req) => {
    if (req === 'BEFORE_AFTER') return t('task_photo_required_before_after');
    if (req === 'AFTER_ONLY') return t('task_photo_required_after_only');
    return t('task_photo_required_none');
  };

  return (
    <section style={{ marginTop: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div>
          <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#ffffff' }}>
            🧹 {t('tasks_title')}
          </h3>
          <p style={{ fontSize: '13px', color: '#cbd5e1' }}>
            {tasks.length} total tasks
          </p>
        </div>
        <button
          onClick={fetchTasks}
          style={{
            background: '#17223b',
            border: '1px solid rgba(255,255,255,0.2)',
            color: '#38bdf8',
            padding: '8px 14px',
            borderRadius: '10px',
            fontSize: '13px',
            cursor: 'pointer',
            fontWeight: 700,
          }}
        >
          {loading ? '…' : '🔄'}
        </button>
      </div>

      {/* Filter Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '6px',
          background: '#10172a',
          padding: '4px',
          borderRadius: '14px',
          marginBottom: '14px',
          border: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        {['ALL', 'PENDING', 'IN_PROGRESS', 'DONE'].map((f) => (
          <button
            key={f}
            onClick={() => setActiveFilter(f)}
            style={{
              flex: 1,
              padding: '8px 6px',
              border: 'none',
              borderRadius: '10px',
              background: activeFilter === f ? '#2563eb' : 'transparent',
              color: activeFilter === f ? '#ffffff' : '#cbd5e1',
              fontSize: '12px',
              fontWeight: 800,
              cursor: 'pointer',
            }}
          >
            {f === 'ALL'
              ? t('tasks_filter_all')
              : f === 'PENDING'
              ? t('tasks_filter_pending')
              : f === 'IN_PROGRESS'
              ? t('tasks_filter_in_progress')
              : t('tasks_filter_done')}
          </button>
        ))}
      </div>

      {/* Task Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {filteredTasks.length === 0 ? (
          <div
            style={{
              padding: '28px 16px',
              textAlign: 'center',
              background: '#10172a',
              borderRadius: '16px',
              border: '1px dashed rgba(255,255,255,0.2)',
              color: '#cbd5e1',
              fontSize: '14px',
            }}
          >
            {loading ? '…' : t('tasks_empty')}
          </div>
        ) : (
          filteredTasks.map((task) => {
            const isQueued = queuedTaskIds.has(task.id);
            return (
              <div
                key={task.id}
                style={{
                  background: '#10172a',
                  borderRadius: '18px',
                  padding: '18px',
                  border:
                    task.status === 'IN_PROGRESS' || task.status === 'AWAITING_EVIDENCE'
                      ? '2px solid #3b82f6'
                      : '1px solid rgba(255, 255, 255, 0.15)',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <span
                    style={{
                      fontSize: '12px',
                      fontWeight: 800,
                      color: '#60a5fa',
                      background: 'rgba(59, 130, 246, 0.2)',
                      padding: '4px 10px',
                      borderRadius: '8px',
                    }}
                  >
                    📍 {task.area_name || task.area?.name || 'Area'}
                  </span>
                  {getStatusBadge(task.status, isQueued)}
                </div>

                <h4 style={{ fontSize: '16px', fontWeight: 800, color: '#ffffff', marginBottom: '6px' }}>
                  {task.name}
                </h4>
                {task.instructions && (
                  <p style={{ fontSize: '13px', color: '#cbd5e1', marginBottom: '12px', lineHeight: 1.4 }}>
                    {task.instructions}
                  </p>
                )}

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', fontSize: '12px', color: '#cbd5e1', marginBottom: '14px' }}>
                  <span style={{ background: '#17223b', padding: '4px 10px', borderRadius: '8px', fontWeight: 600 }}>
                    📷 {getPhotoRequirementText(task.photo_required)}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  {task.status === 'PENDING' && (
                    <button
                      onClick={() => handleStartTask(task)}
                      disabled={actionLoading === task.id}
                      style={{
                        flex: 1,
                        padding: '12px 16px',
                        background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '12px',
                        fontSize: '14px',
                        fontWeight: 800,
                        cursor: 'pointer',
                        minHeight: '48px',
                      }}
                    >
                      {actionLoading === task.id ? '…' : `▶ ${t('task_claim_start')}`}
                    </button>
                  )}

                  {(task.status === 'IN_PROGRESS' || task.status === 'AWAITING_EVIDENCE') && (
                    <>
                      <button
                        onClick={() => setSelectedTaskForPhoto(task)}
                        style={{
                          flex: 1,
                          padding: '12px 14px',
                          background: '#17223b',
                          border: '2px solid #38bdf8',
                          color: '#38bdf8',
                          borderRadius: '12px',
                          fontSize: '13px',
                          fontWeight: 800,
                          cursor: 'pointer',
                          minHeight: '48px',
                        }}
                      >
                        📷 {t('task_add_photo')}
                      </button>
                      <button
                        onClick={() => handleCompleteTask(task)}
                        disabled={actionLoading === task.id}
                        style={{
                          flex: 1,
                          padding: '12px 14px',
                          background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
                          color: 'white',
                          border: 'none',
                          borderRadius: '12px',
                          fontSize: '13px',
                          fontWeight: 800,
                          cursor: 'pointer',
                          minHeight: '48px',
                        }}
                      >
                        {actionLoading === task.id ? '…' : `✅ ${t('task_mark_done')}`}
                      </button>
                    </>
                  )}

                  {task.status !== 'DONE' && task.status !== 'SKIPPED' && (
                    <button
                      onClick={() => setSkipModalTask(task)}
                      style={{
                        padding: '12px 14px',
                        background: '#1e293b',
                        color: '#cbd5e1',
                        border: 'none',
                        borderRadius: '12px',
                        fontSize: '13px',
                        cursor: 'pointer',
                        fontWeight: 700,
                        minHeight: '48px',
                      }}
                    >
                      {t('task_skip')}
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Photo Capture Modal */}
      {selectedTaskForPhoto && (
        <PhotoCaptureModal
          task={selectedTaskForPhoto}
          worker={worker}
          onClose={() => setSelectedTaskForPhoto(null)}
          onPhotoQueued={() => {
            onNotice?.(t('task_status_saved_unconfirmed'), 'info');
            refreshQueuedActions();
          }}
        />
      )}

      {/* Skip Modal */}
      {skipModalTask && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.85)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            zIndex: 1000,
          }}
          onClick={() => setSkipModalTask(null)}
        >
          <div
            style={{
              background: '#10172a',
              borderRadius: '20px',
              padding: '24px',
              maxWidth: '380px',
              width: '100%',
              border: '1px solid rgba(255,255,255,0.2)',
              color: 'white',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontSize: '18px', fontWeight: 800, marginBottom: '8px' }}>{t('task_skip')}</h3>
            <p style={{ fontSize: '13px', color: '#cbd5e1', marginBottom: '16px' }}>{skipModalTask.name}</p>

            <form onSubmit={handleSkipSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <select
                  value={skipReason}
                  onChange={(e) => setSkipReason(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: '10px',
                    background: '#17223b',
                    color: 'white',
                    border: '1px solid rgba(255,255,255,0.2)',
                    fontSize: '14px',
                    outline: 'none',
                  }}
                >
                  <option value="AREA_LOCKED">Area Locked / ताला लगा है</option>
                  <option value="RESIDENT_REQUEST">Resident Request / निवासी का अनुरोध</option>
                  <option value="NO_SUPPLIES">Lack of Supplies / सामान की कमी</option>
                  <option value="OTHER">Other / अन्य कारण</option>
                </select>
              </div>

              <div>
                <textarea
                  rows={2}
                  value={skipNotes}
                  onChange={(e) => setSkipNotes(e.target.value)}
                  placeholder="Notes for supervisor / सुपरवाइजर के लिए विवरण…"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '10px',
                    background: '#17223b',
                    color: 'white',
                    border: '1px solid rgba(255,255,255,0.2)',
                    fontSize: '13px',
                    outline: 'none',
                    resize: 'none',
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setSkipModalTask(null)}
                  style={{ flex: 1, padding: '12px', background: '#1e293b', color: '#cbd5e1', border: 'none', borderRadius: '10px', fontWeight: 700 }}
                >
                  रद्द करें
                </button>
                <button
                  type="submit"
                  disabled={actionLoading === skipModalTask.id}
                  style={{ flex: 1, padding: '12px', background: '#dc2626', color: 'white', border: 'none', borderRadius: '10px', fontWeight: 800 }}
                >
                  छोड़ें
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
};

export default TaskChecklist;
