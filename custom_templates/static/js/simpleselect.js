function displayResult(field,value,options){
    var op = value;
    var val = "-1";
    var txt = "";
    if(options.length==1){
	op = options[0].text;
	val = options[0].id;
	txt = options[0].selected_text;
    }
    else if(options.length==0){
	op = "No es un valor válido";
    }
    else {
	op = "Más de un valor válido";
    }
    $("#"+field+"-resultado").val(op);
    $("#id_"+field).val(val);
    $("#"+field+"_input").val(txt);
    if (txt != "") {
	$($('label[for='+field+'_input]')[0]).addClass("active");
    }
    else {
	$($('label[for='+field+'_input]')[0]).removeClass("active");
    }
}

function initializeSimpleSelect(field,base_url,fwd){
    var value = $("#id_"+field).val();
    if(isFinite(value) && value != "-1") {
	var url = base_url+'?ident='+value;
	$.ajax({
      	    type: 'GET',
      	    url: url
	}).then(function (data) {
	    options = data['results'];
	    if(options.length==1){
		displayResult(field,"",options);
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

function updateField(field,base_url,forward){
    var nro = $("#"+field+"_input").val();
    if (isFinite(nro)){
	nro = parseInt(nro);
    }
    function get_val(field){return $("#id_"+field).val()}
    var params = forward.reduce((obj, x) => (obj[x] = get_val(x), obj),{});
    var url = base_url+'?q='+nro+'&forward='+JSON.stringify(params);
    $.ajax({
      	type: 'GET',
      	url: url
    }).then(function (data) {
	options = data['results'];
	displayResult(field,nro,options);
	return true;
    });
}
