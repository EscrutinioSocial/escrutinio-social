function cargandoCategoria(categoria) {
  let carga = {
    ultimaCategoria: null,
    cantidadCambios: 0
  };
  if (sessionStorage.getItem('carga')) {
    carga = JSON.parse(sessionStorage.getItem('carga'));
  }
  if (carga.ultimaCategoria && carga.ultimaCategoria !== categoria) {
    if (carga.cantidadCambios === 0) {
      // para mostrar una ventana modal en $(document).ready
      // se necesita un delay
      setTimeout(function() {
        $('#cambio-categoria').modal('open');
      }, 500)
    } else {
      M.toast({html: '<span>Continuamos cargando <strong>' + categoria + '</strong>.</span>'})
    }
    carga.cantidadCambios++;
  }
  carga.ultimaCategoria = categoria;
  sessionStorage.setItem('carga', JSON.stringify(carga));
}
