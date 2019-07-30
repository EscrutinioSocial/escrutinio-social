// based on cypress recipes Log in with a required CSRF token
// https://github.com/cypress-io/cypress-example-recipes/blob/master/examples/logging-in__csrf-tokens/cypress/integration/logging-in-csrf-tokens-spec.js
function loginWithCsrfToken(username, password, csrfToken) {
  return cy.request({
    method: 'POST',
    url: '/login/',
    form: true,
    body: {
      username,
      password,
      csrfmiddlewaretoken: csrfToken
    },
  });
}

export function login(username, password) {
  // Obtener csrf token
  // https://github.com/cypress-io/cypress-example-recipes/blob/master/examples/logging-in__csrf-tokens/cypress/integration/logging-in-csrf-tokens-spec.js#L58
  return cy.request('/login')
    .its('body')
    .then((body) => {
      // we can use Cypress.$ to parse the string body
      // thus enabling us to query into it easily
      const $html = Cypress.$(body);
      const csrf  = $html.find("input[name=csrfmiddlewaretoken]").val();
      return loginWithCsrfToken(username, password, csrf);
    })
}

export function loginWithPost(username, password) {
  // Obtener csrf token
  // https://github.com/cypress-io/cypress-example-recipes/blob/master/examples/logging-in__csrf-tokens/cypress/integration/logging-in-csrf-tokens-spec.js#L58
  return cy.request('/login')
    .its('body')
    .then((body) => {
      // we can use Cypress.$ to parse the string body
      // thus enabling us to query into it easily
      const $html = Cypress.$(body);
      const csrf  = $html.find("input[name=csrfmiddlewaretoken]").val();
      return loginWithCsrfToken(username, password, csrf);
    })
}

export function loginWithForm(username, password) {
  cy.visit('/login');
  cy.get('input[name=username]').type(username);
  cy.get('input[name=password]').focus().type(password);
  cy.get('form').submit();
}
