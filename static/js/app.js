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

    form.addEventListener('submit', function(event) {
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

document.addEventListener('DOMContentLoaded', () => {
    addFormSubmitFeedback('upload-pic-form', 'Caricamento...');
    addFormSubmitFeedback('export-data-form', 'Esportazione...', 3000);
});


// --- NUOVA FUNZIONE AJAX GENERICA BASATA SU CLICK ---

async function handleAjaxClick(button, url, successCallback) {
    const form = button.closest('form');
    if (!form) return;

    const formData = new FormData(form);
    const originalButtonHTML = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '...'; 

    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': formData.get('csrf_token') }
        });

        const result = await response.json();

        if (response.ok && result.success) {
            successCallback(result, form);
        } else {
            alert('Errore: ' + (result.error || 'Si è verificato un problema.'));
        }

    } catch (error) {
        console.error('Errore durante la richiesta AJAX:', error);
        alert('Si è verificato un errore di rete. Riprova.');
    } finally {
        // La funzione di successo è responsabile del ripristino del pulsante
        // per gestire i feedback personalizzati (es. "Salvato!")
        if (successCallback !== onUpdateNotesSuccess) {
            button.disabled = false;
            button.innerHTML = originalButtonHTML;
        }
    }
}


// --- FUNZIONI SPECIFICHE PER LA PAGINA SCHEDA ---
// (Queste non sono più usate direttamente, ma la logica è simile)

// --- FUNZIONI SPECIFICHE PER LA PAGINA ESERCIZI ---

function onRenameExerciseSuccess(result, form) {
    const exerciseId = result.exerciseId;
    const newName = result.newName;
    const exerciseRow = document.querySelector(`#exercise-${exerciseId}`);
    if (exerciseRow) {
        const nameSpan = exerciseRow.querySelector('.exercise-name');
        if (nameSpan) {
            nameSpan.textContent = newName;
        }
    }
    
    const modalElement = form.closest('.modal');
    const modalInstance = bootstrap.Modal.getInstance(modalElement);
    modalInstance.hide();
}

function onUpdateNotesSuccess(result, form) {
    const button = form.querySelector('button[type="submit"]');
    const originalText = "Salva Nota"; // Testo originale
    button.innerHTML = 'Salvato!';
    setTimeout(() => {
        button.innerHTML = originalText;
        button.disabled = false;
    }, 1500);
}

function onDeleteExerciseSuccess(result, form) {
    form.closest('tr').remove();
}