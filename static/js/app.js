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
 * Reindirizza le pagine sensibili alla data all'URL con la data locale corrente se non è specificata.
 */
function handleTimezoneRedirect() {
    const body = document.body;
    if (body.dataset.dateSensitivePage !== 'true') {
        return;
    }

    const path = window.location.pathname;
    const pathSegments = path.split('/').filter(Boolean);
    const lastSegment = pathSegments[pathSegments.length - 1];
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;

    // Se l'URL termina già con una data, non fare nulla.
    if (lastSegment && dateRegex.test(lastSegment)) {
        return;
    }

    // Ottieni la data locale dell'utente nel formato YYYY-MM-DD
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    const localDateString = `${year}-${month}-${day}`;

    // Costruisci il nuovo URL e reindirizza
    const newPath = `${path.endsWith('/') ? path.slice(0, -1) : path}/${localDateString}`;
    // Usiamo replace per non creare una nuova voce nella cronologia del browser
    window.location.replace(newPath);
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

// Esegui le funzioni all'avvio
document.addEventListener('DOMContentLoaded', () => {
    handleTimezoneRedirect(); // Esegui il controllo del fuso orario per primo
    addFormSubmitFeedback('export-data-form', 'Esportazione...', 3000);
    initPrivacyBanner();
    bindConfirmationDialogs();
});