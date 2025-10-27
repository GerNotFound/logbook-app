(function (window, document) {
    'use strict';

    const NAMESPACE = 'LogbookSessionePalestra';
    if (window[NAMESPACE]) {
        return;
    }

    const STOPWATCH_UPDATE_MS = 250;
    const RUNNING_TIMER_INTERVAL = 1000;

    const DEFAULT_MESSAGES = {
        save: 'Sei sicuro di voler salvare la sessione?',
        cancel: 'Sei sicuro di voler annullare la sessione? I dati non salvati andranno persi.'
    };

    const state = {
        context: {
            templates: [],
            logData: {},
            userId: '',
            recordDate: '',
            saveMessage: DEFAULT_MESSAGES.save,
            cancelMessage: DEFAULT_MESSAGES.cancel,
            homeUrl: ''
        },
        draftKey: 'workout_draft',
        storageAvailable: true,
        currentDraft: { startTime: null, selectedTemplateId: '', fields: {} },
        initialDraftSnapshot: null,
        elements: {
            templateSelector: null,
            workoutSection: null,
            templateNameInput: null,
            startTimestampInput: null,
            workoutForm: null,
            cancelButton: null,
            templateSelectionBox: null,
            workoutStatusBox: null,
            statusTemplateName: null,
            runningTimer: null,
            stopwatchDisplay: null,
            startBtn: null,
            pauseBtn: null,
            stopBtn: null,
            stopwatchWrapper: null,
            stopwatchContainer: null
        },
        timers: {
            running: null
        },
        stopwatch: {
            isRunning: false,
            startEpoch: 0,
            elapsedMs: 0,
            intervalId: null
        }
    };

    function parseJSON(source, fallback) {
        if (!source) {
            return fallback;
        }
        try {
            return JSON.parse(source);
        } catch (error) {
            console.warn('Impossibile analizzare il contenuto JSON.', error);
            return fallback;
        }
    }

    function deepClone(value) {
        try {
            return JSON.parse(JSON.stringify(value));
        } catch (error) {
            return null;
        }
    }

    function sanitizeFields(fields) {
        if (!fields || typeof fields !== 'object') {
            return {};
        }
        return { ...fields };
    }

    function sanitizeDraft(draft) {
        if (!draft || typeof draft !== 'object') {
            return { startTime: null, selectedTemplateId: '', fields: {} };
        }
        const sanitized = {
            startTime: typeof draft.startTime === 'number' ? draft.startTime : null,
            selectedTemplateId: draft.selectedTemplateId ? String(draft.selectedTemplateId) : '',
            fields: sanitizeFields(draft.fields)
        };
        return sanitized;
    }

    function isLocalStorageAvailable() {
        try {
            const testKey = '__logbook_storage_test__';
            window.localStorage.setItem(testKey, '1');
            window.localStorage.removeItem(testKey);
            return true;
        } catch (error) {
            console.warn('Accesso a localStorage non disponibile', error);
            return false;
        }
    }

    function loadDraftFromStorage() {
        if (!state.storageAvailable) {
            return {};
        }
        try {
            const rawDraft = window.localStorage.getItem(state.draftKey);
            return rawDraft ? JSON.parse(rawDraft) : {};
        } catch (error) {
            console.warn('Impossibile leggere la bozza dell\'allenamento', error);
            state.storageAvailable = false;
            return {};
        }
    }

    function persistDraft(draft) {
        state.currentDraft = sanitizeDraft(draft);
        if (!state.storageAvailable) {
            return;
        }
        try {
            window.localStorage.setItem(state.draftKey, JSON.stringify(state.currentDraft));
        } catch (error) {
            console.warn('Impossibile salvare la bozza dell\'allenamento', error);
            state.storageAvailable = false;
        }
    }

    function clearDraftStorage() {
        if (!state.storageAvailable) {
            return;
        }
        try {
            window.localStorage.removeItem(state.draftKey);
        } catch (error) {
            console.warn('Impossibile cancellare la bozza dell\'allenamento', error);
            state.storageAvailable = false;
        }
    }

    function createEmptyDraft() {
        return { startTime: null, selectedTemplateId: '', fields: {} };
    }

    function ensureStartTime(draft) {
        if (typeof draft.startTime !== 'number') {
            draft.startTime = Date.now();
        }
        return draft.startTime;
    }

    function cacheElements() {
        state.elements.templateSelector = document.getElementById('template-selector');
        state.elements.workoutSection = document.getElementById('workout-section');
        state.elements.templateNameInput = document.getElementById('template-name-input');
        state.elements.startTimestampInput = document.getElementById('start-timestamp-input');
        state.elements.workoutForm = document.getElementById('workout-form');
        state.elements.cancelButton = document.getElementById('cancel-workout-btn');
        state.elements.templateSelectionBox = document.getElementById('template-selection-box');
        state.elements.workoutStatusBox = document.getElementById('workout-status-box');
        state.elements.statusTemplateName = document.getElementById('status-template-name');
        state.elements.runningTimer = document.getElementById('running-timer');
        state.elements.stopwatchDisplay = document.getElementById('stopwatch');
        state.elements.startBtn = document.getElementById('startBtn');
        state.elements.pauseBtn = document.getElementById('pauseBtn');
        state.elements.stopBtn = document.getElementById('stopBtn');
        state.elements.stopwatchWrapper = document.getElementById('stopwatch-wrapper');
        state.elements.stopwatchContainer = document.getElementById('stopwatch-container');
    }

    function formatDuration(totalSeconds) {
        const hours = Math.floor(totalSeconds / 3600).toString().padStart(2, '0');
        const minutes = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
        const seconds = Math.floor(totalSeconds % 60).toString().padStart(2, '0');
        return `${hours}:${minutes}:${seconds}`;
    }

    function startRunningTimer(startTimeMs) {
        const { runningTimer } = state.elements;
        if (!runningTimer) {
            return;
        }
        stopRunningTimer();

        const update = () => {
            const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startTimeMs) / 1000));
            runningTimer.textContent = formatDuration(elapsedSeconds);
        };

        update();
        state.timers.running = window.setInterval(update, RUNNING_TIMER_INTERVAL);
    }

    function stopRunningTimer() {
        if (state.timers.running) {
            window.clearInterval(state.timers.running);
            state.timers.running = null;
        }
        if (state.elements.runningTimer) {
            state.elements.runningTimer.textContent = '00:00:00';
        }
    }

    function getExercisesList(template) {
        if (!template) {
            return [];
        }
        if (Array.isArray(template.exercises)) {
            return template.exercises;
        }
        if (template.exercises && typeof template.exercises === 'object') {
            return Object.values(template.exercises);
        }
        return [];
    }

    function updateCancelButtonLabel(hasTemplateSelected) {
        const { cancelButton } = state.elements;
        if (!cancelButton) {
            return;
        }
        cancelButton.textContent = hasTemplateSelected ? 'ANNULLA' : 'INDIETRO';
    }

    function updateUIForTemplateSelection(templateId, startTime) {
        const { templateSelectionBox, workoutStatusBox, statusTemplateName, runningTimer } = state.elements;
        if (!templateSelectionBox || !workoutStatusBox) {
            return;
        }

        if (templateId) {
            const selectedTemplate = state.context.templates.find((tpl) => String(tpl.id) === String(templateId));
            if (selectedTemplate) {
                templateSelectionBox.classList.add('d-none');
                workoutStatusBox.classList.remove('d-none');
                if (statusTemplateName) {
                    statusTemplateName.textContent = selectedTemplate.name;
                }
                if (typeof startTime === 'number') {
                    startRunningTimer(startTime);
                } else {
                    const ensuredStart = ensureStartTime(state.currentDraft);
                    startRunningTimer(ensuredStart);
                }
                updateCancelButtonLabel(true);
                return;
            }
        }

        templateSelectionBox.classList.remove('d-none');
        workoutStatusBox.classList.add('d-none');
        if (statusTemplateName) {
            statusTemplateName.textContent = '';
        }
        stopRunningTimer();
        if (runningTimer) {
            runningTimer.textContent = '00:00:00';
        }
        updateCancelButtonLabel(false);
    }

    function collectFieldValues() {
        const { workoutSection } = state.elements;
        if (!workoutSection) {
            return {};
        }
        const values = {};
        const inputs = workoutSection.querySelectorAll('input, textarea');
        inputs.forEach((input) => {
            if (input.name && input.value) {
                values[input.name] = input.value;
            }
        });
        return values;
    }

    function resolveFieldValue(draftFields, name) {
        if (draftFields && Object.prototype.hasOwnProperty.call(draftFields, name)) {
            return draftFields[name];
        }
        if (state.context.logData && Object.prototype.hasOwnProperty.call(state.context.logData, name)) {
            return state.context.logData[name];
        }
        return '';
    }

    function createFeedbackSection(draftFields) {
        const wrapper = document.createElement('div');
        wrapper.className = 'mb-4 p-3 border rounded session-feedback';

        const heading = document.createElement('h5');
        heading.className = 'mb-3';
        heading.textContent = 'Feedback Allenamento';
        wrapper.appendChild(heading);

        const noteGroup = document.createElement('div');
        noteGroup.className = 'mb-3';
        const noteLabel = document.createElement('label');
        noteLabel.className = 'form-label';
        noteLabel.setAttribute('for', 'session-note');
        noteLabel.textContent = "Note sull'allenamento";
        const noteField = document.createElement('textarea');
        noteField.className = 'form-control';
        noteField.id = 'session-note';
        noteField.name = 'session_note';
        noteField.rows = 3;
        noteField.placeholder = 'Aggiungi eventuali note...';
        const noteValue = resolveFieldValue(draftFields, 'session_note');
        if (noteValue) {
            noteField.value = noteValue;
        }
        noteGroup.appendChild(noteLabel);
        noteGroup.appendChild(noteField);
        wrapper.appendChild(noteGroup);

        const ratingGroup = document.createElement('div');
        ratingGroup.className = 'mb-1';
        const ratingLabel = document.createElement('label');
        ratingLabel.className = 'form-label';
        ratingLabel.setAttribute('for', 'session-rating');
        ratingLabel.textContent = 'Voto allenamento [1-10]';
        const ratingField = document.createElement('input');
        ratingField.type = 'number';
        ratingField.className = 'form-control';
        ratingField.id = 'session-rating';
        ratingField.name = 'session_rating';
        ratingField.min = '1';
        ratingField.max = '10';
        ratingField.step = '1';
        ratingField.inputMode = 'numeric';
        ratingField.pattern = '[0-9]*';
        ratingField.placeholder = 'Inserisci un valore da 1 a 10';
        const ratingValue = resolveFieldValue(draftFields, 'session_rating');
        if (ratingValue !== '' && ratingValue !== null && ratingValue !== undefined) {
            ratingField.value = ratingValue;
        }
        ratingGroup.appendChild(ratingLabel);
        ratingGroup.appendChild(ratingField);
        wrapper.appendChild(ratingGroup);

        return wrapper;
    }

    function appendFeedbackSection(container, draftFields) {
        if (!container) {
            return;
        }
        container.appendChild(createFeedbackSection(draftFields));
    }

    function saveDraftFromInputs() {
        state.currentDraft.fields = collectFieldValues();
        if (state.elements.templateSelector) {
            state.currentDraft.selectedTemplateId = state.elements.templateSelector.value || '';
        }
        ensureStartTime(state.currentDraft);
        persistDraft(state.currentDraft);
    }

    function handleInputChange() {
        saveDraftFromInputs();
    }

    function attachInputListeners() {
        const { workoutSection } = state.elements;
        if (!workoutSection) {
            return;
        }
        const inputs = workoutSection.querySelectorAll('input, textarea');
        inputs.forEach((input) => {
            input.addEventListener('input', handleInputChange);
            input.addEventListener('change', handleInputChange);
        });
    }

    function renderWorkout(templateId) {
        const { workoutSection, templateNameInput } = state.elements;
        if (!workoutSection || !templateNameInput) {
            return;
        }

        workoutSection.innerHTML = '';
        const draftFields = state.currentDraft.fields || {};
        const selectedTemplate = state.context.templates.find((tpl) => String(tpl.id) === String(templateId));

        if (!templateId || !selectedTemplate) {
            templateNameInput.value = 'Allenamento Libero';
            appendFeedbackSection(workoutSection, draftFields);
            attachInputListeners();
            return;
        }

        templateNameInput.value = selectedTemplate.name;

        const exercises = getExercisesList(selectedTemplate);
        const fragment = document.createDocumentFragment();

        exercises.forEach((exercise, index) => {
            const uniqueSuffix = exercise.id ? String(exercise.id) : `${exercise.exercise_id}_${index}`;
            const parentId = `exercise-group-${uniqueSuffix}`;
            const commentsId = `comments-${uniqueSuffix}`;
            const notesId = `notes-${uniqueSuffix}`;
            const historyId = `history-${uniqueSuffix}`;
            const commentBoxId = `comment-box-${uniqueSuffix}`;
            const lastCommentText = exercise.last_comment
                ? `<strong>${exercise.last_comment_date}:</strong> ${exercise.last_comment}`
                : 'Nessun commento precedente.';
            const commentsHtml = `<div id="${commentsId}" class="collapse" data-bs-parent="#${parentId}"><div class="card card-body mt-2 text-sm">${lastCommentText}</div></div>`;
            const notesHtml = exercise.notes
                ? `<div id="${notesId}" class="collapse" data-bs-parent="#${parentId}"><div class="card card-body mt-2 text-sm text-prewrap">${exercise.notes}</div></div>`
                : '';
            const historyContent = Array.isArray(exercise.history) && exercise.history.length > 0
                ? exercise.history
                    .map((session) => `<div class="mb-1"><small><strong>${session.date_formatted}:</strong> ${session.sets.join(' - ')}</small></div>`)
                    .join('')
                : '<small class="text-muted">Nessuno storico precedente.</small>';
            const historyHtml = `<div id="${historyId}" class="collapse" data-bs-parent="#${parentId}"><div class="card card-body mt-2 text-sm">${historyContent}</div></div>`;

            const draftCommentKey = `comment_${exercise.exercise_id}`;
            const existingComment = draftFields[draftCommentKey] ?? state.context.logData[draftCommentKey] ?? '';
            const commentBoxHtml = `<div id="${commentBoxId}" class="collapse mt-2" data-bs-parent="#${parentId}"><textarea name="comment_${exercise.exercise_id}" class="form-control form-control-sm" rows="2" placeholder="Aggiungi un commento...">${existingComment}</textarea></div>`;

            const commentsButtonHtml = `<button type="button" class="btn btn-sm btn-outline-secondary btn-compact" data-bs-toggle="collapse" data-bs-target="#${commentsId}">Commenti</button>`;
            const notesButtonHtml = exercise.notes
                ? `<button type="button" class="btn btn-sm btn-outline-secondary btn-compact" data-bs-toggle="collapse" data-bs-target="#${notesId}">Note</button>`
                : '';
            const historyButtonHtml = `<button type="button" class="btn btn-sm btn-outline-secondary btn-compact" data-bs-toggle="collapse" data-bs-target="#${historyId}">Storico</button>`;

            let setsHtml = '';
            const totalSets = parseInt(exercise.sets, 10) || 0;
            for (let setIndex = 1; setIndex <= totalSets; setIndex += 1) {
                const logKey = `${exercise.exercise_id}_${setIndex}`;
                const draftWeightKey = `weight_${exercise.exercise_id}_${setIndex}`;
                const draftRepsKey = `reps_${exercise.exercise_id}_${setIndex}`;
                const logEntry = state.context.logData[logKey] || {};
                const repsValue = draftFields[draftRepsKey] ?? logEntry.reps ?? '';
                const weightValue = draftFields[draftWeightKey] ?? logEntry.weight ?? '';

                setsHtml += `
                    <div class="row g-2 align-items-center mb-2">
                        <div class="col-2 text-center"><span class="badge bg-secondary">Set ${setIndex}</span></div>
                        <div class="col-5"><input type="text" name="weight_${exercise.exercise_id}_${setIndex}" class="form-control form-control-sm" placeholder="Peso (kg)" value="${weightValue}"></div>
                        <div class="col-5"><input type="number" min="0" step="1" name="reps_${exercise.exercise_id}_${setIndex}" class="form-control form-control-sm" placeholder="Reps" value="${repsValue}"></div>
                    </div>`;
            }

            const exerciseHtml = `
                <div class="d-flex justify-content-between align-items-center">
                    <h5>${exercise.name}</h5>
                    <div class="btn-group">${commentsButtonHtml}${notesButtonHtml}${historyButtonHtml}</div>
                </div>
                ${commentsHtml}${notesHtml}${historyHtml}
                <hr class="my-2">
                ${setsHtml}
                <div class="mt-2">
                    <button type="button" class="btn btn-sm btn-outline-secondary btn-compact" data-bs-toggle="collapse" data-bs-target="#${commentBoxId}">+ Commento</button>
                </div>
                ${commentBoxHtml}`;

            const wrapper = document.createElement('div');
            wrapper.className = 'mb-3 p-3 border rounded';
            wrapper.id = parentId;
            wrapper.innerHTML = exerciseHtml;
            fragment.appendChild(wrapper);
        });

        workoutSection.appendChild(fragment);
        appendFeedbackSection(workoutSection, draftFields);
        attachInputListeners();
    }

    function handleWorkoutFormKeydown(event) {
        if (event.key !== 'Enter' && event.keyCode !== 13) {
            return;
        }
        const currentInput = event.target;
        if (!currentInput || currentInput.tagName.toLowerCase() !== 'input') {
            return;
        }
        const { workoutSection } = state.elements;
        if (!workoutSection) {
            return;
        }

        event.preventDefault();
        const inputs = Array.from(workoutSection.querySelectorAll('input:not([disabled])'));
        const currentIndex = inputs.indexOf(currentInput);
        const nextInput = inputs[currentIndex + 1];
        if (nextInput) {
            nextInput.focus();
            if (typeof nextInput.select === 'function') {
                nextInput.select();
            }
        } else {
            currentInput.blur();
        }
    }

    function setStopwatchButtonsState() {
        const { startBtn, pauseBtn } = state.elements;
        if (startBtn) {
            startBtn.disabled = state.stopwatch.isRunning;
        }
        if (pauseBtn) {
            pauseBtn.disabled = !state.stopwatch.isRunning;
        }
    }

    function updateStopwatchDisplay() {
        const { stopwatchDisplay } = state.elements;
        if (!stopwatchDisplay) {
            return;
        }
        const elapsed = state.stopwatch.elapsedMs + (state.stopwatch.isRunning ? Date.now() - state.stopwatch.startEpoch : 0);
        const totalSeconds = Math.max(0, Math.floor(elapsed / 1000));
        const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
        const seconds = (totalSeconds % 60).toString().padStart(2, '0');
        stopwatchDisplay.textContent = `${minutes}:${seconds}`;
    }

    function stopStopwatchInterval() {
        if (state.stopwatch.intervalId) {
            window.clearInterval(state.stopwatch.intervalId);
            state.stopwatch.intervalId = null;
        }
    }

    function startStopwatch() {
        if (state.stopwatch.isRunning) {
            return;
        }
        state.stopwatch.isRunning = true;
        state.stopwatch.startEpoch = Date.now();
        stopStopwatchInterval();
        state.stopwatch.intervalId = window.setInterval(updateStopwatchDisplay, STOPWATCH_UPDATE_MS);
        updateStopwatchDisplay();
        setStopwatchButtonsState();
    }

    function pauseStopwatch() {
        if (!state.stopwatch.isRunning) {
            return;
        }
        state.stopwatch.elapsedMs += Date.now() - state.stopwatch.startEpoch;
        state.stopwatch.startEpoch = 0;
        state.stopwatch.isRunning = false;
        stopStopwatchInterval();
        updateStopwatchDisplay();
        setStopwatchButtonsState();
    }

    function resetStopwatch() {
        state.stopwatch.isRunning = false;
        state.stopwatch.startEpoch = 0;
        state.stopwatch.elapsedMs = 0;
        stopStopwatchInterval();
        updateStopwatchDisplay();
        setStopwatchButtonsState();
    }

    function handleVisibilityChange() {
        if (!document.hidden) {
            updateStopwatchDisplay();
        }
    }

    function setupStickyStopwatch() {
        const { stopwatchWrapper, stopwatchContainer } = state.elements;
        if (!stopwatchWrapper || !stopwatchContainer || stopwatchWrapper.dataset.stickyBound === '1') {
            return;
        }
        stopwatchWrapper.dataset.stickyBound = '1';
        stopwatchWrapper.style.minHeight = `${stopwatchWrapper.offsetHeight}px`;
        window.addEventListener('scroll', () => {
            if (stopwatchWrapper.getBoundingClientRect().top <= 0) {
                stopwatchContainer.classList.add('stopwatch-sticky');
            } else {
                stopwatchContainer.classList.remove('stopwatch-sticky');
            }
        });
    }

    function handleTemplateChange(event) {
        const templateId = event.target.value || '';
        const newDraft = {
            startTime: Date.now(),
            selectedTemplateId: templateId,
            fields: {}
        };
        persistDraft(newDraft);
        if (state.elements.startTimestampInput) {
            state.elements.startTimestampInput.value = newDraft.startTime;
        }
        renderWorkout(templateId);
        updateUIForTemplateSelection(templateId, newDraft.startTime);
        if (templateId) {
            saveDraftFromInputs();
        }
    }

    function handleFormSubmit(event) {
        const message = state.context.saveMessage || DEFAULT_MESSAGES.save;
        if (!window.confirm(message)) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
        clearDraftStorage();
        state.currentDraft = createEmptyDraft();
    }

    function resetToEmptyDraft() {
        clearDraftStorage();
        state.currentDraft = createEmptyDraft();
        state.initialDraftSnapshot = deepClone(state.currentDraft);
        persistDraft(state.currentDraft);
        if (state.elements.templateSelector) {
            state.elements.templateSelector.value = '';
        }
        if (state.elements.startTimestampInput) {
            state.elements.startTimestampInput.value = '';
        }
        renderWorkout('');
        updateUIForTemplateSelection('', null);
        resetStopwatch();
    }

    function restoreInitialSnapshot() {
        const snapshot = deepClone(state.initialDraftSnapshot);
        state.currentDraft = snapshot ? sanitizeDraft(snapshot) : createEmptyDraft();
        const templateId = state.currentDraft.selectedTemplateId || '';
        const startTime = templateId ? ensureStartTime(state.currentDraft) : null;
        persistDraft(state.currentDraft);
        if (state.elements.templateSelector) {
            state.elements.templateSelector.value = templateId;
        }
        if (state.elements.startTimestampInput) {
            state.elements.startTimestampInput.value = startTime || '';
        }
        renderWorkout(templateId);
        updateUIForTemplateSelection(templateId, startTime);
        resetStopwatch();
    }

    function handleCancel(event) {
        event.preventDefault();

        const hasActiveTemplate = Boolean(state.currentDraft.selectedTemplateId);
        const initialTemplate = state.initialDraftSnapshot && state.initialDraftSnapshot.selectedTemplateId
            ? String(state.initialDraftSnapshot.selectedTemplateId)
            : '';

        if (!hasActiveTemplate) {
            clearDraftStorage();
            state.currentDraft = createEmptyDraft();
            resetStopwatch();
            if (state.context.homeUrl) {
                window.location.href = state.context.homeUrl;
            }
            return;
        }

        const message = state.context.cancelMessage || DEFAULT_MESSAGES.cancel;
        if (!window.confirm(message)) {
            return;
        }

        if (initialTemplate) {
            restoreInitialSnapshot();
            return;
        }

        resetToEmptyDraft();
    }

    function bindEvents() {
        const { templateSelector, workoutForm, cancelButton, startBtn, pauseBtn, stopBtn } = state.elements;
        if (templateSelector) {
            templateSelector.addEventListener('change', handleTemplateChange);
        }
        if (workoutForm) {
            workoutForm.addEventListener('submit', handleFormSubmit);
            workoutForm.addEventListener('keydown', handleWorkoutFormKeydown);
        }
        if (cancelButton) {
            cancelButton.addEventListener('click', handleCancel);
        }
        if (startBtn) {
            startBtn.addEventListener('click', startStopwatch);
        }
        if (pauseBtn) {
            pauseBtn.addEventListener('click', pauseStopwatch);
        }
        if (stopBtn) {
            stopBtn.addEventListener('click', resetStopwatch);
        }
        document.addEventListener('visibilitychange', handleVisibilityChange);
    }

    function initialize() {
        const dataElement = document.getElementById('sessione-palestra-data');
        if (!dataElement) {
            return;
        }

        state.context.templates = parseJSON(dataElement.dataset.templates, []);
        state.context.logData = parseJSON(dataElement.dataset.log, {});
        state.context.userId = dataElement.dataset.userId || '';
        state.context.recordDate = dataElement.dataset.recordDate || '';
        state.context.saveMessage = dataElement.dataset.saveMessage || DEFAULT_MESSAGES.save;
        state.context.cancelMessage = dataElement.dataset.cancelMessage || DEFAULT_MESSAGES.cancel;
        state.context.homeUrl = dataElement.dataset.homeUrl || '';

        state.draftKey = state.context.userId && state.context.recordDate
            ? `workout_draft_${state.context.userId}_${state.context.recordDate}`
            : 'workout_draft';

        cacheElements();
        state.storageAvailable = isLocalStorageAvailable();

        state.currentDraft = sanitizeDraft(loadDraftFromStorage());
        const fallbackTemplateId = state.elements.templateSelector ? state.elements.templateSelector.value || '' : '';
        if (!state.currentDraft.selectedTemplateId && fallbackTemplateId) {
            state.currentDraft.selectedTemplateId = fallbackTemplateId;
        }
        const startTime = ensureStartTime(state.currentDraft);
        persistDraft(state.currentDraft);

        state.initialDraftSnapshot = deepClone(state.currentDraft);

        if (state.elements.templateSelector) {
            state.elements.templateSelector.value = state.currentDraft.selectedTemplateId || '';
        }
        if (state.elements.startTimestampInput) {
            state.elements.startTimestampInput.value = startTime;
        }

        renderWorkout(state.currentDraft.selectedTemplateId);
        updateUIForTemplateSelection(state.currentDraft.selectedTemplateId, startTime);

        bindEvents();
        setupStickyStopwatch();
        updateStopwatchDisplay();
        setStopwatchButtonsState();
    }

    document.addEventListener('DOMContentLoaded', initialize);

    window[NAMESPACE] = Object.freeze({
        resetStopwatch
    });
})(window, document);
