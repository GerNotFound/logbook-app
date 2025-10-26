// static/js/app.js

/**
 * Funzione per mostrare/nascondere il contenuto di un campo password.
 * @param {HTMLElement} icon - L'elemento <i> cliccato.
 */
function togglePasswordVisibility(icon) {
    const input = icon.previousElementSibling;
    if (input.type === "password") {
        input.type = "text";
        icon.classList.remove("bi-eye-fill");
        icon.classList.add("bi-eye-slash-fill");
    } else {
        input.type = "password";
        icon.classList.remove("bi-eye-slash-fill");
        icon.classList.add("bi-eye-fill");
    }
}

/**
 * Funzione per mostrare un feedback di caricamento su un pulsante durante l'invio di un form.
 * @param {string} formId - L'ID del form da monitorare.
 * @param {string} loadingText - Il testo da mostrare durante il caricamento.
 * @param {number} [timeout=0] - Un ritardo opzionale in ms per riabilitare il pulsante (utile per i download).
 */
function addFormSubmitFeedback(formId, loadingText, timeout = 0) {
    const form = document.getElementById(formId);
    if (!form) return;

    form.addEventListener('submit', function () {
        if (form.dataset.ajax === "true") return;

        const submitButton = form.querySelector('button[type="submit"]');
        if (!submitButton) return;

        const originalText = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.textContent = loadingText;

        if (timeout > 0) {
            setTimeout(() => {
                submitButton.disabled = false;
                submitButton.textContent = originalText;
            }, timeout);
        }
    });
}

function initPrivacyBanner() {
    const banner = document.getElementById('privacy-banner');
    if (!banner) return;

    const dismissButton = banner.querySelector('[data-privacy-dismiss]');
    const storageKey = 'privacyBannerDismissedAt';
    const sixMonthsMs = 1000 * 60 * 60 * 24 * 182;
    let shouldShow = true;

    try {
        const lastDismissed = localStorage.getItem(storageKey);
        if (lastDismissed) {
            const lastDate = new Date(lastDismissed);
            if (!Number.isNaN(lastDate.getTime())) {
                const elapsed = Date.now() - lastDate.getTime();
                shouldShow = elapsed >= sixMonthsMs;
            }
        }
    } catch (error) {
        console.warn('Impossibile accedere allo storage del browser per la privacy banner.', error);
    }

    if (shouldShow) {
        banner.classList.remove('d-none');
    }

    if (dismissButton) {
        dismissButton.addEventListener('click', () => {
            try {
                localStorage.setItem(storageKey, new Date().toISOString());
            } catch (error) {
                console.warn('Impossibile salvare lo stato del banner privacy.', error);
            }
            banner.classList.add('d-none');
        });
    }
}

