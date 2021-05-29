/*
   Si pudimos determinar la mesa unívocamente, actualizamos la
   sección y el circuito (si están vacíos).
*/
function cambioMesa(url_seccion,url_circuito){
    var mesa = $('#id_mesa').val();
    var circuito = $('#id_circuito').val();
    var seccion = $('#id_seccion').val();
    if(mesa != -1){
	var params = {'mesa': mesa, 'desdeMesa': '1'};
	if(circuito == -1){
	    updateFieldUrl('circuito',url_circuito, params);
	}
	if(seccion == -1){
	    updateFieldUrl('seccion',url_seccion,params);
	}
    }
    return true;
}

// esta función se agrega para que el callback se ejecute después de ms millis
// en particular se uso para que el evento keyup no se aplique al toque, sino que espere
// 300 ms después de que el usuario tecleara el distrito
// si el usuario antes de los ms millis apreta una tecla, el timer se resetea.
function delay(callback, ms) {
	var timer = 0;
	return function() {
	  var context = this, args = arguments;
	  clearTimeout(timer);
	  timer = setTimeout(function () {
		callback.apply(context, args);
	  }, ms || 0);
	};
}

function ocultoSeccionCircuito() {
	var distrito = $('#distrito_input').val();
	$('#id_seccion_container').addClass("hide");
	$('#id_circuito_container').addClass("hide");
	if (distrito != "") {
		$('#id_mesa').focus();
	}
    return true;
}

var updateDistrito = function(url, onAfter = null){
    return(
	function(e){
		updateField('distrito', url,[], onAfter);
	    return true;
	}
    )
}

var updateSeccion = function(url){
    return (
	function(e){
	    updateField(
		'seccion',
		url,
		['distrito']
	    );
	    return true;
	}
    )
}

var updateCircuito = function(url){
    return (
	function(e){
	    updateField(
		'circuito',
		url,
		['distrito','seccion']
	    );
	    return true;
	}
    )
}

var updateMesa = function(url,url_seccion,url_circuito){
    return (
	function(e){
	    updateField(
		'mesa',
		url,
		['distrito','seccion','circuito'],
		cambioMesa(url_seccion,url_circuito)
	    );
	    return true;
	}
    )
}
