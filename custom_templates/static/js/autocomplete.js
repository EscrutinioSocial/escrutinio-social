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

function getValuesMapForJson(response) {
  var valuesMap = {};
  response.options.forEach(function(option) {
    valuesMap[option.text] = option.value;
  })
  return valuesMap;
}

function getAutocompleteData(valuesMap) {
  var data = {};
  Object.keys(valuesMap).forEach(function(key) {
    data[key] = null;
  })
  return data;
}

function getValidationPattern(valuesMap) {
  var values = Object.keys(valuesMap).map(key => key);
  return values.join('|');
}

function getValidationMessage(valuesMap) {
  var values = Object.keys(valuesMap).map(key => key);
  return 'Valores posibles: ' + values.join(', ');
}

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