function bindConfirmationDialogs() {
    document.querySelectorAll('form[data-confirm]').forEach((form) => {
        if (form.dataset.confirmBound === '1') {
            return;
        }
        form.dataset.confirmBound = '1';
        form.addEventListener('submit', (event) => {
            const message = form.dataset.confirm;
            if (message && !confirm(message)) {
                event.preventDefault();
                event.stopPropagation();
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    addFormSubmitFeedback('upload-pic-form', 'Caricamento...');
    addFormSubmitFeedback('export-data-form', 'Esportazione...', 3000);
    bindAjaxForms();
    initPrivacyBanner();
    bindConfirmationDialogs();
});

/**
 * Risolve dinamicamente un callback che può essere fornito come funzione o come nome in stringa.
 * @param {Function|string|undefined} callback Riferimento al callback di successo.
 * @returns {Function|null}
 */
function resolveCallback(callback) {
    if (typeof callback === 'function') {
        return callback;
    }
    if (typeof callback === 'string' && typeof window[callback] === 'function') {
        return window[callback];
    }
    return null;
}

/**
 * Chiude la modale (se presente) che contiene il form passato.
 * @param {HTMLFormElement} form
 */
function closeParentModal(form) {
    if (!form) return;
    const modalElement = form.closest('.modal');
    if (!modalElement) return;
    const modalInstance = bootstrap.Modal.getInstance(modalElement) || new bootstrap.Modal(modalElement);
    modalInstance.hide();
}

/**
 * Esegue il binding dei form con attributo data-ajax-url per l'invio tramite fetch.
 */
function bindAjaxForms() {
    const ajaxForms = document.querySelectorAll('form[data-ajax-url]');
    ajaxForms.forEach((form) => {
        if (form.dataset.ajaxBound === '1') {
            return;
        }
        form.dataset.ajaxBound = '1';
        form.dataset.ajax = 'true';

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            event.stopPropagation();

            const confirmMessage = form.dataset.ajaxConfirm;
            if (confirmMessage && !confirm(confirmMessage)) {
                return;
            }

            const submitButton = form.querySelector('button[type="submit"]');
            const originalContent = submitButton ? submitButton.innerHTML : null;
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = form.dataset.loadingText || '...';
            }

            const previousScroll = window.scrollY;
            form.dataset.lastScrollPosition = String(previousScroll);

            try {
                const formData = new FormData(form);
                const csrfToken = form.querySelector('input[name="csrf_token"]')?.value || '';
                const response = await fetch(form.dataset.ajaxUrl, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-CSRFToken': csrfToken },
                    credentials: 'same-origin'
                });

                const isJson = response.headers.get('content-type')?.includes('application/json');
                const payload = isJson ? await response.json() : null;

                if (response.ok && payload?.success) {
                    const successCallback = resolveCallback(form.dataset.ajaxSuccess);
                    if (successCallback) {
                        successCallback(payload, form);
                    } else {
                        window.location.reload();
                    }

                    const storedScroll = parseInt(form.dataset.lastScrollPosition || '', 10);
                    if (!Number.isNaN(storedScroll)) {
                        window.requestAnimationFrame(() => {
                            window.scrollTo(0, storedScroll);
                        });
                    }
                } else {
                    const errorMessage = payload?.error || 'Si è verificato un problema.';
                    alert(errorMessage);
                }
            } catch (error) {
                console.error('Errore durante la richiesta AJAX:', error);
                alert('Si è verificato un errore di rete. Riprova.');
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.innerHTML = originalContent;
                }
            }
        });
    });
}

// --- FUNZIONI SPECIFICHE PER LA PAGINA ESERCIZI ---

function onRenameExerciseSuccess(result, form) {
    const exerciseId = result.exerciseId;
    const newName = result.newName;
    const row = document.querySelector(`#exercise-${exerciseId}`);
    if (row) {
        const nameSpan = row.querySelector('.exercise-name');
        if (nameSpan) {
            nameSpan.textContent = newName;
        }
    } else {
        window.location.reload();
        return;
    }
    closeParentModal(form);
}

function onUpdateNotesSuccess(_, form) {
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;
    const originalText = button.dataset.originalText || button.textContent;
    button.dataset.originalText = originalText;
    button.textContent = 'Salvato!';
    button.disabled = true;
    setTimeout(() => {
        button.textContent = originalText;
        button.disabled = false;
    }, 1500);
}

function onDeleteExerciseSuccess(_, form) {
    const row = form.closest('tr');
    if (row) {
        row.remove();
    }
}

// --- FUNZIONI SPECIFICHE PER LA PAGINA SCHEDA ---

function onRenameTemplateSuccess(result, form) {
    const templateId = result.templateId;
    const newName = result.newName;
    const container = document.querySelector(`#template-${templateId}`);
    if (container) {
        const heading = container.querySelector('h4');
        if (heading) {
            heading.textContent = newName;
        }
    } else {
        window.location.reload();
        return;
    }
    closeParentModal(form);
}

function onAddExerciseSuccess() {
    window.location.reload();
}

function onTemplateExerciseDeleted() {
    window.location.reload();
}
