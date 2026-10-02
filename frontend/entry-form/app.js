document.addEventListener('DOMContentLoaded', () => {
  // DOM References: Form
  const form = document.getElementById('entry-form');
  const btnSubmit = document.getElementById('btn-submit');
  const btnSubmitText = document.getElementById('btn-submit-text');
  const btnSpinner = document.getElementById('btn-spinner');
  const btnReset = document.getElementById('btn-reset');
  const btnPrefill = document.getElementById('btn-prefill');
  const statusBanner = document.getElementById('status-banner');
  const overallPill = document.getElementById('overall-pill');
  const agentCards = document.getElementById('agent-cards');

  // Edit Mode Elements
  const editModeBanner = document.getElementById('edit-mode-banner');
  const editModeText = document.getElementById('edit-mode-text');
  const btnCancelEdit = document.getElementById('btn-cancel-edit');
  const formHeading = document.getElementById('form-heading');
  const formSubheading = document.getElementById('form-subheading');

  // Input Fields & Counters
  const inputName = document.getElementById('project_name');
  const inputDesc = document.getElementById('description');
  const inputReqs = document.getElementById('requirements');
  const inputInfo = document.getElementById('additional_info');

  const countName = document.getElementById('count-project_name');
  const countDesc = document.getElementById('count-description');
  const countReqs = document.getElementById('count-requirements');
  const countInfo = document.getElementById('count-additional_info');

  // Stepper Elements
  const stepValidation = document.getElementById('step-validation');
  const stepAgent1 = document.getElementById('step-agent1');
  const stepAgent2 = document.getElementById('step-agent2');
  const stepAgent3 = document.getElementById('step-agent3');

  const statusValidation = document.getElementById('status-validation');
  const statusAgent1 = document.getElementById('status-agent1');
  const statusAgent2 = document.getElementById('status-agent2');
  const statusAgent3 = document.getElementById('status-agent3');

  // Agent Output Elements
  const summaryAgent1 = document.getElementById('summary-agent1');
  const pathAgent1 = document.getElementById('path-agent1');
  const tagAgent1 = document.getElementById('tag-agent1');

  const summaryAgent2 = document.getElementById('summary-agent2');
  const idAgent2 = document.getElementById('id-agent2');
  const opAgent2 = document.getElementById('op-agent2');
  const tagAgent2 = document.getElementById('tag-agent2');

  const summaryAgent3 = document.getElementById('summary-agent3');
  const pathAgent3 = document.getElementById('path-agent3');
  const tagAgent3 = document.getElementById('tag-agent3');

  // Preview Modal Elements
  const btnViewMd = document.getElementById('btn-view-md');
  const btnViewDoc = document.getElementById('btn-view-doc');
  const previewModal = document.getElementById('preview-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalCode = document.getElementById('modal-code');
  const btnCloseModal = document.getElementById('btn-close-modal');

  // Confirmation Modal Elements
  const confirmModal = document.getElementById('confirm-modal');
  const confirmTitle = document.getElementById('confirm-title');
  const confirmMessage = document.getElementById('confirm-message');
  const btnConfirmCancel = document.getElementById('btn-confirm-cancel');
  const btnConfirmProceed = document.getElementById('btn-confirm-proceed');
  const btnCloseConfirm = document.getElementById('btn-close-confirm');

  // Projects History Table & Filters
  const projectsTbody = document.getElementById('projects-tbody');
  const btnRefreshHistory = document.getElementById('btn-refresh-history');
  const btnClearAirtable = document.getElementById('btn-clear-airtable');
  const filterBtns = document.querySelectorAll('.filter-btn');

  // Application State
  let editingProjectId = null;
  let currentMarkdownPath = '';
  let currentDocPath = '';
  let currentStatusFilter = 'all';
  let confirmCallback = null;

  // =========================================================================
  // 1. Character Counters & Input Listeners
  // =========================================================================
  const fieldConfigs = [
    { input: inputName, counter: countName, max: 120 },
    { input: inputDesc, counter: countDesc, max: 5000 },
    { input: inputReqs, counter: countReqs, max: 5000 },
    { input: inputInfo, counter: countInfo, max: 3000 },
  ];

  function updateCharCounter(input, counter, max) {
    if (!counter || !input) return;
    const len = input.value.length;
    counter.textContent = `${len} / ${max}`;
    counter.classList.remove('limit-near', 'limit-reached');
    if (len >= max) {
      counter.classList.add('limit-reached');
    } else if (len >= max * 0.9) {
      counter.classList.add('limit-near');
    }
  }

  function updateAllCounters() {
    fieldConfigs.forEach(cfg => updateCharCounter(cfg.input, cfg.counter, cfg.max));
  }

  fieldConfigs.forEach(cfg => {
    if (cfg.input) {
      cfg.input.addEventListener('input', () => {
        updateCharCounter(cfg.input, cfg.counter, cfg.max);
        cfg.input.classList.remove('is-invalid');
        const errEl = document.getElementById(`err-${cfg.input.id}`);
        if (errEl) errEl.textContent = '';
      });
    }
  });

  // =========================================================================
  // 2. Pre-fill Demo Data
  // =========================================================================
  btnPrefill.addEventListener('click', () => {
    inputName.value = 'Cloud Sentinel Security Auditor';
    inputDesc.value =
      'Automated cloud infrastructure compliance monitor that continuously scans AWS and GCP environments for security misconfigurations, credential leaks, and excessive IAM privileges.';
    inputReqs.value =
      '- Ingest AWS CloudTrail and VPC Flow Logs in real time\n- Continuous CIS Benchmark compliance scanning\n- Instant webhook alerts for root account access\n- Export daily compliance summaries in Markdown and PDF\n- Sub-second querying for security analyst investigations';
    inputInfo.value =
      'Security Tier 1 application. Encrypted with AWS KMS at rest, zero outbound access without proxy. Target deployment in Q4 2026.';

    clearErrors();
    updateAllCounters();
  });

  btnReset.addEventListener('click', () => {
    setTimeout(() => {
      clearErrors();
      updateAllCounters();
      if (editingProjectId !== null) {
        exitEditMode();
      }
    }, 0);
  });

  function clearErrors() {
    ['project_name', 'description', 'requirements', 'additional_info'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.remove('is-invalid');
      const err = document.getElementById(`err-${id}`);
      if (err) err.textContent = '';
    });
  }

  // =========================================================================
  // 3. Strict Client-side Validation (Anti-spam / Anti-gibberish)
  // =========================================================================
  function checkMeaningfulText(value, fieldLabel, minLetters = 2) {
    if (!value || typeof value !== 'string') {
      return { valid: false, message: `${fieldLabel} must be a valid text string.` };
    }
    const trimmed = value.trim();

    // 1. Must contain at least minLetters alphabetic characters (rejects purely numeric or symbol inputs like "11111111111111111111111")
    const letters = trimmed.match(/[a-zA-Z]/g) || [];
    if (letters.length < minLetters) {
      return {
        valid: false,
        message: `${fieldLabel} must contain meaningful text with letters, not purely numbers or symbols.`
      };
    }

    // 2. Reject repetitive character spam (e.g. 5+ consecutive identical characters like "11111", "aaaaa", ".....")
    if (/(.)\1{4,}/.test(trimmed)) {
      return {
        valid: false,
        message: `${fieldLabel} contains excessive repetitive characters and appears invalid.`
      };
    }

    // 3. Reject low character variety / gibberish (e.g. "ababab", "121212")
    const alnum = trimmed.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (alnum.length >= 6 && new Set(alnum).size < 3) {
      return {
        valid: false,
        message: `${fieldLabel} lacks sufficient character variety and appears to be meaningless spam.`
      };
    }

    return { valid: true };
  }

  function validateForm() {
    clearErrors();
    let valid = true;

    // project_name: 2-120 chars, non-empty, meaningful string
    const nameVal = inputName.value.trim();
    if (!nameVal) {
      showFieldError('project_name', 'Project name is required and cannot be empty.');
      valid = false;
    } else if (nameVal.length < 2) {
      showFieldError('project_name', `Project name must be at least 2 characters (currently ${nameVal.length}).`);
      valid = false;
    } else if (nameVal.length > 120) {
      showFieldError('project_name', `Project name cannot exceed 120 characters (currently ${nameVal.length}).`);
      valid = false;
    } else {
      const check = checkMeaningfulText(nameVal, 'Project name', 2);
      if (!check.valid) {
        showFieldError('project_name', check.message);
        valid = false;
      }
    }

    // description: 5-5000 chars, non-empty
    const descVal = inputDesc.value.trim();
    if (!descVal) {
      showFieldError('description', 'Project description is required and cannot be empty.');
      valid = false;
    } else if (descVal.length < 5) {
      showFieldError('description', `Description must be at least 5 characters (currently ${descVal.length}).`);
      valid = false;
    } else if (descVal.length > 5000) {
      showFieldError('description', `Description cannot exceed 5000 characters (currently ${descVal.length}).`);
      valid = false;
    } else {
      const check = checkMeaningfulText(descVal, 'Description', 2);
      if (!check.valid) {
        showFieldError('description', check.message);
        valid = false;
      }
    }

    // requirements: 5-5000 chars, non-empty
    const reqsVal = inputReqs.value.trim();
    if (!reqsVal) {
      showFieldError('requirements', 'Requirements specification is required.');
      valid = false;
    } else if (reqsVal.length < 5) {
      showFieldError('requirements', `Requirements must be at least 5 characters (currently ${reqsVal.length}).`);
      valid = false;
    } else if (reqsVal.length > 5000) {
      showFieldError('requirements', `Requirements cannot exceed 5000 characters (currently ${reqsVal.length}).`);
      valid = false;
    } else {
      const check = checkMeaningfulText(reqsVal, 'Requirements', 2);
      if (!check.valid) {
        showFieldError('requirements', check.message);
        valid = false;
      }
    }

    // additional_info: max 3000 chars
    const infoVal = inputInfo.value.trim();
    if (infoVal.length > 3000) {
      showFieldError('additional_info', `Additional information cannot exceed 3000 characters (currently ${infoVal.length}).`);
      valid = false;
    } else if (infoVal.length > 0) {
      if (/(.)\1{4,}/.test(infoVal)) {
        showFieldError('additional_info', 'Additional info contains excessive repetitive characters.');
        valid = false;
      } else if (infoVal.length >= 5) {
        const letters = infoVal.match(/[a-zA-Z]/g) || [];
        if (letters.length < 2) {
          showFieldError('additional_info', 'Additional info must contain meaningful text if provided.');
          valid = false;
        }
      }
    }

    return valid;
  }

  function showFieldError(fieldId, message) {
    const el = document.getElementById(fieldId);
    if (el) el.classList.add('is-invalid');
    const err = document.getElementById(`err-${fieldId}`);
    if (err) err.textContent = message;
  }

  // =========================================================================
  // 4. Edit Mode State Machine
  // =========================================================================
  function enterEditMode(project) {
    editingProjectId = project.id;

    // Normalize requirements
    let reqsText = '';
    if (project.requirements) {
      try {
        const parsed = typeof project.requirements === 'string' ? JSON.parse(project.requirements) : project.requirements;
        if (Array.isArray(parsed)) {
          reqsText = parsed.join('\n');
        } else {
          reqsText = String(parsed);
        }
      } catch {
        reqsText = project.requirements;
      }
    }

    inputName.value = project.project_name || '';
    inputDesc.value = project.description || '';
    inputReqs.value = reqsText;
    inputInfo.value = project.additional_info || '';

    clearErrors();
    updateAllCounters();

    // UI Updates
    editModeBanner.style.display = 'flex';
    editModeText.textContent = `Editing Project #${project.id}: "${project.project_name}" (Rev v${project.version})`;
    formHeading.textContent = `Edit Project #${project.id}`;
    formSubheading.textContent = `Modify project specifications and synchronize across database, markdown, and documentation.`;
    btnSubmitText.textContent = `💾 Save & Update Project (v${(project.version || 1) + 1})`;

    // Scroll smoothly to form
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    inputName.focus();
  }

  function exitEditMode() {
    editingProjectId = null;
    editModeBanner.style.display = 'none';
    formHeading.textContent = 'Project Entry Form';
    formSubheading.textContent = 'Submit task specifications to trigger the 3-agent pipeline';
    btnSubmitText.textContent = '🚀 Run Multi-Agent Workflow';
    form.reset();
    clearErrors();
    updateAllCounters();
  }

  btnCancelEdit.addEventListener('click', () => {
    exitEditMode();
  });

  // =========================================================================
  // 5. Reset Pipeline UI
  // =========================================================================
  function resetPipelineUI() {
    [stepValidation, stepAgent1, stepAgent2, stepAgent3].forEach(step => {
      step.className = 'step';
    });

    statusValidation.textContent = 'Awaiting submission';
    statusAgent1.textContent = 'Waiting';
    statusAgent2.textContent = 'Waiting';
    statusAgent3.textContent = 'Waiting';

    overallPill.className = 'status-indicator';
    overallPill.textContent = 'Processing';
    overallPill.classList.add('active');

    statusBanner.style.display = 'none';
    agentCards.style.display = 'none';
  }

  // =========================================================================
  // 6. Submit / Update Form Handler
  // =========================================================================
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    resetPipelineUI();
    btnSubmit.disabled = true;
    btnSpinner.style.display = 'inline-block';

    const payload = {
      project_name: inputName.value.trim(),
      description: inputDesc.value.trim(),
      requirements: inputReqs.value.trim(),
      additional_info: inputInfo.value.trim()
    };

    // Step 1: Input Validation Active
    stepValidation.className = 'step running';
    statusValidation.textContent = 'Validating strict data types & constraints...';

    const isEdit = editingProjectId !== null;
    const url = isEdit ? `/api/projects/${editingProjectId}` : '/api/submit';
    const method = isEdit ? 'PUT' : 'POST';

    try {
      await new Promise(r => setTimeout(r, 150));
      stepValidation.className = 'step completed';
      statusValidation.textContent = 'Backend constraints validated';

      stepAgent1.className = 'step running';
      statusAgent1.textContent = isEdit ? 'Updating Markdown specification...' : 'Generating Markdown artifact...';

      const response = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      let result = {};
      try {
        result = await response.json();
      } catch (parseErr) {
        result = { detail: `HTTP ${response.status}: ${response.statusText}` };
      }

      if (!response.ok || result.overall_status === 'failed') {
        const errMsg = result.errors && result.errors.length ? result.errors.join('; ') : (result.detail || result.error || 'Workflow operation failed');
        throw new Error(errMsg);
      }

      // Step 2: Agent 1 Complete
      stepAgent1.className = 'step completed';
      statusAgent1.textContent = `Completed (${result.markdown_status})`;

      // Step 3: Agent 2 Complete
      stepAgent2.className = 'step completed';
      statusAgent2.textContent = `Persisted record ID #${result.database_record_id} (${result.database_status})`;

      // Step 4: Agent 3 Complete
      stepAgent3.className = 'step completed';
      statusAgent3.textContent = `Documentation synchronized (${result.documentation_status})`;

      // Update Overall Status Pill
      overallPill.className = 'status-indicator success';
      overallPill.textContent = 'Complete';

      // Update Banner
      statusBanner.className = 'banner success';
      statusBanner.style.display = 'block';
      const actionText = isEdit ? 'updated' : 'processed';
      statusBanner.innerHTML = `<strong>Success!</strong> Project <strong>${payload.project_name}</strong> was successfully ${actionText}. (Run ID: <code>${result.workflow_run_id}</code>)`;

      // Populate Agent 1 Output
      currentMarkdownPath = result.markdown_file_path;
      summaryAgent1.textContent = result.markdown_summary;
      pathAgent1.textContent = result.markdown_file_path;
      tagAgent1.textContent = result.markdown_status;

      // Populate Agent 2 Output
      summaryAgent2.textContent = result.database_operation || 'Record successfully persisted in SQLite.';
      idAgent2.textContent = `#${result.database_record_id}`;
      opAgent2.textContent = (result.database_status || 'SUCCESS').toUpperCase();
      tagAgent2.textContent = result.database_status;

      // Populate Agent 3 Output
      currentDocPath = result.documentation_file_path;
      summaryAgent3.textContent = result.documentation_summary;
      pathAgent3.textContent = result.documentation_file_path;
      tagAgent3.textContent = result.documentation_status;

      // Show Agent Result Cards
      agentCards.style.display = 'flex';

      // If we were in edit mode, exit now
      if (isEdit) {
        exitEditMode();
      }

      // Refresh table
      loadRecentProjects();

    } catch (err) {
      console.error('Workflow error:', err);
      stepValidation.className = 'step failed';
      statusValidation.textContent = 'Validation / Execution Rejected';
      stepAgent1.className = 'step';
      statusAgent1.textContent = 'Not run';
      stepAgent2.className = 'step';
      statusAgent2.textContent = 'Not run';
      stepAgent3.className = 'step';
      statusAgent3.textContent = 'Not run';

      overallPill.className = 'status-indicator error';
      overallPill.textContent = 'Rejected';

      statusBanner.className = 'banner error';
      statusBanner.style.display = 'block';
      statusBanner.innerHTML = `<strong>Submission Rejected:</strong> ${escapeHtml(err.message)}`;
    } finally {
      btnSubmit.disabled = false;
      btnSpinner.style.display = 'none';
    }
  });

  // =========================================================================
  // 7. Preview Modal
  // =========================================================================
  async function showPreview(filePath, title) {
    modalTitle.textContent = title;
    modalCode.textContent = 'Loading content...';
    previewModal.style.display = 'flex';

    try {
      const res = await fetch(`/api/preview?path=${encodeURIComponent(filePath)}`);
      const data = await res.json();
      if (res.ok) {
        modalCode.textContent = data.content;
      } else {
        modalCode.textContent = `Error loading file: ${data.detail || 'Not found'}`;
      }
    } catch (e) {
      modalCode.textContent = `Network error loading file: ${e.message}`;
    }
  }

  btnViewMd.addEventListener('click', () => {
    if (currentMarkdownPath) {
      showPreview(currentMarkdownPath, 'Markdown Artifact Preview');
    }
  });

  btnViewDoc.addEventListener('click', () => {
    if (currentDocPath) {
      showPreview(currentDocPath, 'System Documentation Preview');
    }
  });

  btnCloseModal.addEventListener('click', () => {
    previewModal.style.display = 'none';
  });

  previewModal.addEventListener('click', (e) => {
    if (e.target === previewModal) {
      previewModal.style.display = 'none';
    }
  });

  // =========================================================================
  // 8. Confirmation Dialog Modal
  // =========================================================================
  function showConfirmDialog(title, message, onProceed) {
    confirmTitle.textContent = title;
    confirmMessage.innerHTML = message;
    confirmCallback = onProceed;
    confirmModal.style.display = 'flex';
  }

  function hideConfirmDialog() {
    confirmModal.style.display = 'none';
    confirmCallback = null;
  }

  btnConfirmCancel.addEventListener('click', hideConfirmDialog);
  btnCloseConfirm.addEventListener('click', hideConfirmDialog);

  btnConfirmProceed.addEventListener('click', async () => {
    if (confirmCallback) {
      const cb = confirmCallback;
      hideConfirmDialog();
      await cb();
    }
  });

  confirmModal.addEventListener('click', (e) => {
    if (e.target === confirmModal) {
      hideConfirmDialog();
    }
  });

  // =========================================================================
  // 9. Load Recent Projects History & Actions
  // =========================================================================
  async function loadRecentProjects() {
    try {
      const filterParam = currentStatusFilter !== 'all' ? `?status=${currentStatusFilter}` : '';
      const res = await fetch(`/api/projects${filterParam}`);
      const data = await res.json();
      const projects = data.projects || [];

      if (projects.length === 0) {
        projectsTbody.innerHTML = `<tr><td colspan="7" class="text-center" style="color: #94a3b8; padding: 18px;">No ${currentStatusFilter !== 'all' ? currentStatusFilter : ''} projects found in database.</td></tr>`;
        return;
      }

      projectsTbody.innerHTML = projects.map(p => {
        const statusClass = (p.status || 'active').toLowerCase();
        const createdDate = (p.created_at || '').slice(0, 16).replace('T', ' ');
        const updatedDate = (p.updated_at || '').slice(0, 16).replace('T', ' ');

        return `
          <tr data-id="${p.id}">
            <td><code>#${p.id}</code></td>
            <td><strong>${escapeHtml(p.project_name)}</strong></td>
            <td><span class="status-badge ${statusClass}">${escapeHtml(p.status || 'active')}</span></td>
            <td><span class="badge" style="background: rgba(59, 130, 246, 0.15); color: #93c5fd; padding: 2px 6px;">v${p.version || 1}</span></td>
            <td><small style="color: #94a3b8;">${createdDate || '-'}</small></td>
            <td><small style="color: #94a3b8;">${updatedDate || '-'}</small></td>
            <td>
              <div class="btn-actions-group">
                <button 
                  class="btn btn-outline btn-xs btn-row-view" 
                  data-md="${escapeHtml(p.markdown_path || '')}" 
                  data-name="${escapeHtml(p.project_name)}"
                  title="View Markdown"
                >👁️</button>
                <button 
                  class="btn btn-outline btn-xs btn-row-edit" 
                  data-id="${p.id}"
                  title="Edit Project"
                >✏️</button>
                ${p.status !== 'archived' ? `
                  <button 
                    class="btn btn-warning btn-xs btn-row-archive" 
                    data-id="${p.id}"
                    data-name="${escapeHtml(p.project_name)}"
                    title="Archive Project"
                  >📦</button>
                ` : `
                  <button 
                    class="btn btn-outline btn-xs btn-row-restore" 
                    data-id="${p.id}"
                    data-name="${escapeHtml(p.project_name)}"
                    title="Restore Project"
                  >♻️</button>
                `}
                <button 
                  class="btn btn-danger btn-xs btn-row-delete" 
                  data-id="${p.id}"
                  data-name="${escapeHtml(p.project_name)}"
                  title="Permanent Delete"
                >🗑️</button>
              </div>
            </td>
          </tr>
        `;
      }).join('');

      // Attach row event listeners
      attachRowEventListeners(projects);

    } catch (e) {
      console.warn('Could not load projects:', e);
      projectsTbody.innerHTML = `<tr><td colspan="7" class="text-center" style="color: #ef4444; padding: 18px;">Failed to load records from SQLite database.</td></tr>`;
    }
  }

  function attachRowEventListeners(projects) {
    // 1. View Markdown
    document.querySelectorAll('.btn-row-view').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const path = btn.getAttribute('data-md');
        const name = btn.getAttribute('data-name');
        if (path) {
          showPreview(path, `Project: ${name}`);
        } else {
          alert('No markdown file registered for this project record.');
        }
      });
    });

    // 2. Edit Project
    document.querySelectorAll('.btn-row-edit').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-id'), 10);
        const project = projects.find(p => p.id === id);
        if (project) {
          enterEditMode(project);
        }
      });
    });

    // 3. Archive Project (Soft Delete)
    document.querySelectorAll('.btn-row-archive').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-id'), 10);
        const name = btn.getAttribute('data-name');
        showConfirmDialog(
          'Archive Project',
          `Are you sure you want to archive <strong>${escapeHtml(name)}</strong> (ID #${id})? The record will remain in the database marked as <em>archived</em>.`,
          async () => {
            try {
              const res = await fetch(`/api/projects/${id}?permanent=false`, { method: 'DELETE' });
              let result = {};
              try {
                result = await res.json();
              } catch {
                result = { detail: res.statusText };
              }
              if (res.ok) {
                statusBanner.className = 'banner success';
                statusBanner.style.display = 'block';
                statusBanner.innerHTML = `Project <strong>${escapeHtml(name)}</strong> (#${id}) successfully archived.`;
                loadRecentProjects();
              } else {
                alert(`Error archiving project: ${result.detail || result.message || 'Operation failed'}`);
              }
            } catch (err) {
              alert(`Network error: ${err.message}`);
            }
          }
        );
      });
    });

    // 4. Restore Project
    document.querySelectorAll('.btn-row-restore').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = parseInt(btn.getAttribute('data-id'), 10);
        const name = btn.getAttribute('data-name');
        try {
          const res = await fetch(`/api/projects/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'active' })
          });
          let result = {};
          try {
            result = await res.json();
          } catch {
            result = { detail: res.statusText };
          }
          if (res.ok) {
            statusBanner.className = 'banner success';
            statusBanner.style.display = 'block';
            statusBanner.innerHTML = `Project <strong>${escapeHtml(name)}</strong> restored to active.`;
            loadRecentProjects();
          } else {
            alert(`Error restoring project: ${result.detail || result.message || 'Operation failed'}`);
          }
        } catch (err) {
          alert(`Network error: ${err.message}`);
        }
      });
    });

    // 5. Permanent Delete (Hard Delete)
    document.querySelectorAll('.btn-row-delete').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-id'), 10);
        const name = btn.getAttribute('data-name');
        showConfirmDialog(
          '⚠️ Permanent Delete',
          `Are you sure you want to <strong style="color: #ef4444;">PERMANENTLY DELETE</strong> project <strong>${escapeHtml(name)}</strong> (ID #${id})?<br><br>This will completely remove the SQLite row and all related audit logs. This operation CANNOT be undone.`,
          async () => {
            try {
              const res = await fetch(`/api/projects/${id}?permanent=true`, { method: 'DELETE' });
              let result = {};
              try {
                result = await res.json();
              } catch {
                result = { detail: res.statusText };
              }
              if (res.ok) {
                statusBanner.className = 'banner success';
                statusBanner.style.display = 'block';
                statusBanner.innerHTML = `Project <strong>${escapeHtml(name)}</strong> (#${id}) was permanently deleted from the database.`;
                if (editingProjectId === id) {
                  exitEditMode();
                }
                loadRecentProjects();
              } else {
                alert(`Error deleting project: ${result.detail || result.message || 'Operation failed'}`);
              }
            } catch (err) {
              alert(`Network error: ${err.message}`);
            }
          }
        );
      });
    });
  }

  // =========================================================================
  // 10. Filter Buttons Listener
  // =========================================================================
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentStatusFilter = btn.getAttribute('data-filter') || 'all';
      loadRecentProjects();
    });
  });

  btnRefreshHistory.addEventListener('click', loadRecentProjects);

  btnClearAirtable?.addEventListener('click', async () => {
    const confirmed = confirm(
      '⚠️ Clear All Airtable Data?\n\n' +
      'This will permanently delete all records currently stored in your Airtable Base.\n\n' +
      '• Table structure and column/field labels will remain completely intact.\n' +
      '• Local SQLite database projects will NOT be affected.\n\n' +
      'Proceed with clearing Airtable data?'
    );
    if (!confirmed) return;

    const originalText = btnClearAirtable.textContent;
    btnClearAirtable.disabled = true;
    btnClearAirtable.textContent = '⏳ Clearing...';

    try {
      const res = await fetch('/api/airtable/clear', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        alert(`✅ Airtable Data Cleared Successfully!\n\nDeleted ${data.deleted_count} records.\nAll column headers and field labels remain intact.`);
      } else {
        alert(`❌ Failed to clear Airtable: ${data.error || data.reason || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`❌ Connection error: ${err.message}`);
    } finally {
      btnClearAirtable.disabled = false;
      btnClearAirtable.textContent = originalText;
    }
  });

  // Helper: HTML Escaping
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // =========================================================================
  // 11. Dual Mode Switcher & MCP Host Control Center
  // =========================================================================
  const btnModeServer = document.getElementById('btn-mode-server');
  const btnModeHost = document.getElementById('btn-mode-host');
  const serverWorkspace = document.getElementById('server-workspace');
  const hostWorkspace = document.getElementById('host-workspace');
  const mcpStatusBadge = document.getElementById('mcp-status-badge');

  let currentMode = 'server';
  let registeredTools = [];
  let currentSelectedTool = null;
  let lastExecutionData = null;

  async function switchMode(mode, persist = true) {
    currentMode = mode;

    if (mode === 'host') {
      btnModeHost?.classList.add('active');
      btnModeServer?.classList.remove('active');
      if (serverWorkspace) serverWorkspace.style.display = 'none';
      if (hostWorkspace) hostWorkspace.style.display = 'flex';
      if (mcpStatusBadge) {
        mcpStatusBadge.textContent = '🟣 MCP Host Active';
        mcpStatusBadge.className = 'badge mcp-badge';
      }
      loadHostTools();
    } else {
      btnModeServer?.classList.add('active');
      btnModeHost?.classList.remove('active');
      if (serverWorkspace) serverWorkspace.style.display = 'grid';
      if (hostWorkspace) hostWorkspace.style.display = 'none';
      if (mcpStatusBadge) {
        mcpStatusBadge.textContent = '⚡ MCP Server Active';
        mcpStatusBadge.className = 'badge mcp-badge';
      }
    }

    if (persist) {
      try {
        localStorage.setItem('user_mode_pref', mode);
        await fetch('/api/mode', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode })
        });
      } catch (err) {
        console.warn('Could not persist mode preference:', err);
      }
    }
  }

  btnModeServer?.addEventListener('click', () => switchMode('server'));
  btnModeHost?.addEventListener('click', () => switchMode('host'));

  // Host Tabs Navigation
  const hostTabBtns = document.querySelectorAll('.host-tab-btn');
  const hostTabContents = document.querySelectorAll('.host-tab-content');

  hostTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabName = btn.getAttribute('data-tab');
      hostTabBtns.forEach(b => b.classList.remove('active'));
      hostTabContents.forEach(c => (c.style.display = 'none'));

      btn.classList.add('active');
      const targetContent = document.getElementById(`host-tab-${tabName}`);
      if (targetContent) {
        targetContent.style.display = 'block';
      }
    });
  });

  // Load tools from backend
  async function loadHostTools() {
    const hostToolsList = document.getElementById('host-tools-list');
    const statToolCount = document.getElementById('stat-tool-count');
    if (!hostToolsList) return;

    try {
      const res = await fetch('/api/host/tools');
      const data = await res.json();
      registeredTools = data.tools || [];
      if (statToolCount) statToolCount.textContent = registeredTools.length;

      renderToolsList(registeredTools);
    } catch (err) {
      console.error('Failed to load host tools:', err);
      hostToolsList.innerHTML = `<div class="error-feedback">Error loading MCP tools: ${escapeHtml(err.message)}</div>`;
    }
  }

  function renderToolsList(tools) {
    const hostToolsList = document.getElementById('host-tools-list');
    if (!hostToolsList) return;

    if (tools.length === 0) {
      hostToolsList.innerHTML = '<div class="text-center" style="padding: 20px; color: var(--text-muted);">No MCP tools matched query.</div>';
      return;
    }

    hostToolsList.innerHTML = '';
    tools.forEach(tool => {
      const item = document.createElement('div');
      item.className = 'tool-item-card';
      if (currentSelectedTool && currentSelectedTool.name === tool.name) {
        item.classList.add('active');
      }

      item.innerHTML = `
        <div class="tool-item-top">
          <span class="tool-name-code">${escapeHtml(tool.name)}</span>
          <span class="tool-category-badge">${escapeHtml(tool.category)}</span>
        </div>
        <p class="tool-item-desc">${escapeHtml(tool.description)}</p>
      `;

      item.addEventListener('click', () => selectTool(tool));
      hostToolsList.appendChild(item);
    });
  }

  // Filter tools by search
  const hostToolSearch = document.getElementById('host-tool-search');
  hostToolSearch?.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    const filtered = registeredTools.filter(t => 
      t.name.toLowerCase().includes(q) || 
      t.description.toLowerCase().includes(q) ||
      t.category.toLowerCase().includes(q)
    );
    renderToolsList(filtered);
  });

  // Select tool and render dynamic input form
  function selectTool(tool) {
    currentSelectedTool = tool;

    // Update active class in sidebar
    document.querySelectorAll('.tool-item-card').forEach(card => {
      const nameEl = card.querySelector('.tool-name-code');
      if (nameEl && nameEl.textContent === tool.name) {
        card.classList.add('active');
      } else {
        card.classList.remove('active');
      }
    });

    const selectedToolName = document.getElementById('selected-tool-name');
    const selectedToolDesc = document.getElementById('selected-tool-desc');
    const selectedToolCategory = document.getElementById('selected-tool-category');
    const toolEmptyPlaceholder = document.getElementById('tool-empty-placeholder');
    const hostToolForm = document.getElementById('host-tool-form');
    const hostFormFields = document.getElementById('host-form-fields');
    const hostResultsPanel = document.getElementById('host-results-panel');

    if (selectedToolName) selectedToolName.textContent = tool.name;
    if (selectedToolDesc) selectedToolDesc.textContent = tool.description || 'No description provided.';
    if (selectedToolCategory) {
      selectedToolCategory.textContent = tool.category;
      selectedToolCategory.style.display = 'inline-block';
      selectedToolCategory.className = 'badge mcp-badge';
    }

    if (toolEmptyPlaceholder) toolEmptyPlaceholder.style.display = 'none';
    if (hostToolForm) hostToolForm.style.display = 'block';
    if (hostResultsPanel) hostResultsPanel.style.display = 'none';

    // Generate input fields
    hostFormFields.innerHTML = '';
    const params = tool.parameters || [];

    if (params.length === 0) {
      hostFormFields.innerHTML = '<p style="color: var(--text-muted); font-size: 0.88rem; padding: 10px 0;">This tool does not require any parameters. Click execute below to invoke it.</p>';
      return;
    }

    params.forEach(param => {
      const fieldDiv = document.createElement('div');
      fieldDiv.className = 'form-group';

      const label = document.createElement('label');
      label.setAttribute('for', `param-${param.name}`);
      label.innerHTML = `
        <strong>${escapeHtml(param.title || param.name)}</strong>
        <span class="field-type-pill">${escapeHtml(param.type)}</span>
        ${param.required ? '<span class="field-required-badge">*</span>' : '<span style="color: var(--text-muted); font-size: 0.75rem;"> (optional)</span>'}
      `;
      fieldDiv.appendChild(label);

      let inputEl;
      if (param.type === 'boolean') {
        inputEl = document.createElement('select');
        inputEl.className = 'form-control';
        inputEl.innerHTML = `
          <option value="false" ${param.default === false ? 'selected' : ''}>false</option>
          <option value="true" ${param.default === true ? 'selected' : ''}>true</option>
        `;
      } else if (param.type === 'integer' || param.type === 'number') {
        inputEl = document.createElement('input');
        inputEl.type = 'number';
        inputEl.className = 'form-control';
        if (param.default !== undefined && param.default !== null) inputEl.value = param.default;
        if (param.name === 'a') inputEl.value = 10;
        if (param.name === 'b') inputEl.value = 25;
        if (param.name === 'project_id') inputEl.placeholder = 'e.g., 1';
      } else if (param.name === 'description' || param.name === 'requirements' || param.name === 'additional_info') {
        inputEl = document.createElement('textarea');
        inputEl.className = 'form-control';
        inputEl.rows = param.name === 'additional_info' ? 2 : 3;
        if (param.default) inputEl.value = param.default;
        if (param.name === 'project_name') inputEl.placeholder = 'e.g., Distributed Payment Cache';
        if (param.name === 'requirements') inputEl.placeholder = '- Fast in-memory lookup\n- Automatic TTL expiration';
      } else {
        inputEl = document.createElement('input');
        inputEl.type = 'text';
        inputEl.className = 'form-control';
        if (param.default) inputEl.value = param.default;
        if (param.name === 'project_name') inputEl.value = 'Autonomous Analytics Pipeline';
        if (param.name === 'status') inputEl.placeholder = 'active, archived, or all';
      }

      inputEl.id = `param-${param.name}`;
      inputEl.name = param.name;
      if (param.required) inputEl.required = true;

      fieldDiv.appendChild(inputEl);
      hostFormFields.appendChild(fieldDiv);
    });
  }

  // Handle Tool Form Execution
  const hostToolForm = document.getElementById('host-tool-form');
  hostToolForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentSelectedTool) return;

    const btnHostExec = document.getElementById('btn-host-exec');
    const hostExecSpinner = document.getElementById('host-exec-spinner');
    const hostResultsPanel = document.getElementById('host-results-panel');
    const hostResStatus = document.getElementById('host-res-status');
    const hostResLatency = document.getElementById('host-res-latency');
    const statLatency = document.getElementById('stat-latency');
    const hostResFormatted = document.getElementById('host-res-formatted');
    const hostResJsonrpc = document.getElementById('host-res-jsonrpc');

    const args = {};
    const params = currentSelectedTool.parameters || [];
    params.forEach(param => {
      const field = document.getElementById(`param-${param.name}`);
      if (!field) return;

      let val = field.value;
      if (param.type === 'integer' || param.type === 'number') {
        if (val !== '') args[param.name] = Number(val);
      } else if (param.type === 'boolean') {
        args[param.name] = val === 'true';
      } else {
        if (val !== '' || param.required) {
          args[param.name] = val;
        }
      }
    });

    btnHostExec.disabled = true;
    if (hostExecSpinner) hostExecSpinner.style.display = 'inline-block';

    try {
      const res = await fetch('/api/host/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool: currentSelectedTool.name,
          arguments: args
        })
      });

      const data = await res.json();
      lastExecutionData = data;

      if (hostResultsPanel) hostResultsPanel.style.display = 'block';
      if (hostResStatus) {
        hostResStatus.textContent = data.success ? 'Success' : 'Execution Failed';
        hostResStatus.className = data.success ? 'badge badge-success' : 'badge badge-danger';
      }

      const msText = `${data.execution_time_ms || 0}ms`;
      if (hostResLatency) hostResLatency.textContent = msText;
      if (statLatency) statLatency.textContent = msText;

      // Formatted Result
      if (hostResFormatted) {
        hostResFormatted.textContent = typeof data.result === 'object' 
          ? JSON.stringify(data.result, null, 2) 
          : String(data.result || data.raw_text || data.error || 'Done');
      }

      // Raw JSON-RPC framing inspector
      if (hostResJsonrpc) {
        hostResJsonrpc.textContent = JSON.stringify({
          client_jsonrpc_request: data.rpc_request,
          server_jsonrpc_response: data.rpc_response
        }, null, 2);
      }

      // If the tool modified database records, refresh database table in background
      if (['orchestrate_workflow', 'store_project_in_database', 'archive_or_delete_project', 'update_existing_project'].includes(currentSelectedTool.name)) {
        loadRecentProjects();
      }

    } catch (err) {
      if (hostResultsPanel) hostResultsPanel.style.display = 'block';
      if (hostResStatus) {
        hostResStatus.textContent = 'Network Error';
        hostResStatus.className = 'badge badge-danger';
      }
      if (hostResFormatted) hostResFormatted.textContent = `Error: ${err.message}`;
    } finally {
      btnHostExec.disabled = false;
      if (hostExecSpinner) hostExecSpinner.style.display = 'none';
    }
  });

  // Results Tabs (Formatted vs JSON-RPC Inspector)
  const resTabBtns = document.querySelectorAll('.res-tab-btn');
  resTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      resTabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const view = btn.getAttribute('data-view');
      const formattedEl = document.getElementById('host-res-formatted');
      const jsonrpcEl = document.getElementById('host-res-jsonrpc');

      if (view === 'formatted') {
        if (formattedEl) formattedEl.style.display = 'block';
        if (jsonrpcEl) jsonrpcEl.style.display = 'none';
      } else {
        if (formattedEl) formattedEl.style.display = 'none';
        if (jsonrpcEl) jsonrpcEl.style.display = 'block';
      }
    });
  });

  // Host Assistant Natural Language Chat
  const hostChatForm = document.getElementById('host-chat-form');
  const hostChatInput = document.getElementById('host-chat-input');
  const hostChatHistory = document.getElementById('host-chat-history');

  function appendChatMessage(sender, text, toolCalled = null, latency = null) {
    if (!hostChatHistory) return;
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${sender}`;

    let toolBadgeHtml = '';
    if (toolCalled) {
      toolBadgeHtml = `
        <div>
          <span class="msg-tool-chip">⚡ MCP Tool Invoked: <strong>${escapeHtml(toolCalled)}</strong> ${latency ? `(${latency}ms)` : ''}</span>
        </div>
      `;
    }

    // Basic markdown formatting: bold **text**, `code`, newlines
    let formattedHtml = escapeHtml(text)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br/>');

    msgDiv.innerHTML = `
      <div class="msg-bubble">
        <p>${formattedHtml}</p>
        ${toolBadgeHtml}
      </div>
    `;

    hostChatHistory.appendChild(msgDiv);
    hostChatHistory.scrollTop = hostChatHistory.scrollHeight;
    return msgDiv;
  }

  // Host Brain Provider Selector & API Key Handling
  const hostProviderSelect = document.getElementById('host-provider-select');
  const apiKeyContainer = document.getElementById('api-key-container');
  const hostApiKeyInput = document.getElementById('host-api-key-input');
  const btnSaveKey = document.getElementById('btn-save-key');

  let currentHostProvider = 'gemini';

  function updateProviderUI() {
    currentHostProvider = hostProviderSelect?.value || 'gemini';
    if (currentHostProvider === 'local') {
      if (apiKeyContainer) apiKeyContainer.style.display = 'none';
    } else {
      if (apiKeyContainer) apiKeyContainer.style.display = 'flex';
      const storageKey = `${currentHostProvider}_api_key`;
      if (hostApiKeyInput) {
        hostApiKeyInput.value = localStorage.getItem(storageKey) || '';
        hostApiKeyInput.placeholder = `API Key configured in .env (or paste here)...`;
      }
    }
  }
  updateProviderUI();

  hostProviderSelect?.addEventListener('change', updateProviderUI);

  btnSaveKey?.addEventListener('click', () => {
    if (!hostApiKeyInput) return;
    const storageKey = `${currentHostProvider}_api_key`;
    localStorage.setItem(storageKey, hostApiKeyInput.value.trim());
    btnSaveKey.textContent = 'Saved!';
    setTimeout(() => { btnSaveKey.textContent = 'Save'; }, 1500);
  });

  async function sendHostChatMessage(userText) {
    if (!userText.trim()) return;

    appendChatMessage('user', userText);
    if (hostChatInput) hostChatInput.value = '';

    const providerLabel = currentHostProvider === 'gemini' 
      ? 'Google Gemini' 
      : 'Local Engine';

    const thinkingBubble = appendChatMessage('assistant', `Consulting ${providerLabel} Host Brain & formulating tool call...`);

    const activeKey = currentHostProvider !== 'local' 
      ? (hostApiKeyInput?.value.trim() || localStorage.getItem(`${currentHostProvider}_api_key`) || '')
      : null;

    try {
      const res = await fetch('/api/host/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: userText,
          provider: currentHostProvider,
          api_key: activeKey
        })
      });
      const data = await res.json();
      thinkingBubble?.remove();

      const toolCalled = data.tool_called;
      const latency = data.execution ? data.execution.execution_time_ms : null;
      appendChatMessage('assistant', data.message || 'No response returned.', toolCalled, latency);

      // If database or cloud records were modified, refresh table
      if (['orchestrate_workflow', 'archive_or_delete_project', 'sync_all_to_airtable', 'clear_airtable_data'].includes(toolCalled)) {
        loadRecentProjects();
      }
    } catch (err) {
      thinkingBubble?.remove();
      appendChatMessage('assistant', `Error executing MCP host instruction: ${err.message}`);
    }
  }

  hostChatForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    if (hostChatInput) sendHostChatMessage(hostChatInput.value);
  });

  // Quick prompt chips
  const chipBtns = document.querySelectorAll('.chip-btn');
  chipBtns.forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.getAttribute('data-prompt');
      if (prompt) sendHostChatMessage(prompt);
    });
  });

  // Initialize Mode Preference on Startup
  async function initModePreference() {
    try {
      const res = await fetch('/api/mode');
      const data = await res.json();
      const initialMode = data.mode || localStorage.getItem('user_mode_pref') || 'server';
      switchMode(initialMode, false);
    } catch {
      const localMode = localStorage.getItem('user_mode_pref') || 'server';
      switchMode(localMode, false);
    }
  }

  // Initial load
  updateAllCounters();
  loadRecentProjects();
  initModePreference();
});
