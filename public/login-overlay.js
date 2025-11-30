// Wait for page to fully load including images
window.addEventListener('load', function() {

    function addTextOverlay() {
        // Target the specific image container div
        let imageContainer = document.querySelector('div.relative.hidden.bg-muted.lg\\:block.overflow-hidden');

        // Also try targeting by the image source
        if (!imageContainer) {
            const img = document.querySelector('img[src*="login_page.jpg"]');
            if (img) {
                imageContainer = img.parentElement;
            }
        }

        if (imageContainer) {
            const existingOverlay = document.getElementById('login-text-overlay');
            if (existingOverlay) {
                return;
            }

            const overlay = document.createElement('div');
            overlay.id = 'login-text-overlay';
            overlay.style.cssText = `
                position: absolute;
                top: 30%;
                left: 50%;
                transform: translateX(-50%);
                z-index: 200;
                color: white;
                font-family: 'Jost', sans-serif;
                background: rgba(0, 0, 0, 0.6);
                padding: 35px;
                border-radius: 8px;
                max-width: 500px;
                text-align: center;
            `;

            overlay.innerHTML = `
                <div style="margin-bottom: 25px;">
                    <p style="font-size: 18px; line-height: 1.5; margin: 0; font-weight: 500; color: white;">
                        Getting legal help through a traditional law firm can be costly and time-consuming — even a single question can turn into an expensive engagement. With USLAWAI, you can ask unlimited questions for a low monthly fee, saving you both time and money while getting the answers you need, fast.
                    </p>
                </div>
                <div style="border-top: 1px solid rgba(255, 255, 255, 0.4); padding-top: 20px;">
                    <h5 style="font-size: 20px; font-weight: 700; margin: 0 0 5px 0; color: white;">
                        Carl Brännhammar
                    </h5>
                    <p style="font-size: 16px; margin: 0; color: rgba(255, 255, 255, 0.9); font-weight: 400;">
                        Founder & Partner
                    </p>
                </div>
            `;

            imageContainer.appendChild(overlay);
        }
    }

    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                addTextOverlay();
            }
        });
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    addTextOverlay();
});