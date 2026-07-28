document.addEventListener('DOMContentLoaded', () => {
    // --- Booking Modal State Management ---
    const bookingModal = document.getElementById('booking-modal');
    const btnBookNav = document.getElementById('btn-book-nav');
    const btnBookHero = document.getElementById('btn-book-hero');
    const btnModalClose = document.getElementById('btn-modal-close');

    const openModal = () => {
        bookingModal.classList.add('open');
        document.body.style.overflow = 'hidden'; // Lock background scrolling
    };

    const closeModal = () => {
        bookingModal.classList.remove('open');
        document.body.style.overflow = ''; // Unlock scrolling
        resetForm(bookingForm, bookErrorFields);
    };

    if (btnBookNav) btnBookNav.addEventListener('click', openModal);
    if (btnBookHero) btnBookHero.addEventListener('click', openModal);
    if (btnModalClose) btnModalClose.addEventListener('click', closeModal);

    // Close on backdrop click
    bookingModal.addEventListener('click', (e) => {
        if (e.target === bookingModal) {
            closeModal();
        }
    });

    // --- Helper function to reset forms ---
    const resetForm = (form, errorMap) => {
        form.reset();
        Object.values(errorMap).forEach(el => {
            if (el) el.style.display = 'none';
        });
        const successMessage = form.nextElementSibling;
        if (successMessage && successMessage.classList.contains('success-message')) {
            successMessage.style.display = 'none';
        }
        form.style.display = 'block';
    };

    // --- Booking Form Validation ---
    const bookingForm = document.getElementById('booking-form');
    const bookSuccess = document.getElementById('book-success');
    const bookErrorFields = {
        name: document.getElementById('book-name-error'),
        phone: document.getElementById('book-phone-error'),
        doctor: document.getElementById('book-doctor-error'),
        date: document.getElementById('book-date-error')
    };

    bookingForm.addEventListener('submit', (e) => {
        e.preventDefault();
        let isValid = true;

        // Reset errors
        Object.values(bookErrorFields).forEach(el => {
            if (el) el.style.display = 'none';
        });

        // Validate Name
        const nameVal = document.getElementById('book-name').value.trim();
        if (!nameVal) {
            bookErrorFields.name.style.display = 'block';
            isValid = false;
        }

        // Validate Phone (simple format validation)
        const phoneVal = document.getElementById('book-phone').value.trim();
        const phonePattern = /^\+?[0-9\s\-()]{7,15}$/;
        if (!phoneVal || !phonePattern.test(phoneVal)) {
            bookErrorFields.phone.style.display = 'block';
            isValid = false;
        }

        // Validate Doctor
        const doctorVal = document.getElementById('book-doctor').value;
        if (!doctorVal) {
            bookErrorFields.doctor.style.display = 'block';
            isValid = false;
        }

        // Validate Date (must be in the future)
        const dateVal = document.getElementById('book-date').value;
        const selectedDate = new Date(dateVal);
        const today = new Date();
        today.setHours(0,0,0,0);
        
        if (!dateVal || selectedDate < today) {
            bookErrorFields.date.style.display = 'block';
            isValid = false;
        }

        if (isValid) {
            console.log('Booking request submitted:', { nameVal, phoneVal, doctorVal, dateVal });
            
            // Show Success screen inside modal
            bookingForm.style.display = 'none';
            bookSuccess.style.display = 'flex';
            
            // Auto close modal after 3 seconds
            setTimeout(() => {
                closeModal();
            }, 3500);
        }
    });

    // --- Contact Form Validation ---
    const contactForm = document.getElementById('contact-form');
    const contactSuccess = document.getElementById('contact-success');
    const contactErrorFields = {
        name: document.getElementById('name-error'),
        email: document.getElementById('email-error'),
        msg: document.getElementById('msg-error')
    };

    contactForm.addEventListener('submit', (e) => {
        e.preventDefault();
        let isValid = true;

        // Reset errors
        Object.values(contactErrorFields).forEach(el => {
            if (el) el.style.display = 'none';
        });

        // Validate Name
        const nameVal = document.getElementById('contact-name').value.trim();
        if (!nameVal) {
            contactErrorFields.name.style.display = 'block';
            isValid = false;
        }

        // Validate Email
        const emailVal = document.getElementById('contact-email').value.trim();
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailVal || !emailPattern.test(emailVal)) {
            contactErrorFields.email.style.display = 'block';
            isValid = false;
        }

        // Validate Message
        const msgVal = document.getElementById('contact-msg').value.trim();
        if (!msgVal) {
            contactErrorFields.msg.style.display = 'block';
            isValid = false;
        }

        if (isValid) {
            console.log('Contact message submitted:', { nameVal, emailVal, msgVal });
            
            // Show success screen in place of form
            contactForm.style.display = 'none';
            contactSuccess.style.display = 'flex';
        }
    });
});
