import React, { useState, useEffect, useCallback } from 'react';
import PhotoCaptureModal from './PhotoCaptureModal.jsx';

const TaskChecklist = ({ apiBase, authHeaders, isClockedIn, gpsCoords, onNotice }) => {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [selectedTaskForPhoto, setSelectedTaskForPhoto] = useState(null);
  const [skipModalTask, setSkipModalTask] = useState(null);
  const [skipReason, setSkipReason] = useState('AREA_LOCKED');
  const [skipNotes, setSkipNotes] = useState('');
  const [actionLoading, setActionLoading] = useState(null);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/housekeeping/tasks/my-tasks/`, {
        headers: authHeaders(),
      });
      if (!res.ok) {
        // Fallback to general tasks if my-tasks is unavailable
        const fallbackRes = await fetch(`${apiBase}/housekeeping/tasks/`, {
          headers: authHeaders(),
        });
        if (fallbackRes.ok) {
          const fbData = await fallbackRes.json();
          const list = Array.isArray(fbData) ? fbData : fbData.results || [];
          setTasks(list);
          return;
        }
        throw new Error('Could not load housekeeping tasks.');
      }
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.results || [];
      setTasks(list);
    } catch (err) {
      console.warn('Housekeeping task fetch warning:', err.message);
    } finally {
      setLoading(false);
    }
  }, [apiBase, authHeaders]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // ── Action: Claim or Start Task ─────────────────────────────
  const handleStartTask = async (task) => {
    if (!isClockedIn) {
      onNotice?.('Please clock in before claiming or starting shift tasks.', 'error');
      return;
    }
    setActionLoading(task.id);
    try {
      const res = await fetch(`${apiBase}/housekeeping/tasks/${task.id}/claim/`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          action_timestamp: new Date().toISOString(),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          throw new Error('Task has already been claimed by another worker.');
        }
        throw new Error(data.error || 'Failed to claim task.');
      }
      onNotice?.(`Started "${task.name}" ✅`, 'success');
      await fetchTasks();
    } catch (err) {
      onNotice?.(err.message, 'error');
    } finally {
      setActionLoading(null);
    }
  };

  // ── Action: Complete Task ───────────────────────────────────
  const handleCompleteTask = async (task) => {
    if (!isClockedIn) {
      onNotice?.('Please clock in before marking tasks complete.', 'error');
      return;
    }
    setActionLoading(task.id);
    try {
      const res = await fetch(`${apiBase}/housekeeping/tasks/${task.id}/complete/`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          action_timestamp: new Date().toISOString(),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to complete task. Check photo evidence requirements.');
      }
      if (data.status === 'AWAITING_EVIDENCE') {
        onNotice?.(`Task marked awaiting photo evidence. Please capture photos. 📷`, 'info');
      } else {
        onNotice?.(`Task "${task.name}" completed! 🎉`, 'success');
      }
      await fetchTasks();
    } catch (err) {
      onNotice?.(err.message, 'error');
    } finally {
      setActionLoading(null);
    }
  };

  // ── Action: Skip Task ───────────────────────────────────────
  const handleSkipSubmit = async (e) => {
    e?.preventDefault();
    if (!skipModalTask) return;
    setActionLoading(skipModalTask.id);
    try {
      const res = await fetch(`${apiBase}/housekeeping/tasks/${skipModalTask.id}/skip/`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          skip_reason: skipReason,
          notes: skipNotes.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to skip task.');
      }
      onNotice?.(`Task marked skipped (${skipReason}).`, 'info');
      setSkipModalTask(null);
      setSkipNotes('');
      await fetchTasks();
    } catch (err) {
      onNotice?.(err.message, 'error');
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

  const getStatusBadge = (status) => {
    switch (status) {
      case 'PENDING':
        return <span style={{ background: '#334155', color: '#cbd5e1', padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700 }}>PENDING</span>;
      case 'IN_PROGRESS':
        return <span style={{ background: '#1d4ed8', color: '#bfdbfe', padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700 }}>IN PROGRESS</span>;
      case 'AWAITING_EVIDENCE':
        return <span style={{ background: '#b45309', color: '#fef3c7', padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700 }}>AWAITING PHOTO</span>;
      case 'DONE':
        return <span style={{ background: '#065f46', color: '#a7f3d0', padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700 }}>DONE ✅</span>;
      case 'SKIPPED':
        return <span style={{ background: '#581c87', color: '#e9d5ff', padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700 }}>SKIPPED</span>;
      default:
        return <span style={{ background: '#1e293b', color: '#94a3b8', padding: '3px 8px', borderRadius: '6px', fontSize: '11px' }}>{status}</span>;
    }
  };

  const getPhotoRequirementText = (req) => {
    if (req === 'BEFORE_AFTER') return '📷 Before & After Required';
    if (req === 'AFTER_ONLY') return '📷 After Photo Required';
    return 'No Photo Required';
  };

  return (
    <section style={{ marginTop: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div>
          <h3 style={{ fontSize: '17px', fontWeight: 800, color: '#f8fafc' }}>
            🧹 Shift Checklist & Tasks
          </h3>
          <p style={{ fontSize: '12px', color: '#94a3b8' }}>
            {tasks.length} total tasks for this shift
          </p>
        </div>
        <button
          onClick={fetchTasks}
          style={{
            background: '#1a253c',
            border: '1px solid rgba(255,255,255,0.1)',
            color: '#38bdf8',
            padding: '6px 12px',
            borderRadius: '8px',
            fontSize: '12px',
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          {loading ? 'Syncing…' : '🔄 Refresh'}
        </button>
      </div>

      {/* Filter Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '6px',
          background: '#131b2e',
          padding: '4px',
          borderRadius: '12px',
          marginBottom: '14px',
          border: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        {['ALL', 'PENDING', 'IN_PROGRESS', 'DONE'].map((f) => (
          <button
            key={f}
            onClick={() => setActiveFilter(f)}
            style={{
              flex: 1,
              padding: '6px 8px',
              border: 'none',
              borderRadius: '8px',
              background: activeFilter === f ? '#3b82f6' : 'transparent',
              color: activeFilter === f ? '#fff' : '#94a3b8',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              textTransform: 'capitalize',
            }}
          >
            {f.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Tasks List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {filteredTasks.length === 0 ? (
          <div
            style={{
              padding: '24px',
              textAlign: 'center',
              background: '#131b2e',
              borderRadius: '16px',
              border: '1px dashed rgba(255,255,255,0.1)',
              color: '#94a3b8',
              fontSize: '13px',
            }}
          >
            {loading ? 'Syncing housekeeping tasks…' : 'No tasks in this category for your current shift.'}
          </div>
        ) : (
          filteredTasks.map((task) => (
            <div
              key={task.id}
              style={{
                background: '#131b2e',
                borderRadius: '16px',
                padding: '16px',
                border: task.status === 'IN_PROGRESS' || task.status === 'AWAITING_EVIDENCE'
                  ? '1px solid rgba(59, 130, 246, 0.4)'
                  : '1px solid rgba(255, 255, 255, 0.08)',
                boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
              }}
            >
              {/* Card Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    color: '#60a5fa',
                    background: 'rgba(59, 130, 246, 0.15)',
                    padding: '3px 8px',
                    borderRadius: '6px',
                  }}
                >
                  📍 {task.area_name || task.area?.name || 'Assigned Area'}
                </span>
                {getStatusBadge(task.status)}
              </div>

              {/* Title & Desc */}
              <h4 style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
                {task.name}
              </h4>
              {task.instructions && (
                <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '10px', lineHeight: 1.4 }}>
                  {task.instructions}
                </p>
              )}

              {/* Metadata tags */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', fontSize: '11px', color: '#94a3b8', marginBottom: '12px' }}>
                <span style={{ background: '#1a253c', padding: '3px 8px', borderRadius: '6px' }}>
                  {getPhotoRequirementText(task.photo_required)}
                </span>
                {task.photos && task.photos.length > 0 && (
                  <span style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#86efac', padding: '3px 8px', borderRadius: '6px', fontWeight: 600 }}>
                    📷 {task.photos.length} photo{task.photos.length > 1 ? 's' : ''} uploaded
                  </span>
                )}
                {task.priority && (
                  <span style={{ background: '#1a253c', padding: '3px 8px', borderRadius: '6px' }}>
                    Priority: {task.priority}
                  </span>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {task.status === 'PENDING' && (
                  <button
                    onClick={() => handleStartTask(task)}
                    disabled={actionLoading === task.id}
                    style={{
                      flex: 1,
                      padding: '10px 14px',
                      background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '10px',
                      fontSize: '13px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    {actionLoading === task.id ? 'Starting…' : '▶ Claim & Start'}
                  </button>
                )}

                {(task.status === 'IN_PROGRESS' || task.status === 'AWAITING_EVIDENCE') && (
                  <>
                    <button
                      onClick={() => setSelectedTaskForPhoto(task)}
                      style={{
                        flex: 1,
                        padding: '10px 12px',
                        background: '#1a253c',
                        border: '1px solid rgba(56, 189, 248, 0.4)',
                        color: '#38bdf8',
                        borderRadius: '10px',
                        fontSize: '13px',
                        fontWeight: 700,
                        cursor: 'pointer',
                      }}
                    >
                      📷 Add Photo
                    </button>
                    <button
                      onClick={() => handleCompleteTask(task)}
                      disabled={actionLoading === task.id}
                      style={{
                        flex: 1,
                        padding: '10px 12px',
                        background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '10px',
                        fontSize: '13px',
                        fontWeight: 700,
                        cursor: 'pointer',
                      }}
                    >
                      {actionLoading === task.id ? 'Saving…' : '✅ Mark Done'}
                    </button>
                  </>
                )}

                {task.status !== 'DONE' && task.status !== 'SKIPPED' && (
                  <button
                    onClick={() => setSkipModalTask(task)}
                    style={{
                      padding: '10px 12px',
                      background: '#1f2937',
                      color: '#94a3b8',
                      border: 'none',
                      borderRadius: '10px',
                      fontSize: '12px',
                      cursor: 'pointer',
                      fontWeight: 600,
                    }}
                  >
                    Skip
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Photo Capture Modal */}
      {selectedTaskForPhoto && (
        <PhotoCaptureModal
          task={selectedTaskForPhoto}
          apiBase={apiBase}
          authHeaders={authHeaders()}
          gpsCoords={gpsCoords}
          onClose={() => setSelectedTaskForPhoto(null)}
          onPhotoUploaded={() => {
            onNotice?.('Photo evidence uploaded successfully! 📸', 'success');
            fetchTasks();
          }}
        />
      )}

      {/* Skip Reason Modal */}
      {skipModalTask && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
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
              background: '#131b2e',
              borderRadius: '20px',
              padding: '24px',
              maxWidth: '380px',
              width: '100%',
              border: '1px solid rgba(255,255,255,0.12)',
              color: 'white',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontSize: '18px', fontWeight: 800, marginBottom: '8px' }}>Skip Task</h3>
            <p style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '16px' }}>
              Why is "{skipModalTask.name}" being skipped?
            </p>

            <form onSubmit={handleSkipSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>
                  Reason Category
                </label>
                <select
                  value={skipReason}
                  onChange={(e) => setSkipReason(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: '10px',
                    background: '#1a253c',
                    color: 'white',
                    border: '1px solid rgba(255,255,255,0.1)',
                    outline: 'none',
                    fontSize: '14px',
                  }}
                >
                  <option value="AREA_LOCKED">Area Locked / Inaccessible</option>
                  <option value="RESIDENT_REQUEST">Resident Requested Later</option>
                  <option value="NO_SUPPLIES">Lack of Supplies / Equipment</option>
                  <option value="OTHER">Other Operational Reason</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>
                  Supervisor Notes (Optional)
                </label>
                <textarea
                  rows={2}
                  value={skipNotes}
                  onChange={(e) => setSkipNotes(e.target.value)}
                  placeholder="Additional details for supervisor audit…"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '10px',
                    background: '#1a253c',
                    color: 'white',
                    border: '1px solid rgba(255,255,255,0.1)',
                    outline: 'none',
                    fontSize: '13px',
                    resize: 'none',
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                <button
                  type="button"
                  onClick={() => setSkipModalTask(null)}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: '#1f2937',
                    color: '#94a3b8',
                    border: 'none',
                    borderRadius: '10px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading === skipModalTask.id}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: '#ef4444',
                    color: 'white',
                    border: 'none',
                    borderRadius: '10px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Confirm Skip
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
