(function (window, document) {
    'use strict';

    const NAMESPACE = 'LogbookServiceWorkerRegistration';
    if (window[NAMESPACE]) {
        return;
    }

    function registerServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            return;
        }
        const { swUrl, appVersion } = document.body?.dataset || {};
        const registrationUrl = swUrl || '/service-worker.js';
        navigator.serviceWorker.register(registrationUrl, { updateViaCache: 'none' })
            .then((registration) => {
                console.log('Service Worker registrato.');
                if (appVersion) {
                    try {
                        window.localStorage?.setItem('logbook-app-version', appVersion);
                    } catch (storageError) {
                        console.debug('Impossibile salvare la versione dell\'app in localStorage.', storageError);
                    }
                }
                if (registration?.waiting) {
                    registration.waiting.postMessage({ type: 'SKIP_WAITING' });
                }
            })
            .catch((error) => {
                console.log('Registrazione Service Worker fallita:', error);
            });
    }

    window.addEventListener('load', registerServiceWorker);

    window[NAMESPACE] = Object.freeze({
        register: registerServiceWorker
    });
})(window, document);
