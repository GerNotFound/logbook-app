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
        if (this.hasAttribute('onsubmit')) return;

        const submitButton = this.querySelector('button[type="submit"]');
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


// --- FUNZIONE AJAX GENERICA E HELPER PER TUTTE LE PAGINE ---

async function handleAjaxFormSubmit(event, url, onSuccess) {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);
    const submitButton = form.querySelector('button[type="submit"]');
    const originalButtonHTML = submitButton.innerHTML;
    let successHandled = false;

    submitButton.disabled = true;
    submitButton.innerHTML = '...'; 

    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': formData.get('csrf_token') }
        });

        const result = await response.json();

        if (response.ok && result.success) {
            onSuccess(result, form, originalButtonHTML);
            successHandled = true;
        } else {
            alert('Errore: ' + (result.error || 'Si è verificato un problema.'));
        }

    } catch (error) {
        console.error('Errore durante la richiesta AJAX:', error);
        alert('Si è verificato un errore di rete. Riprova.');
    } finally {
        if (!successHandled) {
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonHTML;
        }
    }
}

// --- FUNZIONI SPECIFICHE PER LA PAGINA SCHEDA ---

function onAddExerciseSuccess(result, form) {
    const exercise = result.exercise;
    const tableBody = form.closest('.border.rounded').querySelector('table tbody');
    
    const noExerciseRow = tableBody.querySelector('.no-exercise-row');
    if (noExerciseRow) noExerciseRow.remove();

    const newRow = document.createElement('tr');
    newRow.id = `tex-${exercise.id}`;
    newRow.innerHTML = `
        <td>${exercise.name}</td>
        <td>${exercise.sets}</td>
        <td class="text-center">
            <form onsubmit="handleDeleteTemplateExercise(event, '/scheda/elimina-esercizio')">
                <input type="hidden" name="csrf_token" value="${result.csrf_token}">
                <input type="hidden" name="template_exercise_id" value="${exercise.id}">
                <button type="submit" class="btn btn-sm btn-delete">X</button>
            </form>
        </td>
    `;
    tableBody.appendChild(newRow);
    form.reset();
}

async function handleDeleteTemplateExercise(event, url) {
    if (!confirm('Sei sicuro di voler eliminare questo esercizio?')) {
        event.preventDefault();
        return;
    }
    await handleAjaxFormSubmit(event, url, (result, form) => {
        form.closest('tr').remove();
    });
}

function onRenameTemplateSuccess(result, form, originalButtonHTML) {
    const templateId = result.templateId;
    const newName = result.newName;
    const templateHeader = document.querySelector(`#template-${templateId} h4`);
    if (templateHeader) templateHeader.textContent = newName;
    
    const input = form.querySelector('[name=new_template_name]');
    if(input) input.value = newName;
    
    const modalElement = form.closest('.modal');
    const modalInstance = bootstrap.Modal.getInstance(modalElement);
    modalInstance.hide();

    // Ripristina il pulsante dopo la chiusura del modal
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.disabled = false;
    submitButton.innerHTML = originalButtonHTML;
}


// --- FUNZIONI SPECIFICHE PER LA PAGINA ESERCIZI ---

function onRenameExerciseSuccess(result, form, originalButtonHTML) {
    const exerciseId = result.exerciseId;
    const newName = result.newName;
    const exerciseRow = document.querySelector(`#exercise-${exerciseId}`);
    if (exerciseRow) {
        const nameSpan = exerciseRow.querySelector('.exercise-name');
        if (nameSpan) {
            nameSpan.textContent = newName;
        }
    }
    const input = form.querySelector('[name=new_exercise_name]');
    if(input) input.value = newName;
    
    const modalElement = form.closest('.modal');
    const modalInstance = bootstrap.Modal.getInstance(modalElement);
    modalInstance.hide();
    
    const submitButton = form.querySelector('button[type="submit"]');
    submitButton.disabled = false;
    submitButton.innerHTML = originalButtonHTML;
}

function onUpdateNotesSuccess(result, form, originalButtonHTML) {
    const button = form.querySelector('button[type="submit"]');
    button.innerHTML = 'Salvato!';
    setTimeout(() => {
        button.innerHTML = originalButtonHTML;
        button.disabled = false;
    }, 1500);
}

async function handleDeleteExercise(event, url) {
    if (!confirm('Sei sicuro di voler eliminare questo esercizio? L\'azione è irreversibile.')) {
        event.preventDefault();
        return;
    }
    await handleAjaxFormSubmit(event, url, (result, form) => {
        form.closest('tr').remove();
    });
}