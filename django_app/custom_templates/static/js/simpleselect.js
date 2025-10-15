/*
Esta función simplemente setea los valores y textos correspondiente de
los inputs asociados al campo. Si hay una única opción válida se usan
esos valores.
*/
function displayResult(field,default_value,options=[]){
    var shown_value = default_value;
    var value = -1;
    var input_text = $.trim($('#'+field+'_input').val());
    var required = $('#'+field+'_input').prop('required');
    if(options.length == 1){
		shown_value= options[0].text;
		value = options[0].id;
		input_text = options[0].selected_text;
    } else {
		shown_value = "";
	}
    /* Si val es -1 entonces estamos ante un error. 
     */
    if (value == -1 && !(input_text == "")){
		if (!($("#"+field+"_input").is(':focus')) && input_text == "")  {
			$($('label[for='+field+'_input]')[0]).removeClass("active");
		}
		if (input_text != "" || required){
			$('#inline-error-for-'+field).removeClass("hide");
		}
		if (input_text == ""){
			shown_value = "";
		}
    } else {
		$($('label[for='+field+'_input]')[0]).addClass("active");
		$("#"+field+"-resultado").removeClass("hide");
		$('#inline-error-for-'+field).addClass("hide");
    }
    $("#"+field+"-resultado").val(shown_value);
    if(value != ""){
		$("#id_"+field).val(value);
    }
    $("#"+field+"_input").val(input_text);
    return true;
}

/*
Inicialización de los inputs asociados a un campo. Tomamos el id del
objeto del input "#id_field".
*/
function initializeSimpleSelect(field, baseUrl, onAfter=null) {
    var value = $("#id_"+field).val();
    if(value != -1 && value!="" && isFinite(value)) {
	var url = baseUrl+'?ident='+value;
	$.ajax({
      	    type: 'GET',
      	    url: url
	}).then(function (data) {
			options = data['results'];
			if(options.length==1){
			displayResult(field,"",options);
			if (onAfter) {
				onAfter();
			}
		}
	});
    }
}

function updateFieldUrl(field,url,params){
    var url = url+'?forward='+JSON.stringify(params);
    $.ajax({
      	type: 'GET',
      	url: url
    }).then(function (data) {
		options = data['results'];
		displayResult(field,"",options);
    });
}

/*
Dado un nombre de campo y una URL hacemos la petición AJAX para
obtener las opciones posibles para ese campo; el parámetro `forward`
toma una lista de diccionarios de campos relacionados que pasamos en
la petición. Finalmente, `on_after` es una función que se llama luego
de mostrar los resultados.

TODO: filtrar los parámetros de `forward` que usamos para no 
tener que hacer chequeos en la vista de django. 
*/
function updateField(field, baseUrl, forward, onAfter=null) {

    var nro = $.trim($("#"+field+"_input").val());
	
	if (isFinite(nro)){
		nro = parseInt(nro);
    }
	
	function get_val(field) { 
		return $("#id_"+field).val()
	}

	//si el campo actualizado es distrito, reseteamos los valores de seccion y circuito
	if (field == "distrito") {
		$("#id_seccion").val("");
		$("#id_circuito").val("");
	}
	
	var params = forward.reduce((obj, x) => (obj[x] = get_val(x), obj),{});
	var url = baseUrl+'?q='+nro+'&forward='+JSON.stringify(params);
    $.ajax({
      	type: 'GET',
      	url: url
    }).then(function (data) {
		options = data['results'];
		displayResult(field,nro,options);
		if (onAfter) {
			onAfter();
		}
    });
}
