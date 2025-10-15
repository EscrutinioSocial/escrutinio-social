//la idea de este JS es agregar funciones que se llaman de más de un lado o que no pertenecen a un módulo sino que son cross 
// a toda la aplicación

function calcularYSetearAlturaContenedorDarkroom() {
    // Si hay imagen de acta
    var $container = $('.darkroom-container');
    if ($container.length) {
        // Actualizar el alto de la imagen a lo disponible
        var padding = 24;
        $('html, body').css('overflowY', 'hidden');
        var darkroomHeight = $(window).height() - $container.offset().top - padding * 2;
        $container.height(darkroomHeight);
        // Actualizar el alto del left panel
        var $leftPanel = $('.left-panel .card');
        var leftPanelHeight = $(window).height() - $leftPanel.offset().top - padding;
        $('.left-panel .card')
        .css('max-height', leftPanelHeight)
        .css('overflowY', 'auto');
    }
}