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

// Inizializza il feedback per i form comuni quando il DOM è pronto
document.addEventListener('DOMContentLoaded', () => {
    addFormSubmitFeedback('upload-pic-form', 'Caricamento...');
    addFormSubmitFeedback('export-data-form', 'Esportazione...', 3000);
});