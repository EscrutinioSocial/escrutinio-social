// Algunos helpers para crea un autocomplete
// basado en https://materializecss.com/autocomplete.html

// Arma un diccionario con las descripciones y los IDs de las opciones
// ej: { opcion1Description: opcion1Valor }
// a partir de un listado de <option ...> $('options')
function getValuesMapForOption($option) {
  var valuesMap = {};
  $option.filter(function() {
    return !!$(this).attr('value');
  })
  .each(function() {
    valuesMap[$(this).text()] = $(this).attr('value');
  });
  return valuesMap;
}

// Arma un diccionario con las descripciones y los IDs de las opciones
// ej: { opcion1Description: opcion1Valor }
// a partir del respose de la url que devuelve las opciones del autocomplete
function getValuesMapForJson(response) {
  var valuesMap = {};
  response.options.forEach(function(option) {
    valuesMap[option.text] = option.value;
  })
  return valuesMap;
}

// Arma el objeto data (https://materializecss.com/autocomplete.html
// a partie de un diccionario con las descripciones y los IDs de las opciones
function getAutocompleteData(valuesMap) {
  var data = {};
  Object.keys(valuesMap).forEach(function(key) {
    data[key] = null;
  })
  return data;
}

// Arma el patron de validación del input text
// a partie de un diccionario con las descripciones y los IDs de las opciones
function getValidationPattern(valuesMap) {
  var values = Object.keys(valuesMap).map(key => key);
  return values.join('|');
}

// Arma el mensaje de validación del input text
// a partie de un diccionario con las descripciones y los IDs de las opciones
function getValidationMessage(valuesMap) {
  var values = Object.keys(valuesMap).map(key => key);
  return 'Valores posibles: ' + values.join(', ');
}

// Crea un objeto autocomplete a partir de:
// fieldId: el id del input text
// dataUrl: la url que se utiliza para cargar las opciones del autocomplete
// childAutocomplete: si tiene algún autocomplete hijo (dependiente)
function buildAutocomplete(fieldId, dataUrl, childAutocomplete) {
  var autocomplete = {
    dataUrl: dataUrl,
    component: null,
    valuesMap: {},
    childAutocomplete: childAutocomplete
  };
  var $autocomplete = $('#' + fieldId + '-autocomplete');
  autocomplete.component = M.Autocomplete.init($autocomplete[0], {
    onAutocomplete: function(text) {
      // obtengo el valor a partir del texto
      var value = autocomplete.valuesMap[text];

      if (childAutocomplete) {
        // Actualizo el componente hijo cuando se elige la opcion de autocomplete
        $.get(childAutocomplete.dataUrl, {
          'parent_id': value
        },
        function(response) {
          childAutocomplete.valuesMap = getValuesMapForJson(response);
          childAutocomplete.component.updateData(getAutocompleteData(childAutocomplete.valuesMap));

          // Actualizo la validación
          $(childAutocomplete.component.el).attr('pattern', getValidationPattern(childAutocomplete.valuesMap));
          $(childAutocomplete.component.el).attr('title', getValidationMessage(childAutocomplete.valuesMap));

          // Seteo el valor de los hijos en vacio
          $(childAutocomplete.component.el).val('');
          if (childAutocomplete.childAutocomplete) {
            $(childAutocomplete.childAutocomplete.component.el).val('');
            if (childAutocomplete.childAutocomplete.childAutocomplete) {
              $(childAutocomplete.childAutocomplete.childAutocomplete.component.el).val('');
            }
          }
        }, "json" );
      }
    }
  });
  $autocomplete.change(function(a) {
    // obtengo el valor a partir del texto
    var value = autocomplete.valuesMap[$autocomplete.val()];
    // Actualizo el valor del hidden
    $('#' + fieldId).val(value);
  });
  return autocomplete;
}
