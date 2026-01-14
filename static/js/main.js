// static/js/main.js

document.addEventListener("DOMContentLoaded", function() {
    
    // --- 1. AUTO-CERRAR ALERTAS (Flash Messages) ---
    // Busca todas las alertas de Bootstrap y las cierra a los 4 segundos
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            // Usamos la API de Bootstrap para cerrar la alerta suavemente
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 4000); // 4000 milisegundos = 4 segundos


    // --- 2. VALIDACIÓN DE FORMULARIOS (Bootstrap 5) ---
    // Busca todos los formularios que tengan la clase 'needs-validation'
    var forms = document.querySelectorAll('.needs-validation');

    // Recorre cada formulario y vigila cuando alguien intente enviarlo
    Array.prototype.slice.call(forms).forEach(function (form) {
        form.addEventListener('submit', function (event) {
            
            // Si el formulario NO es válido (campos vacíos, emails raros, etc.)
            if (!form.checkValidity()) {
                event.preventDefault(); // ¡Alto! No envíes nada al servidor
                event.stopPropagation(); // Detén la acción
            }

            // Agrega la clase visual de Bootstrap que pone los bordes rojos/verdes
            form.classList.add('was-validated');
        }, false);
    });

});